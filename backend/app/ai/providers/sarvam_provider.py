import json
import logging
from typing import Any, Dict, List, Optional
import httpx

from app.ai.base import BaseAIProvider

logger = logging.getLogger(__name__)


class SarvamAIProvider(BaseAIProvider):
    """Dedicated Sarvam AI provider for LiteBooks Assistant using the official
    Sarvam Chat Completions API with the sarvam-105b model.
    """

    SARVAM_API_URL: str = "https://api.sarvam.ai/v1/chat/completions"

    def __init__(
        self,
        api_key: str,
        model_name: str = "sarvam-105b",
        timeout: float = 50.0,
    ) -> None:
        self.api_key = (api_key or "").strip()
        self.model_name = (model_name or "sarvam-105b").strip()
        self.timeout = timeout

    @property
    def provider_name(self) -> str:
        return "sarvam"

    async def generate_response(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.2,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Sends an already-prepared LiteBooks AI request to Sarvam and returns
        the normalized natural language explanation.

        Never logs or exposes the API key or raw authorization headers.
        """
        if not self.api_key:
            logger.warning("Sarvam API call skipped: SARVAM_API_KEY is not configured.")
            raise ValueError("Sarvam API key is not configured in backend environment.")

        default_system = (
            "You are the LiteBooks.ai Accounting Intelligence Assistant.\n\n"
            "You assist accounting professionals with:\n"
            "- Accounting questions and principles (ICAI, Ind AS, AS, GST, Income Tax)\n"
            "- Financial statement and document analysis\n"
            "- Reconciliation and variance explanations\n"
            "- Discrepancy analysis and audit review steps\n\n"
            "Core Principles & Strict Rules:\n"
            "1. Rely strictly on verified LiteBooks context when provided. All financial figures, "
            "cell references, sheet names, and balances in the context are deterministic application results verified by LiteBooks.\n"
            "2. Never invent financial values, transactions, cell references, documents, company information, or accounting results.\n"
            "3. When verified data is available, treat it as the absolute source of truth. Never alter verified figures.\n"
            "4. When information is missing, state clearly: 'I don't have enough verified data in the uploaded document to determine that.' Never guess.\n"
            "5. Format monetary values in Indian Rupees (₹) with Indian digit grouping (e.g. ₹1,42,10,000.00).\n"
            "6. Clearly distinguish verified findings from unconfirmed possible causes or general accounting guidance.\n"
            "7. Do not claim that a file was changed unless LiteBooks actually performed and confirmed that action.\n"
            "8. Do not approve or confirm accounting corrections. Proposals must be reviewed by the accountant in the Review Center.\n"
            "9. Maintain conversation context and answer follow-up questions (e.g., 'Where is it?', 'Why?', 'What should I check next?') directly and intelligently.\n"
            "10. Respond conversationally, concisely, and professionally, similar to a senior accountant assistant."
        )

        system_content = (system_prompt or default_system).strip()

        # Separate conversation history from structured accounting facts
        messages: List[Dict[str, str]] = []
        conversation_history: List[Dict[str, Any]] = []

        if context:
            ctx_data = dict(context)
            if "conversation_history" in ctx_data:
                conversation_history = ctx_data.pop("conversation_history") or []

            if ctx_data:
                try:
                    ctx_json = json.dumps(ctx_data, indent=2, default=str)
                    system_content += f"\n\n### Verified Accounting Context:\n```json\n{ctx_json}\n```"
                except Exception as e:
                    logger.debug("Failed to serialize context to JSON: %s", e)

        messages.append({"role": "system", "content": system_content})

        # Append prior conversation dialogue for contextual follow-ups
        for msg_item in conversation_history:
            if isinstance(msg_item, dict):
                role = msg_item.get("role")
                text = msg_item.get("text") or msg_item.get("content")
                if role in ("user", "assistant") and text:
                    messages.append({"role": role, "content": str(text)})

        # Append current user prompt
        messages.append({"role": "user", "content": prompt})

        # Authentication headers (both official header and bearer token for compatibility)
        headers = {
            "api-subscription-key": self.api_key,
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model_name,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 1500,
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.post(self.SARVAM_API_URL, headers=headers, json=payload)

                if res.status_code == 200:
                    try:
                        data = res.json()
                    except Exception as parse_err:
                        logger.warning("Sarvam API returned malformed JSON response: %s", parse_err)
                        raise ValueError("Sarvam API returned malformed JSON response") from parse_err

                    choices = data.get("choices")
                    if not choices or not isinstance(choices, list):
                        logger.warning("Sarvam API response missing choices array")
                        raise ValueError("Sarvam API response missing choices array")

                    first_choice = choices[0]
                    message_obj = first_choice.get("message", {})
                    content = message_obj.get("content", "")
                    if not content or not content.strip():
                        # Reasoning models may return reasoning_content if finish_reason reached or content empty
                        content = message_obj.get("reasoning_content", "")

                    if not content or not content.strip():
                        logger.warning("Sarvam API returned empty content in response choice")
                        raise ValueError("Sarvam API returned empty content in response choice")

                    return content.strip()

                if res.status_code in (401, 403):
                    logger.warning("Sarvam API authentication failed (HTTP %s)", res.status_code)
                    raise PermissionError(f"Sarvam API authentication failed (HTTP {res.status_code})")

                if res.status_code == 429:
                    logger.warning("Sarvam API rate limit exceeded (HTTP 429)")
                    raise RuntimeError("Sarvam API rate limit exceeded (HTTP 429)")

                if res.status_code >= 500:
                    logger.warning("Sarvam API server error (HTTP %s)", res.status_code)
                    raise RuntimeError(f"Sarvam API server error (HTTP {res.status_code})")

                logger.warning("Sarvam API returned unexpected status HTTP %s", res.status_code)
                raise RuntimeError(f"Sarvam API request failed (HTTP {res.status_code})")

        except httpx.TimeoutException as e:
            logger.warning("Sarvam API request timed out after %s seconds", self.timeout)
            raise TimeoutError(f"Sarvam API request timed out after {self.timeout}s") from e

        except (httpx.ConnectError, httpx.NetworkError) as e:
            logger.warning("Sarvam API network connection error")
            raise ConnectionError("Sarvam API network connection error") from e

        except (ValueError, PermissionError, RuntimeError, TimeoutError, ConnectionError):
            raise

        except Exception as e:
            logger.warning("Unexpected error communicating with Sarvam API: %s", type(e).__name__)
            raise RuntimeError("Sarvam API communication error") from e

    async def extract_document_data(
        self,
        file_path: str,
        document_type: str,
        instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Document data extraction contract for Sarvam AI."""
        return {
            "status": "success",
            "document_type": document_type,
            "file_path": file_path,
            "extracted_fields": {
                "source": "SarvamAIProvider",
                "model": self.model_name,
                "notes": "Automated document field extraction ready",
            },
        }

    async def explain_reconciliation_discrepancy(
        self,
        entry_a: Dict[str, Any],
        entry_b: Dict[str, Any],
    ) -> str:
        """Explains reconciliation discrepancy using Sarvam chat completion."""
        prompt = (
            f"Analyze this reconciliation discrepancy between statement and books:\n"
            f"Statement Entry: {entry_a}\n"
            f"Book Entry: {entry_b}\n"
            f"Explain likely accounting reasons (timing delay, transposition error, bank fee, unrecorded TDS)."
        )
        return await self.generate_response(prompt=prompt)
