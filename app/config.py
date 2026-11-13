from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    a11y_api_url: str = "http://localhost:8000"
    groq_api_key: str = ""
    llm_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "llama-3.3-70b-versatile"
    llm_input_usd_per_mtok: float = 0.59     # cost estimate for the dashboard; override in .env
    llm_output_usd_per_mtok: float = 0.79
    db_path: str = "data/testing_agent.db"
    embed_model: str = "BAAI/bge-small-en-v1.5"
    dense_enabled: bool = True


settings = Settings()
