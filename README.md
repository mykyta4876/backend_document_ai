# Document AI REST API Backend (Project B)

Standalone backend that exposes Document AI processing via REST API. Deploy this in **Project B** (where Document AI processors exist) to allow **Project A** (VM in a different org) to use Document AI without cross-org IAM.

## Architecture

```
Project A (VM)  --REST API-->  Project B (this backend)  --Document AI-->  GCP Document AI
```

- **Project A**: Sends documents (GCS path or file) via HTTP, receives extracted data
- **Project B**: Runs this backend + Document AI in same org, no cross-org IAM needed

## Setup

### 1. Deploy to Project B

```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev git uvicorn

git clone https://github.com/mykyta4876/backend_document_ai.git
cd backend_document_ai

python3 -m venv venv

source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env
# Edit .env with Project B GCP project, processor IDs
```

### 2. Environment variables

Create `.env` in `backend_document_ai/`:

```bash
GCP_PROJECT_ID=proud-cathode-472317-u6
DOCUMENT_AI_LOCATION=us
DOCUMENT_AI_FORM_PROCESSOR=b0537b374c7fef1f
DOCUMENT_AI_BANK_STATEMENT_PROCESSOR=aabacea7083545ab
API_KEY=Xk9mP2qR7sT4vW8yZ1aB3cD5eF6gH9iJ0kL2mN4oP6qR8s   # Optional: require X-API-Key header from callers
```

### 3. Configure GCS access

If Project A stores documents in its bucket (`gs://project-a-bucket/...`), grant **Project B's service account** read access to that bucket:

Project B service account: 5331102408-compute@developer.gserviceaccount.com

```bash
# Project B's default compute SA or your custom SA
gsutil iam ch serviceAccount:PROJECT_B_SA@PROJECT_B.iam.gserviceaccount.com:objectViewer gs://PROJECT_A_BUCKET

gsutil iam ch serviceAccount:5331102408-compute@developer.gserviceaccount.com:objectViewer gs://casa-deals-uploads

```

Alternatively, use a shared bucket both projects can access.

### 4. Deploy (e.g. Cloud Run)

```bash
gcloud run deploy doc-ai-api --source . --region us-central1 --project PROJECT_B_ID
```

### 5. Configure Project A

In Project A's `backend/.env`:

```bash
DOCUMENT_AI_MODE=rest
DOCUMENT_AI_REST_API_URL=https://doc-ai-api-xxx.run.app
DOCUMENT_AI_REST_API_KEY=your-secret-key  # Optional, set API_KEY in Project B if used
```

## API Endpoints

### POST /process/form

Process application form. Returns extracted business info (EIN, TIB, etc.).

**JSON body:**
```json
{"storage_path": "gs://bucket/path/to/form.pdf", "mime_type": "application/pdf"}
```

### POST /process/bank

Process bank statement. Returns transactions, daily balances, etc.

**JSON body:**
```json
{"storage_path": "gs://bucket/path/to/statement.pdf", "mime_type": "application/pdf"}
```

**Headers (optional):**
- `X-API-Key`: Required if `API_KEY` is set in Project B

## Development

```bash
uvicorn app.main:app --reload --port 80

sudo /home/elon/backend_document_ai/venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 80
```


Option 4: Use systemd (with sudo)
Create /etc/systemd/system/doc-ai-api.service:
[Unit]
Description=Document AI REST API
After=network.target

[Service]
User=root
WorkingDirectory=/path/to/backend_document_ai
ExecStart=/usr/bin/uvicorn app.main:app --host 0.0.0.0 --port 80
Restart=always

[Install]
WantedBy=multi-user.target

Then:
sudo systemctl daemon-reload
sudo systemctl enable doc-ai-api
sudo systemctl start doc-ai-api
