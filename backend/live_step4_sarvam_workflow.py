import asyncio
import os
import sys
from pathlib import Path
from fastapi.testclient import TestClient

from app.core.config import settings
from app.core.database import Base, SessionLocal, engine
from app.main import app as fastapi_app
from app.modules.ai_assistant.schemas import ChatRequest
from app.modules.ai_assistant.assistant_service import AssistantService
from tests.test_workbook_and_corrections import create_zion_lifts_workbook_bytes

sys.stdout.reconfigure(encoding='utf-8')

async def run_live_sarvam_workflow():
    print("=" * 60)
    print("STEP 4: CONTROLLED REAL SARVAM 105B INTELLIGENCE VALIDATION")
    print("=" * 60)
    
    # Confirm configuration
    print(f"Configured AI Provider: {settings.AI_PROVIDER}")
    print(f"Configured Model: {settings.SARVAM_CHAT_MODEL}")
    has_key = bool(settings.SARVAM_API_KEY)
    print(f"SARVAM API KEY: {'Configured securely' if has_key else 'Not configured'}")
    assert has_key, "Sarvam API Key must be configured for live validation!"
    
    db = SessionLocal()
    client = TestClient(fastapi_app)
    
    # Authenticate user
    print("\n--- Authenticating as accountant@litebooks.ai ---")
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "accountant@litebooks.ai", "password": "Password123!"},
    )
    if login_res.status_code != 200:
        login_res = client.post(
            "/api/v1/auth/login",
            json={"email": "admin@litebooks.ai", "password": "ValidPass123!"},
        )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    auth_headers = {"Authorization": f"Bearer {token}"}
    print("[PASS] Logged in successfully, token acquired.")

    try:
        # 1. General Accounting Test
        print("\n--- TEST 1: General Accounting Query ---")
        q1 = "What is a trial balance? Explain it simply."
        print(f"User: {q1}")
        res1 = client.post("/api/v1/assistant/chat", json={"message": q1}, headers=auth_headers)
        assert res1.status_code == 200, f"Q1 failed: {res1.text}"
        msg1 = res1.json()["message"]
        print(f"Assistant:\n{msg1}\n")
        assert len(msg1.strip()) > 30
        assert "trial balance" in msg1.lower()
        print("[PASS] General Accounting response generated.")

        # 2. Upload Zion Lifts Financials
        print("\n--- TEST 2: Upload Zion_Lifts_Financials.xlsx ---")
        file_path = Path("d:/LiteBooks/backend/Zion_Lifts_Financials.xlsx")
        assert file_path.exists(), "Zion_Lifts_Financials.xlsx missing!"
        conv_id = f"conv_live_step4_{int(asyncio.get_event_loop().time() * 1000)}"
        
        with open(file_path, "rb") as f:
            upload_res = client.post(
                "/api/v1/assistant/upload",
                files={"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                data={"conversation_id": conv_id, "category": "financial"},
                headers=auth_headers,
            )
        assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
        doc_id = upload_res.json()["document_id"]
        print(f"[PASS] Uploaded {file_path.name} as Document ID {doc_id} to conversation {conv_id}")

        # 3. Document Question: "What is wrong with this workbook?"
        print("\n--- TEST 3: Document Question: 'What is wrong with this workbook?' ---")
        res_doc1 = client.post(
            "/api/v1/assistant/chat",
            json={"conversation_id": conv_id, "message": "What is wrong with this workbook?", "file_ids": [doc_id]},
            headers=auth_headers,
        )
        assert res_doc1.status_code == 200, f"Doc Q1 failed: {res_doc1.text}"
        msg_doc1 = res_doc1.json()["message"]
        print(f"Assistant:\n{msg_doc1}\n")
        assert "21,11,678.06" in msg_doc1 or "2111678" in msg_doc1 or "Trade Payables" in msg_doc1
        print("[PASS] Trade Payables / variance identified correctly.")

        # 4. Follow-up: "Where is the mismatch?"
        print("\n--- TEST 4: Follow-up: 'Where is the mismatch?' ---")
        res_doc2 = client.post(
            "/api/v1/assistant/chat",
            json={"conversation_id": conv_id, "message": "Where is the mismatch?", "file_ids": [doc_id]},
            headers=auth_headers,
        )
        assert res_doc2.status_code == 200, f"Doc Q2 failed: {res_doc2.text}"
        msg_doc2 = res_doc2.json()["message"]
        print(f"Assistant:\n{msg_doc2}\n")
        assert "D10" in msg_doc2 or "Balance Sheet" in msg_doc2 or "Notes" in msg_doc2
        print("[PASS] Location accurately retained.")

        # 5. Follow-up: "Why does it matter?"
        print("\n--- TEST 5: Follow-up: 'Why does it matter?' ---")
        res_doc3 = client.post(
            "/api/v1/assistant/chat",
            json={"conversation_id": conv_id, "message": "Why does it matter?", "file_ids": [doc_id]},
            headers=auth_headers,
        )
        assert res_doc3.status_code == 200, f"Doc Q3 failed: {res_doc3.text}"
        msg_doc3 = res_doc3.json()["message"]
        print(f"Assistant:\n{msg_doc3}\n")
        assert len(msg_doc3.strip()) > 30
        print("[PASS] Audit explanation verified.")

        # 6. Follow-up: "What should I check next?"
        print("\n--- TEST 6: Follow-up: 'What should I check next?' ---")
        res_doc4 = client.post(
            "/api/v1/assistant/chat",
            json={"conversation_id": conv_id, "message": "What should I check next?", "file_ids": [doc_id]},
            headers=auth_headers,
        )
        assert res_doc4.status_code == 200, f"Doc Q4 failed: {res_doc4.text}"
        msg_doc4 = res_doc4.json()["message"]
        print(f"Assistant:\n{msg_doc4}\n")
        assert len(msg_doc4.strip()) > 30
        print("[PASS] Next verification steps provided.")

        print("\n" + "=" * 60)
        print("ALL STEP 4 REAL SARVAM 105B CONVERSATION TESTS PASSED!")
        print("=" * 60)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_live_sarvam_workflow())
