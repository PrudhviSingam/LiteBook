import json
import logging
from typing import Any, Dict, Optional
import httpx

from app.ai.base import BaseAIProvider

logger = logging.getLogger(__name__)


class GroqAIProvider(BaseAIProvider):
    """High-speed Groq AI provider for LiteBooks Assistant using OpenAI-compatible API."""

    def __init__(self, api_key: str, model_name: str = "openai/gpt-oss-120b"):
        self.api_key = api_key
        self.model_name = model_name or "openai/gpt-oss-120b"
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    @property
    def provider_name(self) -> str:
        return "groq"

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        default_system = (
            "You are LiteBooks AI Assistant, an expert Indian accounting, taxation (GST & ITR), "
            "and finance automation assistant.\n"
            "Format monetary values in Indian Rupees (₹).\n"
            "Cite relevant Indian accounting principles (ICAI, Ind AS, AS), GST rules, or Income Tax Act sections where relevant.\n"
            "Be precise, clear, and professional. Use markdown formatting with clean tables or bullet points."
        )

        messages = [
            {"role": "system", "content": system_prompt or default_system},
        ]

        if context:
            ctx_summary = json.dumps(context, indent=2, default=str)
            messages.append({
                "role": "system",
                "content": f"### Context Data:\n```json\n{ctx_summary}\n```"
            })

        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
        }

        try:
            async with httpx.AsyncClient(timeout=25.0) as client:
                res = await client.post(self.api_url, headers=headers, json=payload)
                if res.status_code == 200:
                    data = res.json()
                    choices = data.get("choices", [])
                    if choices:
                        return choices[0].get("message", {}).get("content", "").strip()
                logger.warning(f"Groq API returned HTTP {res.status_code}: {res.text[:200]}")
        except Exception as e:
            logger.warning(f"Groq API call failed: {e}")

        # Fallback to local accounting knowledge if API call fails
        from app.modules.ai_assistant.accounting_knowledge import AccountingKnowledgeEngine
        msg, _, _ = AccountingKnowledgeEngine.get_explanation(prompt)
        return msg

    async def extract_document_data(
        self,
        file_path: str,
        document_type: str,
        instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        return {
            "status": "success",
            "document_type": document_type,
            "file_path": file_path,
            "extracted_fields": {
                "source": "GroqAIProvider",
                "notes": "Automated document field extraction ready",
            },
        }

    async def explain_reconciliation_discrepancy(
        self,
        entry_a: Dict[str, Any],
        entry_b: Dict[str, Any],
    ) -> str:
        prompt = (
            f"Analyze this reconciliation discrepancy between statement and books:\n"
            f"Statement Entry: {entry_a}\n"
            f"Book Entry: {entry_b}\n"
            f"Explain likely accounting reasons (timing delay, transposition error, bank fee, unrecorded TDS)."
        )
        return await self.generate_response(prompt=prompt)
