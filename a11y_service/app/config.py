"""Application settings. All model/vendor choices are configurable via environment."""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (any OpenAI-compatible endpoint; defaults target Groq)
    llm_api_key: str = ""
    groq_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_timeout_s: float = 30.0

    # Retrieval models
    embed_model: str = "BAAI/bge-small-en-v1.5"
    rerank_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    retrieval_enabled: bool = True
    sparse_top_k: int = 20
    dense_top_k: int = 20
    rerank_top_k: int = 5
    rrf_k: int = 60

    # Stores
    qdrant_url: str = ""  # empty -> embedded local mode
    qdrant_path: str = str(ROOT / "data" / "qdrant")
    qdrant_collection: str = "wcag_chunks"
    sqlite_path: str = str(ROOT / "data" / "agent.db")
    knowledge_dir: str = str(ROOT / "knowledge")

    # Limits
    max_payload_bytes: int = 2 * 1024 * 1024

    @property
    def effective_llm_key(self) -> str:
        return self.llm_api_key or self.groq_api_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
