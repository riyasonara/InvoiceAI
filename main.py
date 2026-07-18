from fastapi import FastAPI
from pydantic import BaseModel

from services.invoice_service import process_invoice
from services.database_service import create_database, get_all_invoices

# Create the application — this "app" object IS our API.
app = FastAPI()

# Make sure the invoices table exists before any request comes in.
create_database()


# Describes the JSON body the caller must send to /extract.
# Like a request DTO in .NET: one field, pdf_path, which must be a string.
class InvoiceRequest(BaseModel):
    pdf_path: str


# When someone visits the home page ("/"), run this function.
@app.get("/")
def read_root():
    return {"message": "InvoiceAI is running"}


# When someone GETs "/invoices", return every saved invoice.
@app.get("/invoices")
def list_invoices():
    return get_all_invoices()


# When someone POSTs an invoice to "/extract", run this function.
# FastAPI reads the JSON body into an InvoiceRequest object for us.
# Extraction AND saving both happen inside process_invoice now.
@app.post("/extract")
def extract(request: InvoiceRequest):
    return process_invoice(request.pdf_path)
