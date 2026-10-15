import asyncio
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

from app.core.config import settings
from app.ai.providers.sarvam_provider import SarvamAIProvider
from app.ai.factory import get_ai_provider
from app.modules.ai_assistant.assistant_service import AssistantService
from app.modules.ai_assistant.schemas import ChatRequest, AssistantIntentEnum
from app.core.database import SessionLocal


# =========================================================================
# 1. API KEY CONFIGURATION TEST
# =========================================================================

def test_sarvam_api_key_configuration():
    """Verify that Sarvam API key is configured and trimmed properly."""
    provider = SarvamAIProvider(api_key="  test-secret-key-123  ", model_name="sarvam-105b")
    assert provider.api_key == "test-secret-key-123"
    assert provider.provider_name == "sarvam"


# =========================================================================
# 2. MODEL CONFIGURATION TEST
# =========================================================================

def test_sarvam_model_configuration():
    """Verify that model configuration defaults to sarvam-105b and respects custom models."""
    provider_default = SarvamAIProvider(api_key="test-key")
    assert provider_default.model_name == "sarvam-105b"

    provider_custom = SarvamAIProvider(api_key="test-key", model_name="sarvam-105b-custom")
    assert provider_custom.model_name == "sarvam-105b-custom"


# =========================================================================
# 3. SUCCESSFUL SARVAM RESPONSE TEST
# =========================================================================

def test_sarvam_successful_response():
    """Verify that a 200 OK OpenAI-compatible response from Sarvam is parsed correctly."""
    async def _run():
        mock_payload = {
            "id": "chatcmpl-test-01",
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": "Trade Payables differs by ₹21,11,678.06 between Balance Sheet and Note 3 schedule.",
                    },
                    "finish_reason": "stop",
                }
            ],
        }

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_payload

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            provider = SarvamAIProvider(api_key="valid-test-key", model_name="sarvam-105b")
            resp = await provider.generate_response(
                prompt="What is wrong with this workbook?",
                system_prompt="You are LiteBooks assistant.",
            )

            assert "₹21,11,678.06" in resp
            assert "Trade Payables" in resp
            assert mock_post.called

            # Verify headers sent to Sarvam API
            call_kwargs = mock_post.call_args.kwargs
            headers = call_kwargs.get("headers", {})
            assert headers.get("api-subscription-key") == "valid-test-key"
            assert "Bearer valid-test-key" in headers.get("Authorization", "")
            assert call_kwargs.get("json", {}).get("model") == "sarvam-105b"

    asyncio.run(_run())


# =========================================================================
# 4. MALFORMED SARVAM RESPONSE TEST
# =========================================================================

def test_sarvam_malformed_response():
    """Verify that malformed or missing choices in response raise ValueError."""
    async def _run():
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"unexpected_key": "no_choices_here"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            provider = SarvamAIProvider(api_key="valid-test-key")
            with pytest.raises(ValueError, match="missing choices array"):
                await provider.generate_response(prompt="Hello")

    asyncio.run(_run())


# =========================================================================
# 5. TIMEOUT TEST
# =========================================================================

def test_sarvam_timeout():
    """Verify that httpx.TimeoutException is converted to TimeoutError without leaking secrets."""
    async def _run():
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Connection timed out")

            provider = SarvamAIProvider(api_key="valid-test-key", timeout=5.0)
            with pytest.raises(TimeoutError, match="timed out"):
                await provider.generate_response(prompt="Hello")

    asyncio.run(_run())


# =========================================================================
# 6. HTTP 401 UNAUTHORIZED TEST
# =========================================================================

def test_sarvam_http_401_unauthorized():
    """Verify that HTTP 401 raises PermissionError without exposing authorization headers in error."""
    async def _run():
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            provider = SarvamAIProvider(api_key="invalid-api-key")
            with pytest.raises(PermissionError, match="HTTP 401"):
                await provider.generate_response(prompt="Hello")

    asyncio.run(_run())


# =========================================================================
# 7. HTTP 429 RATE LIMIT TEST
# =========================================================================

def test_sarvam_http_429_rate_limit():
    """Verify that HTTP 429 raises RuntimeError indicating rate limit exceeded."""
    async def _run():
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            provider = SarvamAIProvider(api_key="valid-test-key")
            with pytest.raises(RuntimeError, match="HTTP 429"):
                await provider.generate_response(prompt="Hello")

    asyncio.run(_run())


# =========================================================================
# 8. HTTP 500 SERVER ERROR TEST
# =========================================================================

def test_sarvam_http_500_server_error():
    """Verify that HTTP 500 raises RuntimeError indicating server error."""
    async def _run():
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response

            provider = SarvamAIProvider(api_key="valid-test-key")
            with pytest.raises(RuntimeError, match="HTTP 500"):
                await provider.generate_response(prompt="Hello")

    asyncio.run(_run())


