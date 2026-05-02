import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class AppConfig:
    openai_api_key: str | None
    openai_base_url: str | None
    openai_model: str


def get_config() -> AppConfig:
    load_dotenv()

    return AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_base_url=os.getenv("OPENAI_BASE_URL"),
        openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
    )
