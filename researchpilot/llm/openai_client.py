from openai import OpenAI

from researchpilot.config import get_config


def chat_completion(
    messages: list[dict],
    temperature: float = 0.2,
    max_tokens: int | None = None,
) -> str:
    config = get_config()
    api_key = (config.openai_api_key or "").strip()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Please set it in your environment or .env file."
        )

    if config.openai_base_url:
        client = OpenAI(api_key=api_key, base_url=config.openai_base_url)
    else:
        client = OpenAI(api_key=api_key)

    request_kwargs = {
        "model": config.openai_model,
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
