from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class BaseAIProvider(ABC):
    """Abstract Base Class for Finance AI provider implementations.

    Decouples business modules from specific AI vendors (Gemini, OpenAI, Anthropic, Local).
    """

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns provider identifier name."""
        pass

    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generates AI assistant explanation or conversational response."""
        pass

    @abstractmethod
    async def extract_document_data(
        self,
        file_path: str,
        document_type: str,
        instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Extracts structured data from uploaded financial documents (invoices, statements, forms)."""
        pass

    @abstractmethod
    async def explain_reconciliation_discrepancy(
        self,
        entry_a: Dict[str, Any],
        entry_b: Dict[str, Any],
    ) -> str:
        """Provides human-readable accounting analysis of reconciliation differences."""
        pass
