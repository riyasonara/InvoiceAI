from google import genai
from google.genai.errors import ServerError
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()

# Create Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def extract_invoice(prompt, invoice_text):
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt + "\n" + invoice_text,
        )

        return json.loads(response.text)

    except ServerError:
        return {
            "success": False,
            "error": "Gemini service is temporarily unavailable. Please try again later."
        }

    except json.JSONDecodeError:
        return {
            "success": False,
            "error": "Gemini returned invalid JSON."
        }