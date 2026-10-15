import asyncio
from app.ai.factory import get_ai_provider

async def test_live_sarvam():
    print("Testing live Sarvam AI Provider...")
    provider = get_ai_provider()
    print(f"Provider name: {provider.provider_name}")
    print(f"Model name: {provider.model_name}")
    assert provider.provider_name == "sarvam"
    assert provider.model_name == "sarvam-105b"

    prompt = "Explain what a trial balance is in simple accounting terms."
    system_prompt = (
        "You are LiteBooks.ai Accounting Intelligence Assistant, an expert Indian accounting, "
        "taxation, and financial document intelligence assistant.\n"
        "Be concise, clear, and professional. Format in markdown."
    )

    try:
        response = await provider.generate_response(prompt=prompt, system_prompt=system_prompt)
        import sys
        sys.stdout.reconfigure(encoding='utf-8')
        print(response)
        print("--- End Response ---\n")
        assert len(response.strip()) > 20
        print("[SUCCESS] Live Sarvam 105b request completed successfully!")
    except Exception as e:
        print(f"[ERROR] Live Sarvam request failed: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_live_sarvam())
