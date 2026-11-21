from querya.config import Settings
from querya.llm.anthropic_client import AnthropicClient
from querya.llm.base import LLMClient
from querya.llm.openai_client import OpenAICompatibleClient


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.llm_provider == "anthropic":
        key = settings.anthropic_api_key.get_secret_value() if settings.anthropic_api_key else None
        return AnthropicClient(
            model=settings.model_name,
            max_tokens=settings.llm_max_tokens,
            timeout_s=settings.llm_timeout_s,
            api_key=key,
            show_thinking=settings.anthropic_show_thinking,
        )
    return OpenAICompatibleClient(
        model=settings.model_name,
        base_url=settings.openai_base_url,
        api_key=settings.openai_api_key.get_secret_value(),
        max_tokens=settings.llm_max_tokens,
        timeout_s=settings.llm_timeout_s,
        temperature=settings.llm_temperature,
    )
