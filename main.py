import os
import tempfile

from fastapi import FastAPI, File, UploadFile

from services.invoice_service import process_invoice
from services.database_service import create_database, get_all_invoices

# Create the application — this "app" object IS our API.
app = FastAPI()

# Make sure the invoices table exists before any request comes in.
create_database()


# When someone visits the home page ("/"), run this function.
@app.get("/")
def read_root():
    return {"message": "InvoiceAI is running"}


# When someone GETs "/invoices", return every saved invoice.
@app.get("/invoices")
def list_invoices():
    return get_all_invoices()


# When someone POSTs a PDF file to "/extract", run this function.
# The file arrives as multipart/form-data; FastAPI hands it to us as an UploadFile.
@app.post("/extract")
async def extract(file: UploadFile = File(...)):
    # Read the uploaded file's raw bytes into memory.
    contents = await file.read()

    # Write those bytes to a temporary file on disk, because our existing
    # read_pdf() expects a file PATH. This is the one place that knows about
    # storage — swap it for Azure Blob later without touching anything else.
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(contents)
        temp_path = tmp.name

    try:
        # Hand the temp path to our existing extract -> save pipeline.
        return process_invoice(temp_path)
    finally:
        # Always delete the temp file, even if extraction raised an error.
        os.remove(temp_path)
