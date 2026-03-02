# PDF Parser API for Richards & Law

Automated legal document processing system for personal injury law firm intake workflows. This API extracts structured data from New York State Motor Vehicle Accident Reports (MV-104) and generates customized retainer agreements.

## Challenge Context

**Problem:** Richards & Law receives police reports from potential clients and needs to manually extract data to draft retainer agreements. This process is time-consuming, error-prone, and doesn't scale.

**Solution:** Automated pipeline that:
1. Parses police reports to extract key fields
2. Detects corrupted/unreadable documents for client follow-up
3. Generates personalized retainer agreements with correct pronouns and scope
4. Sends automated emails with scheduling links

**Workflow:**
```
Police Report → /parse → Extract Data → /fill-retainer → Generate DOCX → Email Client
```

---

## Endpoints

### 1. `/parse` - Extract Data from Police Report

Extracts structured information from NY MV-104 accident reports using Claude's vision capabilities.

**Method:** `POST`

**Request:**
- `Content-Type: multipart/form-data`
- Body: `file` (PDF document)

**Success Response (200):**
```json
{
  "result": "{...JSON data...}"
}
```

**Corrupted File Response (200):**
```json
{
  "corrupted_file": true,
  "error": "File was parsed but is unreadable or corrupted. Missing critical fields: Accident Date, Defendant Name",
  "result": "{...partial data...}"
}
```

**Error Response (400/500):**
```json
{
  "error": "Error message"
}
```

**Extracted Fields:**
| Field | Type | Description |
|-------|------|-------------|
| `Accident Date` | string | YYYY-MM-DD format |
| `Accident Location` | string | Street address or intersection |
| `Accident Description` | string | 1-2 sentence factual summary |
| `Client Plate Number` | string | Vehicle 1 (plaintiff) plate |
| `Defendant Name` | string | LAST, FIRST format |
| `Defendant Plate Number` | string | Vehicle 2 plate |
| `Num Injured` | integer | Number of injured people |
| `Client Gender` | string | "M" or "F" |
| `Statute of Limitations Date` | string | Accident Date + 8 years (YYYY-MM-DD) |
| `client_last_name` | string | UPPERCASE |
| `client_first_name` | string | Title Case |
| `client_street_number` | string | House/building number |
| `client_street_name` | string | UPPERCASE, no suffix |
| `client_city` | string | UPPERCASE, no suffix |
| `client_state` | string | UPPERCASE, 2-letter code |
| `client_zip_code` | string | ZIP code |

**Corrupted File Detection:**
- Validates that critical fields (`Accident Date`, `Defendant Name`, `Client Gender`, `client_last_name`, `client_first_name`) are present
- Returns `corrupted_file: true` if critical data is missing (e.g., poor quality scan, wrong document type)
- Returns 200 status to allow workflow branching in automation tools

---

### 2. `/fill-retainer` - Generate Customized Retainer Agreement

Fills a Word template with extracted client data and generates a personalized retainer agreement.

**Method:** `POST`

**Request:**
- `Content-Type: application/json`
- Body: Data from `/parse` endpoint

**Request Body:**
```json
{
  "client_first_name": "Guillermo",
  "client_last_name": "REYES",
  "Accident Date": "2018-12-06",
  "Defendant Name": "FRANCOIS, LIONEL",
  "Client Gender": "M",
  "Accident Location": "Flatbush Avenue and Plaza Street East, Kings County, NY",
  "Client Plate Number": "XCGY85",
  "Accident Description": "V1 was driving northbound...",
  "Num Injured": 0,
  "Statute of Limitations Date": "2026-12-06"
}
```

**Success Response (200):**
```json
{
  "docx_base64": "base64-encoded-docx-file-content"
}
```

**Error Responses:**
- `400`: Missing required fields
- `500`: Template file not found, server error

