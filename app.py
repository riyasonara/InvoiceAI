from google import genai
from dotenv import load_dotenv
import os

from services.invoice_service import process_invoice
from services.database_service import create_database, get_all_invoices, save_invoice

create_database()

invoices = get_all_invoices()

print(invoices)

# invoice = {
#     "vendor": "ABC Electronics",
#     "invoice_number": "INV-1001",
#     "invoice_date": "2026-07-10",
#     "gst": 396,
#     "total": 2596,
# }

# save_invoice(invoice)

# print("Invoice saved successfully!")

# Load environment variables from .env file
load_dotenv()

# Set the API key for Google GenAI
api_key = os.getenv("GEMINI_API_KEY")

# Create a gemini client
client = genai.Client(api_key=api_key)

pdf_path = input("Enter PDF path: ")

result = process_invoice(pdf_path)

if result.get("success") == False:
    print(result["error"])
else:
    print("Vendor:", result["vendor"])
    print("Invoice Number:", result["invoice_number"])
    print("GST:", result["gst"])
    print("Total:", result["total"])
