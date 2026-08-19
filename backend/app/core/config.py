import os
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    # Gemini Flash — used for all LLM text generation (notes, segmentation, summaries)
    gemini_api_key_fortext: str = Field("", validation_alias="GEMINI_API_KEY_FORTEXT")
    # Gemini Imagen — used for generating educational diagrams inside notes
    gemini_api_key: str = Field("", validation_alias="GEMINI_API_KEY")
    # Fallback transcript fetcher
    supadata_api_key: str = Field("", validation_alias="SUPADATA_API_KEY")
    # Notion export (optional)
    notion_api_key: str = Field("", validation_alias="NOTION_API_KEY")
    port: int = Field(8000, validation_alias="PORT")
    host: str = Field("127.0.0.1", validation_alias="HOST")

    class Config:
        env_file = os.environ.get("ENV_FILE_PATH", ".env")
        env_file_encoding = "utf-8"
        extra = "ignore"

# Instantiate settings — imported by all services
settings = Settings()
