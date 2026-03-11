"""Tests for Referral Programme endpoints.

Run with:
    python3.11 -m pytest test_referrals.py -v

Or against a specific API:
    API_BASE_URL=https://relationshipos-api.onrender.com/api/v1 python3.11 -m pytest test_referrals.py -v
"""

import os
import pytest
import requests

BASE_URL = os.environ.get("API_BASE_URL", "https://relationshipos-api.onrender.com/api/v1")
TEST_EMAIL = "test@example.com"
TEST_PASSWORD = "testpassword123"

# ── Auth helper ───────────────────────────────────────────────────────────────

def get_token():
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_EMAIL,
        "password": TEST_PASSWORD,
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["access_token"]


def auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def create_person(token, first_name, phone, email=None):
    payload = {
        "first_name": first_name,
        "last_name": "Referral",
        "phone": phone,
        "tier": "A",
    }
    if email:
        payload["email"] = email
    r = requests.post(f"{BASE_URL}/people", json=payload, headers=auth_headers(token))
    assert r.status_code == 201, f"Create person failed: {r.text}"
    return r.json()["id"]


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestReferralMemberRegistration:
    """Tests for POST /people/{id}/register-referral-member."""

    def test_register_referral_member_no_email(self):
        """Register a person with no email — should succeed, email_sent=False."""
        token = get_token()
        person_id = create_person(token, "NoEmail", "+64211000001")

        r = requests.post(
            f"{BASE_URL}/people/{person_id}/register-referral-member",
            json={"reward_amount": 300},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["referral_member"] is True
        assert data["referral_reward_amount"] == 300.0
        assert data["email_sent"] is False
        assert data["email_sent_reason"] == "No email address on file"

    def test_register_referral_member_with_email_no_smtp(self):
        """Register a person with email but no SMTP configured — email_sent=False."""
        token = get_token()
        person_id = create_person(token, "HasEmail", "+64211000002", email="test_referral@example.com")

        r = requests.post(
            f"{BASE_URL}/people/{person_id}/register-referral-member",
            json={"reward_amount": 250},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["referral_member"] is True
        assert data["referral_reward_amount"] == 250.0
        assert data["email_sent"] is False
        assert data["email_sent_reason"] == "No SMTP configured"

    def test_register_referral_member_default_reward(self):
        """Register without specifying reward_amount — should default to 250."""
        token = get_token()
        person_id = create_person(token, "DefaultReward", "+64211000003")

        r = requests.post(
            f"{BASE_URL}/people/{person_id}/register-referral-member",
            json={},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["referral_reward_amount"] == 250.0

    def test_register_referral_member_not_found(self):
        """Registering a non-existent person should return 404."""
        token = get_token()
        r = requests.post(
            f"{BASE_URL}/people/999999/register-referral-member",
            json={},
            headers=auth_headers(token),
        )
        assert r.status_code == 404

    def test_register_referral_member_creates_activity(self):
        """Registering a referral member should create an activity log entry."""
        token = get_token()
        person_id = create_person(token, "ActivityCheck", "+64211000004")

        requests.post(
            f"{BASE_URL}/people/{person_id}/register-referral-member",
            json={"reward_amount": 200},
            headers=auth_headers(token),
        )

        # Check activities for this person
        r = requests.get(
            f"{BASE_URL}/activities?person_id={person_id}",
            headers=auth_headers(token),
        )
        assert r.status_code == 200
        activities = r.json()
        notes_list = [a["notes"] for a in activities if a.get("notes")]
        assert any("Referral programme registered" in n for n in notes_list), \
            f"No referral activity found. Activities: {notes_list}"


class TestReferralCRUD:
    """Tests for referral CRUD endpoints."""

    def test_create_referral(self):
        """Create a referral relationship between two people."""
        token = get_token()
        referrer_id = create_person(token, "Referrer", "+64211000010")
        referred_id = create_person(token, "Referred", "+64211000011")

        r = requests.post(
            f"{BASE_URL}/referrals",
            json={
                "referrer_person_id": referrer_id,
                "referred_person_id": referred_id,
                "notes": "Met at open home",
            },
            headers=auth_headers(token),
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["referrer_person_id"] == referrer_id
        assert data["referred_person_id"] == referred_id
        assert data["referral_status"] == "registered"
        assert data["reward_status"] == "none"
        assert data["notes"] == "Met at open home"

    def test_create_referral_duplicate_rejected(self):
        """Creating the same referral twice should return 409."""
        token = get_token()
        referrer_id = create_person(token, "DupReferrer", "+64211000020")
        referred_id = create_person(token, "DupReferred", "+64211000021")

        payload = {
            "referrer_person_id": referrer_id,
            "referred_person_id": referred_id,
        }
        r1 = requests.post(f"{BASE_URL}/referrals", json=payload, headers=auth_headers(token))
        assert r1.status_code == 201

        r2 = requests.post(f"{BASE_URL}/referrals", json=payload, headers=auth_headers(token))
        assert r2.status_code == 409

    def test_list_referrals(self):
        """GET /referrals should return a list."""
        token = get_token()
        r = requests.get(f"{BASE_URL}/referrals", headers=auth_headers(token))
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_list_referrals_filter_by_status(self):
        """Filter referrals by status."""
        token = get_token()
        referrer_id = create_person(token, "FilterRef", "+64211000030")
        referred_id = create_person(token, "FilterRefd", "+64211000031")

        requests.post(
            f"{BASE_URL}/referrals",
            json={"referrer_person_id": referrer_id, "referred_person_id": referred_id},
            headers=auth_headers(token),
        )

        r = requests.get(
            f"{BASE_URL}/referrals?status=registered",
            headers=auth_headers(token),
        )
        assert r.status_code == 200
        data = r.json()
        assert all(item["referral_status"] == "registered" for item in data)

    def test_list_person_referrals(self):
        """GET /people/{id}/referrals should return referrals for that person."""
        token = get_token()
        referrer_id = create_person(token, "PersonRef", "+64211000040")
        referred_id = create_person(token, "PersonRefd", "+64211000041")

        requests.post(
            f"{BASE_URL}/referrals",
            json={"referrer_person_id": referrer_id, "referred_person_id": referred_id},
            headers=auth_headers(token),
        )

        r = requests.get(
            f"{BASE_URL}/people/{referrer_id}/referrals",
            headers=auth_headers(token),
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1
        assert any(item["referrer_person_id"] == referrer_id for item in data)

    def test_update_referral_status(self):
        """Update referral_status through the lifecycle."""
        token = get_token()
        referrer_id = create_person(token, "UpdateRef", "+64211000050")
        referred_id = create_person(token, "UpdateRefd", "+64211000051")

        create_r = requests.post(
            f"{BASE_URL}/referrals",
            json={"referrer_person_id": referrer_id, "referred_person_id": referred_id},
            headers=auth_headers(token),
        )
        ref_id = create_r.json()["id"]

        r = requests.put(
            f"{BASE_URL}/referrals/{ref_id}",
            json={"referral_status": "listing_secured"},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, r.text
        assert r.json()["referral_status"] == "listing_secured"

    def test_update_reward_status_to_earned_creates_activity(self):
        """Updating reward_status to 'earned' should create an activity log."""
        token = get_token()
        referrer_id = create_person(token, "EarnRef", "+64211000060")
        referred_id = create_person(token, "EarnRefd", "+64211000061")

        create_r = requests.post(
            f"{BASE_URL}/referrals",
            json={"referrer_person_id": referrer_id, "referred_person_id": referred_id},
            headers=auth_headers(token),
        )
        ref_id = create_r.json()["id"]

        r = requests.put(
            f"{BASE_URL}/referrals/{ref_id}",
            json={"reward_status": "earned"},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, r.text
        assert r.json()["reward_status"] == "earned"

        # Check activity was logged
        acts = requests.get(
            f"{BASE_URL}/activities?person_id={referrer_id}",
            headers=auth_headers(token),
        )
        notes_list = [a["notes"] for a in acts.json() if a.get("notes")]
        assert any("reward earned" in n for n in notes_list), \
            f"No reward earned activity. Notes: {notes_list}"

    def test_update_reward_status_to_paid_sets_paid_at(self):
        """Updating reward_status to 'paid' should set reward_paid_at."""
        token = get_token()
        referrer_id = create_person(token, "PaidRef", "+64211000070")
        referred_id = create_person(token, "PaidRefd", "+64211000071")

        create_r = requests.post(
            f"{BASE_URL}/referrals",
            json={"referrer_person_id": referrer_id, "referred_person_id": referred_id},
            headers=auth_headers(token),
        )
        ref_id = create_r.json()["id"]

        r = requests.put(
            f"{BASE_URL}/referrals/{ref_id}",
            json={"reward_status": "paid"},
            headers=auth_headers(token),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["reward_status"] == "paid"
        assert data["reward_paid_at"] is not None

    def test_close_referral(self):
        """DELETE /referrals/{id} should soft-close the referral."""
        token = get_token()
        referrer_id = create_person(token, "CloseRef", "+64211000080")
        referred_id = create_person(token, "CloseRefd", "+64211000081")

        create_r = requests.post(
            f"{BASE_URL}/referrals",
            json={"referrer_person_id": referrer_id, "referred_person_id": referred_id},
            headers=auth_headers(token),
        )
        ref_id = create_r.json()["id"]

        r = requests.delete(
            f"{BASE_URL}/referrals/{ref_id}",
            headers=auth_headers(token),
        )
        assert r.status_code == 200, r.text
        assert r.json()["id"] == ref_id

        # Verify it shows as closed in list
        list_r = requests.get(
            f"{BASE_URL}/referrals?status=closed",
            headers=auth_headers(token),
        )
        closed_ids = [item["id"] for item in list_r.json()]
        assert ref_id in closed_ids

    def test_invalid_referral_status_rejected(self):
        """Updating to an invalid status should return 422."""
        token = get_token()
        referrer_id = create_person(token, "InvalidRef", "+64211000090")
        referred_id = create_person(token, "InvalidRefd", "+64211000091")

        create_r = requests.post(
            f"{BASE_URL}/referrals",
            json={"referrer_person_id": referrer_id, "referred_person_id": referred_id},
            headers=auth_headers(token),
        )
        ref_id = create_r.json()["id"]

        r = requests.put(
            f"{BASE_URL}/referrals/{ref_id}",
            json={"referral_status": "invalid_status"},
            headers=auth_headers(token),
        )
        assert r.status_code == 422

    def test_referral_not_found(self):
        """Updating a non-existent referral should return 404."""
        token = get_token()
        r = requests.put(
            f"{BASE_URL}/referrals/999999",
            json={"referral_status": "sold"},
            headers=auth_headers(token),
        )
        assert r.status_code == 404

    def test_referral_includes_person_summaries(self):
        """Referral response should include referrer and referred person summaries."""
        token = get_token()
        referrer_id = create_person(token, "SummaryRef", "+64211000100")
        referred_id = create_person(token, "SummaryRefd", "+64211000101")

        r = requests.post(
            f"{BASE_URL}/referrals",
            json={"referrer_person_id": referrer_id, "referred_person_id": referred_id},
            headers=auth_headers(token),
        )
        assert r.status_code == 201, r.text
        data = r.json()
        assert data["referrer"] is not None
        assert data["referrer"]["first_name"] == "SummaryRef"
        assert data["referred"] is not None
        assert data["referred"]["first_name"] == "SummaryRefd"


if __name__ == "__main__":
    # Quick smoke test
    token = get_token()
    print(f"Login OK. Token: {token[:20]}...")

    person_id = create_person(token, "SmokeTest", "+64211999999")
    r = requests.post(
        f"{BASE_URL}/people/{person_id}/register-referral-member",
        json={"reward_amount": 500},
        headers=auth_headers(token),
    )
    print(f"Register referral member: {r.status_code} — {r.json()}")
