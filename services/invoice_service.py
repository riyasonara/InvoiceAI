from readers.pdf_reader import read_pdf
from services.ai_service import extract_invoice, extract_invoice_from_pdf
from services.database_service import save_invoice


def process_invoice(pdf_path, user_id):
    # Read the PDF's text layer first (the cheap path).
    text = read_pdf(pdf_path)

    if text is None:
        return {
            "success": False,
            "code": "unreadable_pdf",
            "error": "Unable to read the PDF. Please select a valid PDF file.",
        }

    # Load the extraction prompt (same instructions for both paths).
    with open("prompts/invoice_prompt.txt", "r") as file:
        prompt = file.read()

    # ROUTE: if pypdf found real text, use the cheap text path. If the text
    # layer is empty (a scanned or photographed PDF), escalate to Gemini's
    # vision by sending the PDF file itself.
    if text.strip():
        result = extract_invoice(prompt, text)
    else:
        with open(pdf_path, "rb") as pdf_file:
            pdf_bytes = pdf_file.read()
        result = extract_invoice_from_pdf(prompt, pdf_bytes)

    # If extraction failed, return the error without saving anything.
    if result.get("success") is False:
        return result

    # Extraction worked — persist it under the current owner, then return it.
    save_invoice(result, user_id)
    return result
