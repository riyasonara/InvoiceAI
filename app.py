from services.invoice_service import process_invoice
from services.database_service import create_database, get_all_invoices, save_invoice

# Make sure the invoices table exists before we touch it
create_database()

# Ask the user which PDF to process
pdf_path = input("Enter PDF path: ")

# Read the PDF -> load the prompt -> call Gemini -> get structured data back
result = process_invoice(pdf_path)

# process_invoice returns {"success": False, "error": ...} when something failed.
# On success it returns the extracted invoice dict directly (no "success" key),
# so an absent key means "this worked".
if result.get("success") is False:
    print(result["error"])
else:
    # Persist the invoice so it outlives this single run
    save_invoice(result)
    print("Invoice saved successfully!\n")

    print("Vendor:", result["vendor"])
    print("Invoice Number:", result["invoice_number"])
    print("GST:", result["gst"])
    print("Total:", result["total"])

# Show everything stored so far, including what we just saved
print("\nAll invoices in the database:")
for invoice in get_all_invoices():
    print(invoice)
