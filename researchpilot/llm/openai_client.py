from openai import OpenAI

from researchpilot.config import AppConfig, get_config


def _resolve_llm_settings(config: AppConfig) -> tuple[str, str | None, str]:
    if config.llm_provider == "deepseek":
        api_key = (config.deepseek_api_key or "").strip()
        if not api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is missing. Please set it in your environment or .env file."
            )
        return api_key, config.deepseek_base_url.strip(), config.deepseek_model

    if config.llm_provider == "openai":
        api_key = (config.openai_api_key or "").strip()
        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is missing. Please set it in your environment or .env file."
            )
        base_url = config.openai_base_url.strip() if config.openai_base_url else None
        return api_key, base_url, config.openai_model

    raise RuntimeError(
        f"Unsupported LLM_PROVIDER: {config.llm_provider}. Expected 'openai' or 'deepseek'."
    )


def chat_completion(
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    config = get_config()
    api_key, base_url, model = _resolve_llm_settings(config)

    if base_url:
        client = OpenAI(api_key=api_key, base_url=base_url)
    else:
        client = OpenAI(api_key=api_key)

    request_kwargs = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }
    if max_tokens is not None:
        request_kwargs["max_tokens"] = max_tokens

    resp = client.chat.completions.create(**request_kwargs)
    content = resp.choices[0].message.content
    if content is None:
        return ""
    return content
