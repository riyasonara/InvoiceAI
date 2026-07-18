from pypdf import PdfReader


def read_pdf(file_path):
    try:
        reader = PdfReader(file_path)

        text = ""

        for page in reader.pages:
            text += page.extract_text() + "\n"

        return text

    except Exception as e:
        print(f"Error reading PDF: {e}")
        return None
