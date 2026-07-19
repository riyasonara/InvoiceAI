import os
import sqlite3
import tempfile

from fastapi import Cookie, Depends, FastAPI, File, HTTPException, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from services.invoice_service import process_invoice
from services.database_service import create_database, get_all_invoices
from services.user_service import (
    create_users_table,
    create_user,
    get_user_by_email,
    get_user_by_id,
)
from services.auth_service import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)

# Create the application — this "app" object IS our API.
app = FastAPI()

# Allow our React dev server (a different origin) to call this API.
# Without this, the browser blocks the requests with a CORS error.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # the Vite dev server
    allow_credentials=True,                    # allow the auth cookie to cross origins
    allow_methods=["*"],                       # allow GET, POST, etc.
    allow_headers=["*"],                       # allow any request headers
)

# Make sure the invoices and users tables exist before any request comes in.
create_database()
create_users_table()


def get_current_user(access_token: str | None = Cookie(default=None)):
    """FastAPI dependency: turn the httpOnly auth cookie into the logged-in user.

    Cookie(default=None) reads the "access_token" cookie the browser sends
    automatically. Rejects with 401 if the cookie is missing, invalid, expired,
    or points to a user who no longer exists.
    """
    credentials_error = HTTPException(
        status_code=401,
        detail="Not authenticated.",
    )

    if access_token is None:
        raise credentials_error

    payload = decode_access_token(access_token)
    if payload is None:
        raise credentials_error

    user_id = payload.get("sub")
    if user_id is None:
        raise credentials_error

    user = get_user_by_id(int(user_id))
    if user is None:
        raise credentials_error

    return user


# What the caller must send to register. Pydantic validates both fields:
# a real email format, and a password of at least 8 characters.
class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


# What we send back. It has NO password field, so even if we accidentally
# returned the hash, FastAPI would strip it to just these fields.
class UserResponse(BaseModel):
    id: int
    email: EmailStr


# Login just needs the credentials — no min-length check here; we only
# validate length when *creating* a password, not when checking one.
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


# When someone visits the home page ("/"), run this function.
@app.get("/")
def read_root():
    return {"message": "InvoiceAI is running"}


# Create a new user account.
@app.post("/register", response_model=UserResponse, status_code=201)
def register(request: RegisterRequest):
    # Never store the raw password — hash it first.
    hashed = hash_password(request.password)

    try:
        return create_user(request.email, hashed)
    except sqlite3.IntegrityError:
        # The users.email UNIQUE constraint fired: this email is taken.
        raise HTTPException(
            status_code=409,  # 409 Conflict
            detail="An account with this email already exists.",
        )


# Log in with email + password. On success, sets the JWT in an httpOnly cookie
# and returns the user (the token itself never touches the response body).
@app.post("/login", response_model=UserResponse)
def login(request: LoginRequest, response: Response):
    user = get_user_by_email(request.email)

    # SECURITY: return the SAME vague error whether the email is unknown or the
    # password is wrong. Revealing which would let an attacker discover valid
    # emails one guess at a time.
    if user is None or not verify_password(request.password, user["hashed_password"]):
        raise HTTPException(
            status_code=401,  # 401 Unauthorized
            detail="Incorrect email or password.",
        )

    token = create_access_token(user["id"])

    # Store the JWT in an httpOnly cookie: the browser sends it automatically on
    # every request, and JavaScript cannot read it (protects against XSS theft).
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,                             # JavaScript can't read it
        samesite="lax",                            # not sent on cross-site requests (CSRF defense)
        secure=False,                              # DEV ONLY over HTTP; set True in production (HTTPS)
        max_age=ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # cookie expires with the token
    )

    return {"id": user["id"], "email": user["email"]}


# Log out by clearing the auth cookie. Because the cookie is httpOnly, only the
# server can remove it — the frontend can't do it in JavaScript.
@app.post("/logout")
def logout(response: Response):
    response.delete_cookie(key="access_token")
    return {"message": "Logged out."}


# Return the currently logged-in user. Depends(get_current_user) makes this
# endpoint require a valid bearer token — our first PROTECTED route.
@app.get("/me", response_model=UserResponse)
def read_me(current_user: dict = Depends(get_current_user)):
    return current_user


# When someone GETs "/invoices", return every saved invoice.
# Depends(get_current_user) makes this require a valid token.
@app.get("/invoices")
def list_invoices(current_user: dict = Depends(get_current_user)):
    return get_all_invoices(current_user["id"])


# Uploads bigger than this are rejected before we do any work.
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

# Translates a service-layer error code into the HTTP status it should become.
# The service layer stays HTTP-ignorant; this mapping lives in the web layer.
ERROR_STATUS = {
    "unreadable_pdf": 422,       # 422 caller sent a file we couldn't read
    "ai_unavailable": 503,       # 503 the upstream AI provider is down
    "invalid_ai_response": 500,  # 500 the AI returned something unusable
}


# When someone POSTs a PDF file to "/extract", run this function.
# The file arrives as multipart/form-data; FastAPI hands it to us as an UploadFile.
@app.post("/extract")
async def extract(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    # Guard 1: must be a PDF. content_type is the MIME type the browser sent.
    # (This is a cheap early filter — the real check is that read_pdf() can
    # actually parse it, which happens downstream.)
    if file.content_type != "application/pdf":
        raise HTTPException(
            status_code=415,  # 415 Unsupported Media Type
            detail="Only PDF files are supported.",
        )

    # Read the uploaded file's raw bytes into memory.
    contents = await file.read()

    # Guard 2: reject files that are too large.
    if len(contents) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,  # 413 Content Too Large
            detail="File is too large. The maximum size is 10 MB.",
        )

    # Write those bytes to a temporary file on disk, because our existing
    # read_pdf() expects a file PATH. This is the one place that knows about
    # storage — swap it for Azure Blob later without touching anything else.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        temp_path = tmp.name

    try:
        # Hand the temp path to our extract -> save pipeline, tagged with the
        # current user so the invoice is saved under their account.
        result = process_invoice(temp_path, current_user["id"])
    finally:
        # Always delete the temp file, even if extraction raised an error.
        os.remove(temp_path)

    # Translate a service-layer failure into the right HTTP status.
    # Unknown/missing codes default to 500 (something unexpected broke).
    if result.get("success") is False:
        status_code = ERROR_STATUS.get(result.get("code"), 500)
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result
