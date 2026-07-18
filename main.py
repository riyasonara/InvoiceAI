import os
import sqlite3
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, Field

from services.invoice_service import process_invoice
from services.database_service import create_database, get_all_invoices
from services.user_service import create_users_table, create_user, get_user_by_email
from services.auth_service import hash_password, verify_password, create_access_token

# Create the application — this "app" object IS our API.
app = FastAPI()

# Allow our React dev server (a different origin) to call this API.
# Without this, the browser blocks the requests with a CORS error.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # the Vite dev server
    allow_methods=["*"],                       # allow GET, POST, etc.
    allow_headers=["*"],                       # allow any request headers
)

# Make sure the invoices and users tables exist before any request comes in.
create_database()
create_users_table()


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


# What login returns: the JWT and its type (the standard "bearer" scheme).
class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


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


# Log in with email + password, receive a JWT access token.
@app.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
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
    return {"access_token": token, "token_type": "bearer"}


# When someone GETs "/invoices", return every saved invoice.
@app.get("/invoices")
def list_invoices():
    return get_all_invoices()


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
async def extract(file: UploadFile = File(...)):
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
        # Hand the temp path to our existing extract -> save pipeline.
        result = process_invoice(temp_path)
    finally:
        # Always delete the temp file, even if extraction raised an error.
        os.remove(temp_path)

    # Translate a service-layer failure into the right HTTP status.
    # Unknown/missing codes default to 500 (something unexpected broke).
    if result.get("success") is False:
        status_code = ERROR_STATUS.get(result.get("code"), 500)
        raise HTTPException(status_code=status_code, detail=result["error"])

    return result
