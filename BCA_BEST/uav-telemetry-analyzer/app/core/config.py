import os
from pydantic_settings import BaseSettings
from pydantic_settings import SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "UAV-Telemetry-Analyzer"
    # AI API keys (OpenAI or local LLM via any API)
    AI_API_KEY: str = os.getenv("AI_API_KEY", "your-key-here")
    AI_MODEL: str = "gpt-4-turbo"
    # Docker/Server settings
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
settings = Settings()
