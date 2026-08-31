from typing import Dict, Any
from finside.providers.base import BaseProvider
from finside.providers.gemini_provider import GeminiProvider
from finside.providers.openai_provider import OpenAIProvider
from finside.providers.anthropic_provider import AnthropicProvider
from finside.providers.huggingface_provider import HuggingFaceProvider
from finside.providers.mock_provider import MockProvider


class ProviderFactory:
    """SOLID Factory & Open/Closed Principle: LLM Sağlayıcı Fabrikası."""

    _providers = {
        "gemini": GeminiProvider,
        "openai": OpenAIProvider,
        "anthropic": AnthropicProvider,
        "huggingface": HuggingFaceProvider,
        "mock": MockProvider
    }

    @classmethod
    def create_provider(cls, provider_name: str, model_config: Dict[str, Any], system_prompt: str, api_key: str) -> BaseProvider:
        provider_cls = cls._providers.get(provider_name.lower(), MockProvider)
        return provider_cls(model_config=model_config, system_prompt=system_prompt, api_key=api_key)
