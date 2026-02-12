"""
Configuration for Document AI REST API Backend (Project B)
"""
from pydantic_settings import BaseSettings
import os


class Settings(BaseSettings):
    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"

    # GCP (Project B - where Document AI processors live)
    GCP_PROJECT_ID: str = ""
    DOCUMENT_AI_LOCATION: str = "us"
    DOCUMENT_AI_FORM_PROCESSOR: str = ""
    DOCUMENT_AI_BANK_STATEMENT_PROCESSOR: str = ""

    # Cloud Storage (for gs:// paths - use Project B bucket or shared bucket)
    STORAGE_BUCKET_NAME: str = ""

    # Optional: API key for authenticating callers (Project A)
    # If set, requests must include header: X-API-Key: <value>
    API_KEY: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
