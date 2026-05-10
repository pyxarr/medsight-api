import json
import os
from pathlib import Path
from typing import Dict, Any

import requests
import jwt
from dotenv import load_dotenv

# Load environment variables from root and frontend
load_dotenv()
frontend_env = Path(__file__).resolve().parent.parent.parent / "medsight" / ".env"
if frontend_env.exists():
    load_dotenv(frontend_env)

BASE_URL = os.getenv("TEST_API_BASE_URL", "http://127.0.0.1:8000/api")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

class SupabaseAuth:
    """Helper to manage test identities on Supabase."""
    def __init__(self, role: str, email: str, password: str):
        self.role = role
        self.email = email
        self.password = password
        self.token = None

    def _sign_in(self) -> requests.Response:
        """Helper to perform the sign-in request."""
        return requests.post(
            f"{SUPABASE_URL.rstrip('/')}/auth/v1/token?grant_type=password",
            headers={"apikey": SUPABASE_PUBLISHABLE_KEY, "Content-Type": "application/json"},
            json={"email": self.email, "password": self.password},
            timeout=10
        )

    def authenticate(self):
        """Ensure user exists and get an access token."""
        # 1. Try to sign in first
        resp = self._sign_in()
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            # DEBUG: Print the algorithm used in the token header
            try:
                header = jwt.get_unverified_header(token)
                print(f"JWT Header for {self.role}: {header}")
            except Exception as e:
                print(f"Could not decode header: {e}")
            
            self.token = token
            return self.token

        print(f"Sign-in failed for {self.email} ({resp.status_code}), attempting signup...")

        # 2. Attempt sign-up
        try:
            signup_resp = requests.post(
                f"{SUPABASE_URL.rstrip('/')}/auth/v1/signup",
                headers={"apikey": SUPABASE_PUBLISHABLE_KEY, "Content-Type": "application/json"},
                json={"email": self.email, "password": self.password, "data": {"role": self.role}},
                timeout=10
            )
            if signup_resp.status_code not in {200, 201, 400, 422}:
                print(f"Signup error: {signup_resp.status_code} - {signup_resp.text}")
        except Exception as e:
            print(f"Signup exception: {e}")

        # 3. Try to sign in again after signup attempt
        resp = self._sign_in()
        if resp.status_code != 200:
            print(f"Auth Error ({self.role}): {resp.status_code} - {resp.text}")
            resp.raise_for_status()
            
        self.token = resp.json().get("access_token")
        print(f"Token for {self.role}: {self.token[:50]}...")
        return self.token

def run_test(name: str, endpoint: str, token: str, payload: Dict[str, Any], expected_status: int = 200):
    """Execute a single API request and print the result."""
    print(f"\n--- Testing: {name} ---")
    url = f"{BASE_URL}/{endpoint}"
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        print(f"Status: {response.status_code}")
        
        if response.status_code == expected_status:
            print("SUCCESS: Response matches expected status")
            if response.status_code == 200:
                print(json.dumps(response.json(), indent=2))
        else:
            print(f"FAILED: Expected {expected_status}, got {response.status_code}")
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"ERROR: {str(e)}")

def main():
    # 1. Setup Identities (exactly 2 accounts)
    print("Authenticating test users...")
    c_email = os.getenv("TEST_CLINICIAN_EMAIL", "test.clinician@example.com")
    c_pass = os.getenv("TEST_CLINICIAN_PASSWORD", "TestPass123!")
    m_email = os.getenv("TEST_MEMBER_EMAIL", "test.member@example.com")
    m_pass = os.getenv("TEST_MEMBER_PASSWORD", "TestPass123!")
    
    print(f"Clinician Email: {c_email}, Password: {c_pass}")
    print(f"Member Email: {m_email}, Password: {m_pass}")
    
    clinician = SupabaseAuth("clinician", c_email, c_pass)
    member = SupabaseAuth("member", m_email, m_pass)
    
    print("Attempting to authenticate clinician...")
    try:
        c_token = clinician.authenticate()
        print(f"Clinician auth successful!")
    except Exception as e:
        print(f"Clinician auth FAILED: {e}")
        return
    
    print("Attempting to authenticate member...")
    try:
        m_token = member.authenticate()
        print(f"Member auth successful!")
    except Exception as e:
        print(f"Member auth FAILED: {e}")
        return

    print("\nWarming up API and database connection...")
    try:
        requests.get("http://127.0.0.1:8000/", timeout=30)
        print("Warmup complete.")
    except Exception:
        print("Warmup timed out — continuing anyway.")

    # 2. Define Payloads
    clinical_data = {
        "age": 45.0,
        "menopause": 1,
        "tumor_size_cm": 2.5,
        "invasive_nodes": 1.0,
        "breast_side": 0,
        "metastasis": 0,
        "breast_quadrant": 1,
        "breast_disease_history": 0
    }

    blood_data = {
        "body_mass_index": 24.5,
        "glucose": 90.0,
        "insulin": 7.2,
        "homeostasis_model_assessment": 2.0,
        "leptin": 15.1,
        "adiponectin": 10.2,
        "resistin": 8.1,
        "monocyte_chemoattractant_protein": 300.0
    }

    # 3. Execute Scenarios
    
    # Scenario A: Member Flow (Clinical only) - Requires patient_id
    run_test(
        "Member Assessment (Clinical Only)",
        "member/assess",
        m_token,
        {"patient_id": "MEM-001", "clinical_data": clinical_data}
    )

    # Scenario B: Clinician Basic (Clinical only) - NO patient_id
    run_test(
        "Clinician Assessment (Clinical Only)",
        "clinician/manual-assess",
        c_token,
        {"first_name": "Test", "last_name": "Clinician", "clinical_data": clinical_data}
    )

    # Scenario C: Clinician Blood (Clinical + Blood) - NO patient_id
    run_test(
        "Clinician Assessment (Clinical + Blood)",
        "clinician/manual-assess",
        c_token,
        {"first_name": "Test", "last_name": "Clinician", "clinical_data": clinical_data, "blood_panel": blood_data}
    )

    # Scenario D: Negative Test - Clinician attempting to send Biopsy data
    run_test(
        "Clinician Manual Entry (Attempting Biopsy - should be ignored)",
        "clinician/manual-assess",
        c_token,
        {
            "first_name": "Test", 
            "last_name": "Clinician", 
            "clinical_data": clinical_data,
            "biopsy_data": {"mean_radius": 15.0} # Extra field
        }
    )

if __name__ == "__main__":
    main()
