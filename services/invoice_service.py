from readers.pdf_reader import read_pdf
from services.ai_service import extract_invoice
from services.database_service import save_invoice


def process_invoice(pdf_path, user_id):
    # Read the PDF file
    text = read_pdf(pdf_path)

    if text is None:
        return {
            "success": False,
            "code": "unreadable_pdf",
            "error": "Unable to read the PDF. Please select a valid PDF file.",
        }

    # Load the extraction prompt
    with open("prompts/invoice_prompt.txt", "r") as file:
        prompt = file.read()

    # Extract invoice information using the AI service
    result = extract_invoice(prompt, text)

    # If extraction failed, return the error without saving anything.
    if result.get("success") is False:
        return result

    # Extraction worked — persist it under the current owner, then return it.
    save_invoice(result, user_id)
    return result
