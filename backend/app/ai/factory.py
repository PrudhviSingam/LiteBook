from typing import Optional
from app.core.config import settings
from app.ai.base import BaseAIProvider
from app.ai.providers.mock_provider import MockAIProvider
from app.ai.providers.groq_provider import GroqAIProvider
from app.ai.providers.sarvam_provider import SarvamAIProvider


def get_ai_provider(provider_name: Optional[str] = None) -> BaseAIProvider:
    """Factory function to resolve and instantiate configured AI provider."""
    provider_type = (provider_name or settings.AI_PROVIDER).lower().strip()

    if provider_type == "sarvam" or (provider_type != "mock" and bool(settings.SARVAM_API_KEY)):
        return SarvamAIProvider(
            api_key=settings.SARVAM_API_KEY,
            model_name=settings.SARVAM_CHAT_MODEL,
        )

    if provider_type == "groq" and settings.AI_API_KEY:
        return GroqAIProvider(api_key=settings.AI_API_KEY, model_name=settings.AI_MODEL_NAME)

    if provider_type == "mock":
        return MockAIProvider()

    # Fallback to safe mock provider
    return MockAIProvider()