**Data Transformations:**
- `client_name` = `client_first_name` + `client_last_name`
- Pronouns derived from `Client Gender` (M → his/he/him, F → her/she/her)
- `injury_paragraph` conditional logic:
  - **Num Injured > 0:** "Additionally, since the motor vehicle accident involved an injured person, Attorney will also investigate potential bodily injury claims and review relevant medical records to substantiate non-economic damages."
  - **Num Injured = 0:** "However, since the motor vehicle accident involved no reported injured people, the scope of this engagement is strictly limited to the recovery of property damage and loss of use."

**Template Placeholders:**
- `{{client_name}}`
- `{{accident_date}}`
- `{{defendant_name}}`
- `{{pronoun_his_her}}`
- `{{pronoun_he_she}}`
- `{{pronoun_him_her}}`
- `{{accident_location}}`
- `{{client_plate}}`
- `{{accident_description}}`
- `{{injury_paragraph}}`
- `{{sol_date}}`

---

## Additional Endpoints

### `/health` - Health Check
**Method:** `GET`
**Response:** `{"status": "ok"}`

### `/debug` - Debug Request Info
**Method:** `POST`
**Response:** Returns file info, form data, and content type for debugging

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key for Claude |
| `PORT` | No | Server port (default: 5000) |

---

## Deployment

### Render (render.yaml)
```yaml
services:
  - type: web
    name: pdf-parser-api
    runtime: python
    buildCommand: pip install -r requirements.txt
    startCommand: gunicorn app:app
    envVars:
      - key: ANTHROPIC_API_KEY
        sync: false
```

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY="your-key-here"

# Run server
python app.py
# or with gunicorn
gunicorn app:app
```

---

## Integration with make.com

### Example Workflow:

1. **Webhook Trigger** → Receives email with police report attachment
2. **HTTP Module (POST /parse)** → Extracts data from PDF
3. **Filter/Router** → Check if `corrupted_file == true`
   - **If true** → Send email to client requesting better document
   - **If false** → Continue to step 4
4. **HTTP Module (POST /fill-retainer)** → Generate retainer DOCX
5. **Base64 Decode** → Convert `docx_base64` to file
6. **Email Module** → Send retainer agreement to client with Calendly link

---

## Files

```
pdf-parser-api/
├── app.py                      # Flask app with /parse endpoint
├── fill_retainer.py            # Blueprint with /fill-retainer endpoint
├── retainer_template.docx      # Word template with placeholders
├── requirements.txt            # Python dependencies
├── render.yaml                 # Render deployment config
└── README.md                   # This file
```

---

## Dependencies

- Flask - Web framework
- Anthropic SDK - Claude API for vision/OCR
- python-docx - Word document generation
- Gunicorn - Production WSGI server

---

## Example Use Case

**Input:** NY MV-104 Police Report PDF for Guillermo Reyes

**Step 1: Parse**
```bash
curl -X POST https://your-api.com/parse \
  -F "file=@police_report.pdf"
```

**Response:**
```json
{
  "result": "{\"Accident Date\": \"2018-12-06\", \"Defendant Name\": \"FRANCOIS, LIONEL\", ...}"
}
```

**Step 2: Fill Retainer**
```bash
curl -X POST https://your-api.com/fill-retainer \
  -H "Content-Type: application/json" \
  -d '{"client_first_name": "Guillermo", "client_last_name": "REYES", ...}'
```

**Output:** Personalized retainer agreement DOCX with:
- Correct client name: "Guillermo REYES"
- Proper pronouns: "his/he/him" (derived from Gender: M)
- Correct scope: Property damage only (Num Injured = 0)
- Accurate details: Flatbush Avenue, XCGY85 plate, SOL date 2026-12-06

---

## Error Handling

### Corrupted/Unreadable Files
Poor quality scans, photocopies, or non-police report documents are detected and flagged:
- API returns `corrupted_file: true` with 200 status
- Automation can trigger client notification workflow
- Example message: *"The police report you submitted appears to be a poor quality copy that we cannot read. Please provide a clearer scan or the original document."*

### Validation
- Empty file → 400 error
- Missing critical fields in parsed data → `corrupted_file: true`
- Template file missing → 500 error

---

## License

Built for Swans Applied AI Hackathon 2026 - Legal Engineering Challenge
