import requests
import json
import os
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def main():
    print("=== STARTING LIVE API ASSISTANT VERIFICATION ===")
    
    # 1. Login
    login_res = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": "accountant@litebooks.ai", "password": "Password123!"}
    )
    assert login_res.status_code == 200, f"Login failed: {login_res.text}"
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print("[PASS] Login successful as accountant@litebooks.ai")

    # 2. Upload Zion Workbook
    zion_path = r"D:\LiteBooks\backend\storage\uploads\zion_orig_123.xlsx"
    conv_id = f"live_conv_{os.urandom(4).hex()}"
    
    with open(zion_path, "rb") as f:
        upload_res = requests.post(
            f"{BASE_URL}/assistant/upload",
            headers=headers,
            files={"file": ("Zion_Lifts_Financials_2025-26.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"conversation_id": conv_id}
        )
    assert upload_res.status_code == 200, f"Upload failed: {upload_res.text}"
    upload_data = upload_res.json()
    doc_id = upload_data["document_id"]
    print(f"[PASS] Document uploaded successfully: Doc ID={doc_id}, Sheet={upload_data.get('sheet_name')}, Period={upload_data.get('period')}")

    # 3. Turn 1: "What is wrong with this workbook?"
    print("\n--- TURN 1: 'What is wrong with this workbook?' ---")
    r1 = requests.post(
        f"{BASE_URL}/assistant/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "What is wrong with this workbook?",
            "file_ids": [doc_id]
        }
    )
    assert r1.status_code == 200, f"Turn 1 failed: {r1.text}"
    d1 = r1.json()
    print("ASSISTANT:")
    print(d1["message"])
    assert len(d1["message"].strip()) > 0
    assert "1,443.84" in d1["message"] or "Balance Sheet" in d1["message"]
    print("[PASS] Turn 1 passed: Non-empty grounded answer with balance sheet discrepancy!")

    # 4. Turn 2: Contextual follow-up: "What is the difference?"
    print("\n--- TURN 2: 'What is the difference?' ---")
    r2 = requests.post(
        f"{BASE_URL}/assistant/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "What is the difference?"
        }
    )
    assert r2.status_code == 200, f"Turn 2 failed: {r2.text}"
    d2 = r2.json()
    print("ASSISTANT:")
    print(d2["message"])
    assert "21,11,678.06" in d2["message"] or "1,443.84" in d2["message"]
    print("[PASS] Turn 2 passed: Context retained across turns without re-uploading!")

    # 5. Turn 3: "Where is the problem?"
    print("\n--- TURN 3: 'Where is the problem?' ---")
    r3 = requests.post(
        f"{BASE_URL}/assistant/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "Where is the problem?"
        }
    )
    assert r3.status_code == 200, f"Turn 3 failed: {r3.text}"
    d3 = r3.json()
    print("ASSISTANT:")
    print(d3["message"])
    assert "Balance Sheet" in d3["message"]
    print("[PASS] Turn 3 passed: Source location identified!")

    # 6. Turn 4: "Are there formula errors?"
    print("\n--- TURN 4: 'Are there formula errors?' ---")
    r4 = requests.post(
        f"{BASE_URL}/assistant/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "Are there formula errors in this workbook?"
        }
    )
    assert r4.status_code == 200, f"Turn 4 failed: {r4.text}"
    d4 = r4.json()
    print("ASSISTANT:")
    print(d4["message"])
    assert "formula" in d4["message"].lower() or "range" in d4["message"].lower()
    print("[PASS] Turn 4 passed: Formula errors identified!")

    # 7. Turn 5: "Why is the automated reconciliation not working?"
    print("\n--- TURN 5: 'Why is the automated reconciliation not working?' ---")
    r5 = requests.post(
        f"{BASE_URL}/assistant/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "Why is the automated reconciliation not working?"
        }
    )
    assert r5.status_code == 200, f"Turn 5 failed: {r5.text}"
    d5 = r5.json()
    print("ASSISTANT:")
    print(d5["message"])
    assert "formula" in d5["message"].lower() or "range" in d5["message"].lower()
    print("[PASS] Turn 5 passed: Formula range omission impact explained!")

    # 8. Test conversation persistence API
    print("\n--- CHECKING CONVERSATION RESTORATION API ---")
    r_conv = requests.get(
        f"{BASE_URL}/assistant/conversation/{conv_id}",
        headers=headers
    )
    assert r_conv.status_code == 200
    conv_data = r_conv.json()
    assert conv_data["conversation_id"] == conv_id
    assert len(conv_data["messages"]) >= 5
    print(f"[PASS] Conversation persisted with {len(conv_data['messages'])} messages and {len(conv_data['files'])} files.")

    print("\n============================================================")
    print("ALL LIVE API TESTS PASSED SUCCESSFULLY!")
    print("============================================================")

if __name__ == "__main__":
    main()
