import requests

BASE_URL = "http://127.0.0.1:8000"

def run_auth_and_scoping_audit():
    print("--- 1. Testing Registration and Login ---")
    # Register User A
    user_a_email = "audit_user_a@litebooks.ai"
    user_b_email = "audit_user_b@litebooks.ai"
    pwd = "AuditPassword123!"

    # Login or Register User A
    login_a = requests.post(f"{BASE_URL}/api/v1/auth/login", data={"username": user_a_email, "password": pwd})
    if login_a.status_code != 200:
        reg_a = requests.post(f"{BASE_URL}/api/v1/auth/register", json={
            "email": user_a_email,
            "full_name": "Audit User A",
            "password": pwd,
            "role": "accountant"
        })
        assert reg_a.status_code in (200, 201), f"Reg A failed: {reg_a.text}"
        login_a = requests.post(f"{BASE_URL}/api/v1/auth/login", data={"username": user_a_email, "password": pwd})
    assert login_a.status_code == 200, f"Login A failed: {login_a.text}"
    token_a = login_a.json()["access_token"]
    headers_a = {"Authorization": f"Bearer {token_a}"}

    # Login or Register User B
    login_b = requests.post(f"{BASE_URL}/api/v1/auth/login", data={"username": user_b_email, "password": pwd})
    if login_b.status_code != 200:
        reg_b = requests.post(f"{BASE_URL}/api/v1/auth/register", json={
            "email": user_b_email,
            "full_name": "Audit User B",
            "password": pwd,
            "role": "accountant"
        })
        assert reg_b.status_code in (200, 201), f"Reg B failed: {reg_b.text}"
        login_b = requests.post(f"{BASE_URL}/api/v1/auth/login", data={"username": user_b_email, "password": pwd})
    assert login_b.status_code == 200, f"Login B failed: {login_b.text}"
    token_b = login_b.json()["access_token"]
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Test /me
    me_a = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers_a)
    assert me_a.status_code == 200, me_a.text
    assert me_a.json()["email"] == user_a_email
    user_a_id = me_a.json()["id"]

    me_b = requests.get(f"{BASE_URL}/api/v1/auth/me", headers=headers_b)
    assert me_b.status_code == 200, me_b.text
    assert me_b.json()["email"] == user_b_email
    user_b_id = me_b.json()["id"]
    assert user_a_id != user_b_id, "User IDs must be distinct"

    print("--- 2. Testing Protected Routes without Token (Must be 401) ---")
    protected_endpoints = [
        "/api/v1/auth/me",
        "/api/v1/documents",
        "/api/v1/reconciliation/sessions",
        "/api/v1/gst/registrations",
        "/api/v1/itr/profiles",
        "/api/v1/financial-statements/profiles",
        "/api/v1/assistant/conversations",
    ]
    for ep in protected_endpoints:
        unauth = requests.get(f"{BASE_URL}{ep}")
        assert unauth.status_code == 401, f"Expected 401 for {ep}, got {unauth.status_code}"

    print("--- 3. Testing User-Scoped Data Isolation ---")
    # A creates Financial Statement profile
    fs_a = requests.post(f"{BASE_URL}/api/financial-statements/profiles", headers=headers_a, json={
        "entity_name": "User A Private Ltd",
        "financial_year": "2023-24",
        "reporting_period": "ANNUAL",
        "framework": "SCHEDULE_III"
    })
    assert fs_a.status_code == 201, fs_a.text
    fs_a_id = fs_a.json()["id"]

    # User B lists profiles: User A's profile must NOT appear in User B's list
    fs_b_list = requests.get(f"{BASE_URL}/api/financial-statements/profiles", headers=headers_b)
    assert fs_b_list.status_code == 200, fs_b_list.text
    b_ids = [p["id"] for p in fs_b_list.json()]
    assert fs_a_id not in b_ids, "Cross-user data leakage in Financial Statements listing!"

    # User B directly tries to access User A's profile: MUST be 404
    fs_b_access = requests.get(f"{BASE_URL}/api/financial-statements/profiles/{fs_a_id}", headers=headers_b)
    assert fs_b_access.status_code == 404, f"Cross-user access permitted: {fs_b_access.status_code}"

    # A creates ITR profile
    itr_a = requests.post(f"{BASE_URL}/api/itr/profiles", headers=headers_a, json={
        "pan": "AAAPA9999K",
        "taxpayer_name": "User A Taxpayer",
        "assessment_year": "2024-25",
        "financial_year": "2023-24",
    })
    assert itr_a.status_code == 201, itr_a.text
    itr_a_id = itr_a.json()["id"]

    # User B lists ITR profiles: User A's ITR profile must NOT be in B's list
    itr_b_list = requests.get(f"{BASE_URL}/api/itr/profiles", headers=headers_b)
    assert itr_b_list.status_code == 200, itr_b_list.text
    b_itr_ids = [p["id"] for p in itr_b_list.json()]
    assert itr_a_id not in b_itr_ids, "Cross-user data leakage in ITR listing!"

    # User B directly tries to access User A's ITR profile
    itr_b_access = requests.get(f"{BASE_URL}/api/itr/profiles/{itr_a_id}", headers=headers_b)
    assert itr_b_access.status_code == 404, f"Cross-user ITR access permitted: {itr_b_access.status_code}"

    # A creates GST registration
    gst_a = requests.post(f"{BASE_URL}/api/gst/registrations", headers=headers_a, json={
        "gstin": "27AAAPA9999K1Z5",
        "legal_name": "User A GST Corp",
        "trade_name": "User A Corp",
        "state_code": "27",
    })
    assert gst_a.status_code in (200, 201), gst_a.text
    gst_a_id = gst_a.json()["id"]

    # User B lists GST registrations: must not see User A's registration
    gst_b_list = requests.get(f"{BASE_URL}/api/gst/registrations", headers=headers_b)
    assert gst_b_list.status_code == 200, gst_b_list.text
    b_gst_ids = [r["id"] for r in gst_b_list.json()]
    assert gst_a_id not in b_gst_ids, "Cross-user data leakage in GST registrations!"

    # User B directly tries to access User A's GST registration
    gst_b_access = requests.get(f"{BASE_URL}/api/gst/registrations/{gst_a_id}", headers=headers_b)
    assert gst_b_access.status_code == 404, f"Cross-user GST access permitted: {gst_b_access.status_code}"

    # A creates AI Assistant conversation
    conv_a = requests.post(f"{BASE_URL}/api/v1/assistant/conversations", headers=headers_a, json={
        "title": "User A Confidential Audit Query"
    })
    assert conv_a.status_code in (200, 201), conv_a.text
    conv_a_id = conv_a.json()["id"]

    # User B directly tries to access User A's conversation
    conv_b_access = requests.get(f"{BASE_URL}/api/v1/assistant/conversations/{conv_a_id}", headers=headers_b)
    assert conv_b_access.status_code in (403, 404), f"Cross-user Assistant conversation access permitted: {conv_b_access.status_code}"

    print("ALL AUTHENTICATION & MULTI-TENANT SCOPING CHECKS PASSED PERFECTLY!")

if __name__ == "__main__":
    run_auth_and_scoping_audit()
