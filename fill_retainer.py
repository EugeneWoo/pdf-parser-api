import os
import base64
import io
from docx import Document
from flask import Blueprint, request, jsonify

fill_retainer_bp = Blueprint("fill_retainer", __name__)

TEMPLATE_PATH = os.path.join(os.path.dirname(__file__), "retainer_template.docx")


@fill_retainer_bp.route("/fill-retainer", methods=["POST"])
def fill_retainer():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    required = ["client_name", "accident_date", "defendant_name", "pronoun_his_her",
                "pronoun_he_she", "accident_location", "client_plate", "injury_paragraph", "sol_date"]
    missing = [k for k in required if k not in data]
    if missing:
        return jsonify({"error": f"Missing fields: {missing}"}), 400

    if not os.path.exists(TEMPLATE_PATH):
        return jsonify({"error": "Template file not found on server"}), 500

    doc = Document(TEMPLATE_PATH)

    def replace_in_paragraph(para, replacements):
        for key, val in replacements.items():
            placeholder = "{{" + key + "}}"
            if placeholder in para.text:
                for run in para.runs:
                    if placeholder in run.text:
                        run.text = run.text.replace(placeholder, val)

    replacements = {
        "client_name": data["client_name"],
        "accident_date": data["accident_date"],
        "defendant_name": data["defendant_name"],
        "pronoun_his_her": data["pronoun_his_her"],
        "pronoun_he_she": data["pronoun_he_she"],
        "pronoun_him_her": data.get("pronoun_him_her", data["pronoun_his_her"]),
        "accident_location": data["accident_location"],
        "client_plate": data["client_plate"],
        "injury_paragraph": data["injury_paragraph"],
        "sol_date": data["sol_date"],
    }

    for para in doc.paragraphs:
        replace_in_paragraph(para, replacements)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    replace_in_paragraph(para, replacements)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)

    docx_base64 = base64.standard_b64encode(buf.read()).decode("utf-8")
    return jsonify({"docx_base64": docx_base64})
