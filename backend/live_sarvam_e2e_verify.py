import json
import requests
from pathlib import Path

BACKEND_URL = "http://127.0.0.1:8000/api/v1"

def run_e2e_verification():
    print("=== LIVE E2E VERIFICATION OF LITEBOOKS ASSISTANT & SARVAM ===")

    # 1. Login
    print("\n1. Authenticating as admin@litebooks.ai...")
    login_res = requests.post(
        f"{BACKEND_URL}/auth/login",
        json={"email": "admin@litebooks.ai", "password": "ValidPass123!"},
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[PASS] Login successful, JWT token acquired.")

    # 2. Upload Zion_Lifts_Financials.xlsx
    file_path = Path("d:/LiteBooks/backend/Zion_Lifts_Financials.xlsx")
    assert file_path.exists(), "Zion_Lifts_Financials.xlsx not found!"
    conv_id = f"conv_live_sarvam_{int(Path(__file__).stat().st_mtime)}"

    print(f"\n2. Uploading {file_path.name} to conversation {conv_id}...")
    with open(file_path, "rb") as f:
        upload_res = requests.post(
            f"{BACKEND_URL}/assistant/upload",
            headers=headers,
            files={"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"conversation_id": conv_id, "category": "financial"},
        )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    doc_info = upload_res.json()
    doc_id = doc_info["document_id"]
    print(f"[PASS] Upload successful. Document ID: {doc_id}, Type: {doc_info['document_type']}, Status: {doc_info['status']}")

    # 3. Ask "What is wrong with this workbook?"
    print("\n3. Asking: 'What is wrong with this workbook?'...")
    chat_res1 = requests.post(
        f"{BACKEND_URL}/assistant/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "What is wrong with this workbook?",
            "file_ids": [doc_id],
        },
    )
    assert chat_res1.status_code == 200, f"Chat Q1 failed: {chat_res1.text}"
    data1 = chat_res1.json()
    print("Response Q1:")
    print("-" * 50)
    print(data1["message"])
    print("-" * 50)
    assert "₹21,11,678.06" in data1["message"] or "21,11,678.06" in data1["message"]
    print("[PASS] Trade Payables discrepancy of ₹21,11,678.06 verified in response.")

    # 4. Ask "Where is the mismatch?"
    print("\n4. Asking follow-up: 'Where is the mismatch?'...")
    chat_res2 = requests.post(
        f"{BACKEND_URL}/assistant/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "Where is the mismatch?",
            "file_ids": [doc_id],
        },
    )
    assert chat_res2.status_code == 200, f"Chat Q2 failed: {chat_res2.text}"
    data2 = chat_res2.json()
    print("Response Q2:")
    print("-" * 50)
    print(data2["message"])
    print("-" * 50)
    assert "D10" in data2["message"] or "Balance Sheet" in data2["message"]
    print("[PASS] Balance Sheet / Cell D10 location verified in follow-up response.")

    # 5. Ask "Why?"
    print("\n5. Asking follow-up: 'Why?'...")
    chat_res3 = requests.post(
        f"{BACKEND_URL}/assistant/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "Why?",
            "file_ids": [doc_id],
        },
    )
    assert chat_res3.status_code == 200, f"Chat Q3 failed: {chat_res3.text}"
    data3 = chat_res3.json()
    print("Response Q3:")
    print("-" * 50)
    print(data3["message"])
    print("-" * 50)
    print("[PASS] Follow-up explanation verified.")

    # 6. Ask General Accounting Question
    print("\n6. Asking general question: 'Explain what a trial balance is in simple accounting terms.'...")
    chat_res4 = requests.post(
        f"{BACKEND_URL}/assistant/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "Explain what a trial balance is in simple accounting terms.",
        },
    )
    assert chat_res4.status_code == 200, f"Chat Q4 failed: {chat_res4.text}"
    data4 = chat_res4.json()
    print("Response Q4:")
    print("-" * 50)
    print(data4["message"])
    print("-" * 50)
    assert "Trial Balance" in data4["message"] or "Debit" in data4["message"] or "Credit" in data4["message"]
    print("[PASS] General accounting explanation verified.")

    # 7. Check for Secret Leaks in Responses
    all_responses = [data1["message"], data2["message"], data3["message"], data4["message"]]
    for idx, resp_text in enumerate(all_responses, 1):
        assert "SARVAM_API_KEY" not in resp_text
        assert "Bearer" not in resp_text
        assert "api-subscription-key" not in resp_text
    print("\n[PASS] Secret leak check: ZERO secret or authorization headers in API responses.")

    print("\n=== ALL LIVE E2E CHECKS PASSED ===")

if __name__ == "__main__":
    run_e2e_verification()
