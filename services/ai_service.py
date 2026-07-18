from google import genai
from google.genai import types
from google.genai.errors import ServerError
from dotenv import load_dotenv
import os
import json

# Load environment variables
load_dotenv()

# Create Gemini client
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


def _extract_json(text):
    """Pull the JSON object out of a raw model response.

    Even with JSON mode on, LLMs can occasionally wrap output in markdown
    fences or add stray text. Taking the substring from the first '{' to the
    last '}' recovers the object in those cases. If there are no braces, we
    return the text unchanged so json.loads raises a clean error.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1:
        return text
    return text[start:end + 1]


def extract_invoice(prompt, invoice_text):
    try:
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt + "\n" + invoice_text,
            # Constrain the model to return valid JSON (prevent the problem).
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )

        # Defensively clean the text before parsing (repair, just in case).
        return json.loads(_extract_json(response.text))

    except ServerError:
        return {
            "success": False,
            "code": "ai_unavailable",
            "error": "Gemini service is temporarily unavailable. Please try again later."
        }

    except json.JSONDecodeError:
        return {
            "success": False,
            "code": "invalid_ai_response",
            "error": "Gemini returned invalid JSON."
        }
