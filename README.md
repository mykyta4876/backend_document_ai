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
cd backend_document_ai
pip install -r requirements.txt
cp .env.example .env
# Edit .env with Project B GCP project, processor IDs
```

### 2. Environment variables

Create `.env` in `backend_document_ai/`:

```bash
GCP_PROJECT_ID=your-project-b-id
DOCUMENT_AI_LOCATION=us
DOCUMENT_AI_FORM_PROCESSOR=94bed4fec40208e3
DOCUMENT_AI_BANK_STATEMENT_PROCESSOR=5dd3a055ba3a8e44
API_KEY=   # Optional: require X-API-Key header from callers
```

### 3. Configure GCS access

If Project A stores documents in its bucket (`gs://project-a-bucket/...`), grant **Project B's service account** read access to that bucket:

```bash
# Project B's default compute SA or your custom SA
gsutil iam ch serviceAccount:PROJECT_B_SA@PROJECT_B.iam.gserviceaccount.com:objectViewer gs://PROJECT_A_BUCKET
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
uvicorn app.main:app --reload --port 8001
```
