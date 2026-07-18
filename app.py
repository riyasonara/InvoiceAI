from services.invoice_service import process_invoice
from services.database_service import create_database, get_all_invoices

# Make sure the invoices table exists before we touch it
create_database()

# Ask the user which PDF to process
pdf_path = input("Enter PDF path: ")

# Read the PDF -> load the prompt -> call Gemini -> save -> return the invoice.
# The saving now happens inside process_invoice, so this file just reports the result.
result = process_invoice(pdf_path)

if result.get("success") is False:
    print(result["error"])
else:
    print("Invoice saved successfully!\n")

    print("Vendor:", result["vendor"])
    print("Invoice Number:", result["invoice_number"])
    print("GST:", result["gst"])
    print("Total:", result["total"])

# Show everything stored so far
print("\nAll invoices in the database:")
for invoice in get_all_invoices():
    print(invoice)
