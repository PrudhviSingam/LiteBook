import urllib.request
import json
import requests

def test_live_servers():
    print("--- 1. Testing Frontend (http://localhost:5173) ---", flush=True)
    try:
        r = requests.get("http://localhost:5173", timeout=5)
        print("Status:", r.status_code, flush=True)
        print("Root div present:", 'id="root"' in r.text, flush=True)
        print("Vite client present:", "@vite/client" in r.text, flush=True)
        for line in r.text.splitlines():
            if "<title>" in line:
                print("HTML Title:", line.strip().encode('ascii', 'replace').decode('ascii'), flush=True)
    except Exception as e:
        print("Frontend connection error:", e, flush=True)

    print("\n--- 2. Testing Backend Root (http://127.0.0.1:8000/) ---", flush=True)
    try:
        r = requests.get("http://127.0.0.1:8000/", timeout=5)
        print("Status:", r.status_code, flush=True)
    except Exception as e:
        print("Backend connection error:", e, flush=True)

    print("\n--- 3. Testing Authentication & Protected Routes ---", flush=True)
    # Unauthorized test
    try:
        r_unauth = requests.get("http://127.0.0.1:8000/api/v1/dashboard/summary", timeout=5)
        print("Unauthorized GET /api/v1/dashboard/summary -> Status:", r_unauth.status_code, flush=True)
    except Exception as e:
        print("Unauth request error:", e, flush=True)

    # Login test
    login_payload = {
        "email": "accountant@litebooks.ai",
        "password": "Password123!"
    }
    r_login = requests.post("http://127.0.0.1:8000/api/v1/auth/login", json=login_payload, timeout=5)
    print("POST /api/v1/auth/login -> Status:", r_login.status_code, flush=True)
    token = None
    if r_login.status_code == 200:
        login_data = r_login.json()
        token = login_data.get("access_token")
        print("JWT Token acquired:", bool(token), "| Token type:", login_data.get("token_type"), flush=True)

    headers = {"Authorization": f"Bearer {token}"} if token else {}

    # Authenticated summary test
    print("Calling authenticated GET /api/v1/dashboard/summary...", flush=True)
    try:
        r_auth = requests.get("http://127.0.0.1:8000/api/v1/dashboard/summary", headers=headers, timeout=10)
        print("Authenticated GET /api/v1/dashboard/summary -> Status:", r_auth.status_code, flush=True)
    except Exception as e:
        print("Auth summary error:", e, flush=True)

    print("\n--- 4. Testing File Uploads ---", flush=True)
    # XLSX
    xlsx_doc_id = None
    try:
        with open("d:/LiteBooks/backend/Zion_Lifts_Financials.xlsx", "rb") as f:
            r_xlsx = requests.post(
                "http://127.0.0.1:8000/api/v1/documents/upload",
                files={"file": ("Zion_Lifts_Financials.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
                headers=headers,
                timeout=15
            )
        print("Upload XLSX Status:", r_xlsx.status_code, "| Response:", r_xlsx.json() if r_xlsx.status_code == 200 else r_xlsx.text, flush=True)
        xlsx_doc_id = r_xlsx.json().get("id") if r_xlsx.status_code in (200, 201) else None
    except Exception as e:
        print("Upload XLSX error:", e, flush=True)

    # XLS
    try:
        with open("d:/LiteBooks/test_files/financial_sample.xls", "rb") as f:
            r_xls = requests.post(
                "http://127.0.0.1:8000/api/v1/documents/upload",
                files={"file": ("financial_sample.xls", f, "application/vnd.ms-excel")},
                headers=headers,
                timeout=15
            )
        print("Upload XLS Status:", r_xls.status_code, "| Response:", r_xls.json() if r_xls.status_code == 200 else r_xls.text, flush=True)
    except Exception as e:
        print("Upload XLS error:", e, flush=True)

    # CSV
    try:
        with open("d:/LiteBooks/test_files/accounting_sample.csv", "rb") as f:
            r_csv = requests.post(
                "http://127.0.0.1:8000/api/v1/documents/upload",
                files={"file": ("accounting_sample.csv", f, "text/csv")},
                headers=headers,
                timeout=15
            )
        print("Upload CSV Status:", r_csv.status_code, "| Response:", r_csv.json() if r_csv.status_code == 200 else r_csv.text, flush=True)
    except Exception as e:
        print("Upload CSV error:", e, flush=True)

    # PDF
    try:
        with open("d:/LiteBooks/test_files/vendor_invoice.pdf", "rb") as f:
            r_pdf = requests.post(
                "http://127.0.0.1:8000/api/v1/documents/upload",
                files={"file": ("vendor_invoice.pdf", f, "application/pdf")},
                headers=headers,
                timeout=15
            )
        print("Upload PDF Status:", r_pdf.status_code, "| Response:", r_pdf.json() if r_pdf.status_code == 200 else r_pdf.text, flush=True)
    except Exception as e:
        print("Upload PDF error:", e, flush=True)

    # Invalid PNG
    try:
        with open("d:/LiteBooks/test_files/invalid_image.png", "rb") as f:
            r_png = requests.post(
                "http://127.0.0.1:8000/api/v1/documents/upload",
                files={"file": ("invalid_image.png", f, "image/png")},
                headers=headers,
                timeout=15
            )
        print("Upload PNG (invalid) Status:", r_png.status_code, "| Detail:", r_png.text, flush=True)
    except Exception as e:
        print("Upload PNG error:", e, flush=True)

    print("\n--- 5. Testing Document Inspection & Persistence ---", flush=True)
    if xlsx_doc_id:
        try:
            r_inspect = requests.get(f"http://127.0.0.1:8000/api/v1/documents/{xlsx_doc_id}/analysis", headers=headers, timeout=15)
            print("Analysis Status:", r_inspect.status_code, flush=True)
            if r_inspect.status_code == 200:
                insp = r_inspect.json()
                print("Sheets found:", [s.get("sheet_name") for s in insp.get("sheets", [])], flush=True)
                print("Discrepancies found:", len(insp.get("discrepancies", [])), flush=True)
        except Exception as e:
            print("Inspection error:", e, flush=True)

    print("\n--- 6. Testing AI Assistant with Attached Document ---", flush=True)
    try:
        chat_payload = {
            "message": "What is wrong with this workbook?",
            "file_ids": [xlsx_doc_id] if xlsx_doc_id else []
        }
        r_chat = requests.post("http://127.0.0.1:8000/api/v1/assistant/chat", json=chat_payload, headers=headers, timeout=20)
        print("AI Chat Status:", r_chat.status_code, flush=True)
        if r_chat.status_code == 200:
            chat_resp = r_chat.json()
            print("AI Response Preview:", chat_resp.get("message", "")[:300], flush=True)
            print("Findings attached to reply:", len(chat_resp.get("findings", [])), flush=True)
    except Exception as e:
        print("AI Chat error:", e, flush=True)

if __name__ == "__main__":
    test_live_servers()
