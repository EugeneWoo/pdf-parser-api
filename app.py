import os
import base64
import anthropic
from flask import Flask, request, jsonify

app = Flask(__name__)
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are a legal data extraction assistant. Extract structured data from police reports for a personal injury law firm. Return ONLY a valid JSON object with these exact keys:

- Accident Date (YYYY-MM-DD format; top left of document)
- Accident Location (street address or intersection; lower half of doc)
- Accident Description (1-2 sentence factual summary of how the accident occurred; lower half of doc)
- Client Plate Number (Vehicle 1 plate — the plaintiff; left side of form)
- Defendant Name (LAST, FIRST format)
- Defendant Plate Number (Vehicle 2 plate)
- Num Injured (integer; extract from "No. Injured" field top of form)
- Client Gender (M or F — gender of Vehicle 1 driver; left side of form)
- Statute of Limitations Date (Accident Date + 8 years, YYYY-MM-DD)
- client_last_name (plaintiff last name, UPPERCASE)
- client_first_name (plaintiff first name, Title Case)
- client_street_number (house/building number only from Vehicle 1 driver address e.g. "195"; left side of form)
- client_street_name (street name only from Vehicle 1 driver address, UPPERCASE, no suffix e.g. "ILLINOIS"; left side of form)

Rules:
- Plaintiff/client is always the Vehicle 1 driver
- SOL date = accident date + exactly 8 years
- client_street_number and client_street_name come from the Vehicle 1 driver address field
- Return raw JSON only — no markdown, no explanation"""


@app.route("/parse", methods=["POST"])
def parse_pdf():
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    pdf_file = request.files["file"]
    pdf_bytes = pdf_file.read()

    if len(pdf_bytes) == 0:
        return jsonify({"error": "File is empty"}), 400

    pdf_base64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")

    try:
        message = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Extract all required fields from this police report and return the JSON object.",
                        },
                    ],
                }
            ],
        )
        return jsonify({"result": message.content[0].text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/debug", methods=["POST"])
def debug():
    files_info = {k: {"size": len(v.read()), "content_type": v.content_type, "filename": v.filename} for k, v in request.files.items()}
    form_info = {k: v for k, v in request.form.items()}
    return jsonify({"files": files_info, "form": form_info, "content_type": request.content_type})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
