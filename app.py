import os
import base64
import json
import anthropic
from flask import Flask, request, jsonify
from fill_retainer import fill_retainer_bp

app = Flask(__name__)
app.register_blueprint(fill_retainer_bp)
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """You are a legal data extraction assistant. Extract structured data from police reports for a personal injury law firm. Return ONLY a valid JSON object with these exact keys:

- Accident Date (YYYY-MM-DD format; top left of document)
- Accident Location (street address or intersection; lower half of doc)
- Accident Description (1-2 sentence factual summary of how the accident occurred; lower half of doc)
- Client Plate Number (Vehicle 1 plate — the plaintiff; left side of form)
- Defendant Name (LAST, First Name format)
- Defendant Plate Number (Vehicle 2 plate)
- Num Injured (integer; extract from "No. Injured" field top of form)
- Client Gender (M or F — gender of Vehicle 1 driver; left side of form)
- Statute of Limitations Date (Accident Date + 8 years, YYYY-MM-DD)
- client_last_name (plaintiff last name, UPPERCASE)
- client_first_name (plaintiff first name, Title Case)
- client_street_number (house/building number only from Vehicle 1 driver address e.g. "195"; left side of form)
- client_street_name (street name only from Vehicle 1 driver address, UPPERCASE, no suffix e.g. "ILLINOIS AVENUE"; left side of form)
- client_city (city only from Vehicle 1 driver address, UPPERCASE, no suffix e.g. "CHICAGO"; left side of form)
- client_state (state only from Vehicle 1 driver address, UPPERCASE, no suffix e.g. "IL"; left side of form)
- client_zip_code (zip code only from Vehicle 1 driver address, INTEGER e.g. "60614"; left side of form)
- client_date_of_birth (YYYY-MM-DD format; left side of form below 'City of Town' field)

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

        result_text = message.content[0].text.strip()
        if result_text.startswith("```"):
            result_text = result_text.split("```", 2)[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.rsplit("```", 1)[0].strip()

        # Validate the response to detect corrupted/unreadable files
        try:
            # Try to parse the JSON response
            data = json.loads(result_text)

            # Check for critical fields that indicate a readable police report
            critical_fields = ["Accident Date", "Defendant Name", "Client Gender",
                             "client_last_name", "client_first_name"]

            missing_critical = [field for field in critical_fields if field not in data or not data[field]]

            if missing_critical:
                # File was processed but critical data is missing = corrupted/unreadable
                return jsonify({
                    "corrupted_file": True,
                    "error": "File was parsed but is unreadable or corrupted. Missing critical fields: " + ", ".join(missing_critical),
                    "result": result_text  # Include partial data for reference
                }), 200

            return jsonify({"result": result_text})

        except json.JSONDecodeError:
            # Response is not valid JSON = corrupted file
            return jsonify({
                "corrupted_file": True,
                "error": "File was parsed but returned invalid data format. Unable to extract structured information.",
                "raw_response": result_text
            }), 200

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
