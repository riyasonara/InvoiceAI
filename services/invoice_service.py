from readers.pdf_reader import read_pdf
from services.ai_service import extract_invoice


def process_invoice(pdf_path):
    # Read the PDF file
    text = read_pdf(pdf_path)

    if text is None:
        return {
            "success": False,
            "error": "Unable to read the PDF. Please select a valid PDF file.",
        }

    # Extract invoice information using AI service
    with open("prompts/invoice_prompt.txt", "r") as file:
        prompt = file.read()

    return extract_invoice(prompt, text)
