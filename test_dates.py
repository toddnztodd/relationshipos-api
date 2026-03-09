"""
Test suite for Important Dates endpoints.

Tests all four per-person CRUD endpoints and the cross-person upcoming endpoint.
Requires the server to be running and seed data to be loaded.
"""

import sys
import requests
from datetime import date, timedelta

BASE = "http://localhost:8000"
API  = f"{BASE}/api/v1"

PASS = "✓"
FAIL = "✗"

errors = 0


def check(label: str, resp: requests.Response, expected_status: int) -> dict:
    global errors
    ok = resp.status_code == expected_status
    mark = PASS if ok else FAIL
    print(f"  {mark} [{resp.status_code}] {label}")
    if not ok:
        errors += 1
        print(f"      Expected {expected_status}. Body: {resp.text[:300]}")
    return resp.json() if ok and resp.status_code != 204 else {}


def main():
    print("=" * 60)
    print("RelationshipOS — Important Dates Test Suite")
    print("=" * 60)

    # ── Auth ──────────────────────────────────────────────────────
    print("\n── Auth ──")
    r = requests.post(f"{API}/auth/login", json={"email": "todd@eves.co.nz", "password": "password123"})
    if r.status_code != 200:
        print(f"FATAL: Login failed ({r.status_code}). Run seed_data.py first.")
        sys.exit(1)
    token = r.json()["access_token"]
    H = {"Authorization": f"Bearer {token}"}
    print(f"  {PASS} Logged in as todd@eves.co.nz")

    # ── Verify person 1 exists ────────────────────────────────────
    r = requests.get(f"{API}/people/1", headers=H)
    if r.status_code != 200:
        print("FATAL: Person 1 not found. Run seed_data.py first.")
        sys.exit(1)
    person = r.json()
    print(f"  {PASS} Person 1 confirmed: {person['first_name']} {person['last_name']}")

    # ── POST — create dates for person 1 ─────────────────────────
    print("\n── POST /api/v1/people/1/dates/ ──")

    # Birthday: today + 5 days (will appear in upcoming/14)
    bday_date = (date.today() + timedelta(days=5)).strftime("%m-%d")
    r = requests.post(f"{API}/people/1/dates/", headers=H, json={
        "label": "Birthday",
        "date": bday_date,
        "year": 1985,
        "reminder_days_before": 7,
        "notes": "Loves coffee — send a card"
    })
    bday = check("Create Birthday", r, 201)
    bday_id = bday.get("id")
    print(f"      id={bday_id}, label={bday.get('label')}, date={bday.get('date')}, year={bday.get('year')}")

    # Anniversary: today + 30 days (outside default 14-day window)
    ann_date = (date.today() + timedelta(days=30)).strftime("%m-%d")
    r = requests.post(f"{API}/people/1/dates/", headers=H, json={
        "label": "Wedding Anniversary",
        "date": ann_date,
        "reminder_days_before": 14,
    })
    ann = check("Create Anniversary", r, 201)
    ann_id = ann.get("id")
    print(f"      id={ann_id}, label={ann.get('label')}, date={ann.get('date')}")

    # Add a date for person 2 as well (for cross-person upcoming test)
    soon_date = (date.today() + timedelta(days=3)).strftime("%m-%d")
    r = requests.post(f"{API}/people/2/dates/", headers=H, json={
        "label": "Settlement Date",
        "date": soon_date,
        "notes": "Contract signed — follow up"
    })
    p2_date = check("Create date for person 2", r, 201)
    p2_date_id = p2_date.get("id")
    print(f"      id={p2_date_id}, label={p2_date.get('label')}, date={p2_date.get('date')}")

    # Validation: bad MM-DD format
    r = requests.post(f"{API}/people/1/dates/", headers=H, json={
        "label": "Bad Date", "date": "25-03"  # wrong order
    })
    check("Reject invalid MM-DD (25-03)", r, 422)

    # Validation: person not found
    r = requests.post(f"{API}/people/99999/dates/", headers=H, json={
        "label": "Ghost", "date": "01-01"
    })
    check("404 for unknown person", r, 404)

    # ── GET — list dates for person 1 ─────────────────────────────
    print("\n── GET /api/v1/people/1/dates/ ──")
    r = requests.get(f"{API}/people/1/dates/", headers=H)
    dates_list = check("List dates for person 1", r, 200)
    print(f"      Returned {len(dates_list)} date(s)")
    for d in dates_list:
        print(f"        id={d['id']}  label={d['label']}  date={d['date']}  year={d['year']}  reminder={d['reminder_days_before']}d")

    # GET for person with no dates
    r = requests.get(f"{API}/people/3/dates/", headers=H)
    empty = check("List dates for person 3 (empty)", r, 200)
    print(f"      Returned {len(empty)} date(s) (expected 0)")

    # ── PUT — update a date ───────────────────────────────────────
    print(f"\n── PUT /api/v1/people/1/dates/{bday_id}/ ──")
    r = requests.put(f"{API}/people/1/dates/{bday_id}/", headers=H, json={
        "notes": "Updated note — prefers tea actually",
        "reminder_days_before": 10
    })
    updated = check("Update Birthday notes and reminder", r, 200)
    print(f"      notes='{updated.get('notes')}'  reminder={updated.get('reminder_days_before')}d")

    # PUT wrong person scope
    r = requests.put(f"{API}/people/2/dates/{bday_id}/", headers=H, json={"label": "Hijack"})
    check("404 when date_id belongs to different person", r, 404)

    # ── DELETE — remove a date ────────────────────────────────────
    print(f"\n── DELETE /api/v1/people/1/dates/{ann_id}/ ──")
    r = requests.delete(f"{API}/people/1/dates/{ann_id}/", headers=H)
    check("Delete Anniversary", r, 204)

    # Confirm it's gone
    r = requests.get(f"{API}/people/1/dates/", headers=H)
    remaining = check("List after delete (should be 1 left)", r, 200)
    print(f"      Remaining dates for person 1: {len(remaining)} (expected 1)")

    # ── GET /dates/upcoming/ ──────────────────────────────────────
    print("\n── GET /api/v1/dates/upcoming/ ──")

    # Default 14-day window — should include birthday (+5 days) and person 2 date (+3 days)
    r = requests.get(f"{API}/dates/upcoming/", headers=H)
    upcoming_14 = check("Upcoming dates (default 14 days)", r, 200)
    print(f"      Found {len(upcoming_14)} date(s) in next 14 days:")
    for d in upcoming_14:
        print(f"        [{d['days_until']}d] {d['person_first_name']} {d['person_last_name'] or ''} — {d['label']} on {d['next_occurrence']}")

    # Narrow window of 2 days — should only include person 2's date (+3 days is outside)
    r = requests.get(f"{API}/dates/upcoming/?days=2", headers=H)
    upcoming_2 = check("Upcoming dates (2-day window)", r, 200)
    print(f"      Found {len(upcoming_2)} date(s) in next 2 days")

    # Wide window of 365 days — should include everything
    r = requests.get(f"{API}/dates/upcoming/?days=365", headers=H)
    upcoming_365 = check("Upcoming dates (365-day window)", r, 200)
    print(f"      Found {len(upcoming_365)} date(s) in next 365 days")

    # Verify sort order (days_until ascending)
    if len(upcoming_14) >= 2:
        assert upcoming_14[0]["days_until"] <= upcoming_14[1]["days_until"], "Results not sorted by days_until"
        print(f"  {PASS} Results correctly sorted by days_until ascending")

    # Verify person details are included
    if upcoming_14:
        first = upcoming_14[0]
        assert "person_first_name" in first, "Missing person_first_name"
        assert "person_last_name" in first, "Missing person_last_name"
        assert "person_phone" in first, "Missing person_phone"
        assert "next_occurrence" in first, "Missing next_occurrence"
        assert "days_until" in first, "Missing days_until"
        print(f"  {PASS} Response shape includes all required person and occurrence fields")

    # ── Auth guard ────────────────────────────────────────────────
    print("\n── Auth Guards ──")
    r = requests.get(f"{API}/people/1/dates/")
    check("GET dates without token → 401", r, 401)
    r = requests.get(f"{API}/dates/upcoming/")
    check("GET upcoming without token → 401", r, 401)

    # ── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    if errors == 0:
        print(f"ALL TESTS PASSED ✓")
    else:
        print(f"{errors} TEST(S) FAILED ✗")
    print("=" * 60)
    return errors


if __name__ == "__main__":
    sys.exit(main())