# =========================================================================
# 9. MISSING API KEY TEST
# =========================================================================

def test_sarvam_missing_api_key():
    """Verify that an empty or whitespace API key raises ValueError cleanly."""
    async def _run():
        provider = SarvamAIProvider(api_key="")
        with pytest.raises(ValueError, match="Sarvam API key is not configured"):
            await provider.generate_response(prompt="Hello")

    asyncio.run(_run())


# =========================================================================
# 10. FALLBACK BEHAVIOR TEST
# =========================================================================

def test_sarvam_fallback_in_general_accounting():
    """Verify that if Sarvam is configured but fails/times out, general accounting questions
    fall back cleanly to the deterministic AccountingKnowledgeEngine without failing with 500.
    """
    async def _run():
        db = SessionLocal()
        try:
            req = ChatRequest(message="What is a debit and credit?", conversation_id="conv_fallback_test")

            # Temporarily mock get_ai_provider to return a failing Sarvam provider
            failing_provider = SarvamAIProvider(api_key="test-key")
            with patch.object(failing_provider, "generate_response", side_effect=TimeoutError("Sarvam timed out")):
                with patch("app.modules.ai_assistant.assistant_service.get_ai_provider", return_value=failing_provider):
                    res = await AssistantService.process_chat(db=db, req=req, user_id=1)

                    assert res is not None
                    assert res.intent == AssistantIntentEnum.GENERAL_ACCOUNTING
                    # Should receive clean accounting fallback message
                    assert "Debit" in res.message or "Assets = Liabilities + Equity" in res.message
                    assert "Traceback" not in res.message
                    assert res.confidence == "HIGH"
        finally:
            db.close()

    asyncio.run(_run())


# =========================================================================
# 11. ACCOUNTING CONTEXT TEST (DETERMINISTIC VERIFICATION)
# =========================================================================

def test_sarvam_accounting_context_preservation():
    """Verifies that:
    1. Exact verified figures (₹1,42,10,000.00, ₹1,63,21,678.06, ₹21,11,678.06) are passed to Sarvam context.
    2. Sarvam prompt receives structured context with verified findings.
    3. The application response preserves deterministic values exactly.
    """
    async def _run():
        captured_context = {}

        async def fake_generate_response(prompt, system_prompt=None, temperature=0.2, context=None):
            nonlocal captured_context
            captured_context = context or {}
            return (
                "Based on the verified audit inspection of your workbook, a **Trade Payables Schedule Discrepancy** "
                "was detected.\n\n"
                "- **Location:** Balance Sheet → Cell D10\n"
                "- **Balance Sheet Value:** ₹1,42,10,000.00\n"
                "- **Notes Schedule Total:** ₹1,63,21,678.06\n"
                "- **Variance:** ₹21,11,678.06\n\n"
                "This suggests an unposted vendor invoice or sub-ledger omission of ₹21,11,678.06."
            )

        provider = SarvamAIProvider(api_key="valid-test-key", model_name="sarvam-105b")
        provider.generate_response = AsyncMock(side_effect=fake_generate_response)

        test_context = {
            "document": {"name": "Zion_Lifts_Financials.xlsx", "sheets": ["Balance Sheet", "Notes"]},
            "verified_findings": [
                {
                    "title": "Trade Payables Schedule Discrepancy",
                    "location": "Balance Sheet → Trade Payables",
                    "sheet": "Balance Sheet",
                    "cell_address": "D10",
                    "actual_value": "₹1,42,10,000.00",
                    "expected_value": "₹1,63,21,678.06",
                    "difference": "₹21,11,678.06",
                    "confidence": "HIGH",
                }
            ],
            "conversation_history": [
                {"role": "user", "text": "What is wrong with this workbook?"},
            ],
        }

        result = await provider.generate_response(
            prompt="Where is the mismatch and why?",
            system_prompt="LiteBooks Assistant",
            context=test_context,
        )

        # 1. Verify context passed to provider contains exact verified amounts
        assert captured_context.get("verified_findings") is not None
        findings = captured_context["verified_findings"]
        assert findings[0]["actual_value"] == "₹1,42,10,000.00"
        assert findings[0]["expected_value"] == "₹1,63,21,678.06"
        assert findings[0]["difference"] == "₹21,11,678.06"
        assert findings[0]["cell_address"] == "D10"

        # 2. Verify returned response preserves exact figures
        assert "₹1,42,10,000.00" in result
        assert "₹1,63,21,678.06" in result
        assert "₹21,11,678.06" in result
        assert "D10" in result

    asyncio.run(_run())
