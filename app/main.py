"""
Document AI REST API Backend (Project B)
Exposes Document AI processing for cross-org access from Project A.
"""
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import logging
import time

from app.config import settings
from app.document_processor import DocumentProcessor

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Document AI REST API",
    description="Document AI processing API for cross-org access (Project B)",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log every request and response with timing."""
    start = time.time()
    logger.info(f">>> REQUEST {request.method} {request.url.path} from {request.client.host if request.client else 'unknown'}")
    logger.info(f"    Headers: Content-Type={request.headers.get('content-type', 'N/A')}")
    if request.headers.get("X-API-Key"):
        logger.info("    X-API-Key: [present]")
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(f"<<< RESPONSE {response.status_code} in {elapsed:.2f}s")
    return response


def _verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key if configured."""
    if settings.API_KEY:
        if not x_api_key or x_api_key != settings.API_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "document-ai-api"}


@app.post("/process/form")
async def process_form(
    request: Request,
    x_api_key: Optional[str] = Header(None),
):
    """
    Process application form.
    - Multipart: upload file as form field "file"
    - JSON: send {"storage_path": "gs://bucket/path", "mime_type": "application/pdf"}
    """
    _verify_api_key(x_api_key)
    processor = DocumentProcessor()
    try:
        content_type = request.headers.get("content-type", "")
        logger.info(f"[process/form] Content-Type: {content_type}")
        if "multipart/form-data" in content_type:
            form = await request.form()
            file = form.get("file")
            if file and hasattr(file, "read"):
                content = await file.read()
                mime = getattr(file, "content_type", None) or "application/pdf"
                logger.info(f"[process/form] Processing uploaded file, size={len(content)} bytes, mime={mime}")
                result = processor.process_form(content=content, mime_type=mime)
                logger.info(f"[process/form] Extracted {len([k for k, v in result.items() if v])} fields")
                return result
            raise HTTPException(status_code=400, detail="File upload required for multipart request")
        body = await request.json()
        storage_path = body.get("storage_path")
        mime_type = body.get("mime_type", "application/pdf")
        logger.info(f"[process/form] Processing storage_path={storage_path}, mime_type={mime_type}")
        if not storage_path:
            raise HTTPException(status_code=400, detail="storage_path required in JSON body")
        result = processor.process_form(storage_path=storage_path, mime_type=mime_type)
        logger.info(f"[process/form] Extracted {len([k for k, v in result.items() if v])} fields")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing form")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process/bank")
async def process_bank_statement(
    request: Request,
    x_api_key: Optional[str] = Header(None),
):
    """
    Process bank statement.
    - Multipart: upload file as form field "file"
    - JSON: send {"storage_path": "gs://bucket/path", "mime_type": "application/pdf"}
    """
    _verify_api_key(x_api_key)
    processor = DocumentProcessor()
    try:
        content_type = request.headers.get("content-type", "")
        logger.info(f"[process/bank] Content-Type: {content_type}")
        if "multipart/form-data" in content_type:
            form = await request.form()
            file = form.get("file")
            if file and hasattr(file, "read"):
                content = await file.read()
                mime = getattr(file, "content_type", None) or "application/pdf"
                logger.info(f"[process/bank] Processing uploaded file, size={len(content)} bytes, mime={mime}")
                result = processor.process_bank_statement(content=content, mime_type=mime)
                logger.info(f"[process/bank] Extracted {len(result.get('transactions', []))} transactions, {len(result.get('daily_balances', []))} daily balances")
                return result
            raise HTTPException(status_code=400, detail="File upload required for multipart request")
        body = await request.json()
        storage_path = body.get("storage_path")
        mime_type = body.get("mime_type", "application/pdf")
        logger.info(f"[process/bank] Processing storage_path={storage_path}, mime_type={mime_type}")
        if not storage_path:
            raise HTTPException(status_code=400, detail="storage_path required in JSON body")
        result = processor.process_bank_statement(storage_path=storage_path, mime_type=mime_type)
        logger.info(f"[process/bank] Extracted {len(result.get('transactions', []))} transactions, {len(result.get('daily_balances', []))} daily balances")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error processing bank statement")
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8001)
