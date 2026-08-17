import io
import os
import json
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
frontend_env = Path(__file__).resolve().parent.parent.parent / "medsight" / ".env"
if frontend_env.exists():
    load_dotenv(frontend_env)

BASE_URL = os.getenv("TEST_API_BASE_URL", "http://127.0.0.1:8000/api")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")

class SupabaseAuth:
    """Helper to manage test identities on Supabase."""
    def __init__(self, role: str, email: str, password: str):
        self.role = role
        self.email = email
        self.password = password
        self.token = None

    def _sign_in(self) -> requests.Response:
        """Perform the Supabase sign-in request and return the response."""
        return requests.post(
            f"{SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password",
            headers={"apikey": SUPABASE_PUBLISHABLE_KEY, "Content-Type": "application/json"},
            json={"email": self.email, "password": self.password},
            timeout=10
        )

    def authenticate(self):
        """Ensure the user exists in Supabase and return a valid access token."""
        resp = self._sign_in()
        if resp.status_code == 200:
            self.token = resp.json().get("access_token")
            return self.token

        try:
            requests.post(
                f"{SUPABASE_URL.rstrip('/')}/auth/v1/signup",
                headers={"apikey": SUPABASE_PUBLISHABLE_KEY, "Content-Type": "application/json"},
                json={"email": self.email, "password": self.password, "data": {"role": self.role}},
                timeout=10
            )
        except Exception:
            pass

        resp = self._sign_in()
        if resp.status_code != 200:
            resp.raise_for_status()
            
        self.token = resp.json().get("access_token")
        return self.token

def run_test(name: str, method: str, endpoint: str, token: str, payload: Any = None, files: Any = None, expected_status: int = 200) -> bool:
    """Execute a single API request and verify the result. Return True if successful."""
    print(f"\n--- Testing: {name} ---")
    if token:
        print(f"Using token: {token[:15]}...")
    
    # The health check lives at the root path, outside the /api prefix used by all other routes.
    if endpoint == "...":
        url = "http://127.0.0.1:8000/"
    else:
        url = f"{BASE_URL}/{endpoint}"
        
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    
    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=30)
        elif method == "POST":
            if files:
                response = requests.post(url, headers=headers, files=files, timeout=30)
            else:
                response = requests.post(url, headers=headers, json=payload, timeout=30)
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unsupported method: {method}")

        print(f"Status: {response.status_code}")
        
        if response.status_code == expected_status:
            print("SUCCESS: Response matches expected status")
            if response.status_code == 200:
                try:
                    print(json.dumps(response.json(), indent=2))
                except json.JSONDecodeError:
                    print("Response body is not JSON")
            return True
        else:
            print(f"FAILED: Expected {expected_status}, got {response.status_code}")
            print(f"Response: {response.text}")
            return False
    except Exception as e:
        print(f"ERROR: {str(e)}")
        return False

def main():
    """Authenticate test users, warm up the API, and run all API verification scenarios."""
    print("Authenticating test users...")
    c_email = os.getenv("TEST_CLINICIAN_EMAIL", "test.clinician@example.com")
    c_pass = os.getenv("TEST_CLINICIAN_PASSWORD", "TestPass123!")
    m_email = os.getenv("TEST_MEMBER_EMAIL", "test.member@example.com")
    m_pass = os.getenv("TEST_MEMBER_PASSWORD", "TestPass123!")
    
    clinician = SupabaseAuth("clinician", c_email, c_pass)
    member = SupabaseAuth("member", m_email, m_pass)
    
    try:
        c_token = clinician.authenticate()
        m_token = member.authenticate()
    except Exception as e:
        print(f"Auth failed: {e}")
        return

    results = []

    print("\nWarming up API...")
    try:
        requests.get("http://127.0.0.1:8000/", timeout=30)
    except Exception:
        pass

    # Payloads
    clinical_data = {
        "age": 45.0, "menopause": 1, "tumor_size_cm": 2.5, "invasive_nodes": 1.0,
        "breast_side": 0, "metastasis": 0, "breast_quadrant": 1, "breast_disease_history": 0
    }

    # 1. Public & General Auth Routes
    results.append(run_test("Health Check", "GET", "...", "None", expected_status=200))
    results.append(run_test("User Profile (Member)", "GET", "users/me", m_token, expected_status=200))
    results.append(run_test("User Profile (Clinician)", "GET", "users/me", c_token, expected_status=200))
    results.append(run_test("User Profile (No Auth)", "GET", "users/me", "", expected_status=401))

    # 2. Member Assessment
    results.append(run_test(
        "Member Manual Assess (Valid)", 
        "POST", "member/manual-assess", m_token, 
        {"first_name": "Test", "last_name": "Member", "clinical_data": clinical_data}, 
        expected_status=200
    ))
    results.append(run_test(
        "Member Manual Assess (Wrong Role - Clinician)", 
        "POST", "member/manual-assess", c_token, 
        {"first_name": "Test", "last_name": "Member", "clinical_data": clinical_data}, 
        expected_status=403
    ))
    results.append(run_test("Member History List", "GET", "member/assessments", m_token, expected_status=200))
    results.append(run_test("Member History List (Wrong Role - Clinician)", "GET", "member/assessments", c_token, expected_status=403))

    # 3. Clinician Manual Assessment
    results.append(run_test(
        "Clinician Manual Assess (Valid)", 
        "POST", "clinician/manual-assess", c_token, 
        {"first_name": "API", "last_name": "Test", "clinical_data": clinical_data}, 
        expected_status=200
    ))
    results.append(run_test(
        "Clinician Manual Assess (Wrong Role - Member)", 
        "POST", "clinician/manual-assess", m_token, 
        {"first_name": "API", "last_name": "Test", "clinical_data": clinical_data}, 
        expected_status=403
    ))

    # 4. Clinician Batch Assessment
    csv_content = "patient_name,cli_age,cli_menopause,cli_tumor_size_cm,cli_invasive_nodes,cli_breast_side,cli_metastasis,cli_breast_quadrant,cli_breast_disease_history\n"
    csv_content += "Batch Test,45,1,2.5,1,0,0,1,0"
    files = {"file": ("test_batch.csv", io.BytesIO(csv_content.encode("utf-8")), "text/csv")}
    
    results.append(run_test(
        "Clinician Batch Assess (Valid)", 
        "POST", "clinician/batch-assess", c_token, 
        payload=None, files=files, 
        expected_status=200
    ))
    results.append(run_test(
        "Clinician Batch Assess (Wrong Role - Member)", 
        "POST", "clinician/batch-assess", m_token, 
        payload=None, files=files, 
        expected_status=403
    ))

    # 5. Clinician History
    results.append(run_test("Clinician History List", "GET", "clinician/assessments", c_token, expected_status=200))
    results.append(run_test("Clinician History List (Wrong Role)", "GET", "clinician/assessments", m_token, expected_status=403))

    total = len(results)

    passed = sum(results)
    failed = total - passed
    
    print("\n" + "="*30)
    print("API TEST SUMMARY")
    print("="*30)
    print(f"Total Tests Run: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print("="*30)

if __name__ == "__main__":
    main()
