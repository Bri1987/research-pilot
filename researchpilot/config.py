import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class AppConfig:
    llm_provider: str
    openai_api_key: str | None
    openai_base_url: str | None
    openai_model: str
    deepseek_api_key: str | None
    deepseek_base_url: str
    deepseek_model: str


def get_config() -> AppConfig:
    load_dotenv()

    return AppConfig(
        llm_provider=os.getenv("LLM_PROVIDER", "openai").strip().lower(),
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY"),
        deepseek_base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
    )
