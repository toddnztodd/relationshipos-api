"""Comprehensive API test script for RelationshipOS."""

import requests
import json
import sys

BASE = "http://localhost:8000"
API = f"{BASE}/api/v1"

def p(label, resp):
    status = "✓" if resp.status_code < 400 else "✗"
    print(f"  {status} [{resp.status_code}] {label}")
    if resp.status_code >= 400:
        print(f"    Error: {resp.text[:200]}")
    return resp

def main():
    errors = 0

    print("=" * 60)
    print("RelationshipOS API Test Suite")
    print("=" * 60)

    # ── Health ──
    print("\n── Health ──")
    r = p("GET /", requests.get(f"{BASE}/"))
    r = p("GET /health", requests.get(f"{BASE}/health"))

    # ── Auth ──
    print("\n── Authentication ──")
    r = p("POST /auth/login", requests.post(f"{API}/auth/login", json={
        "email": "todd@eves.co.nz", "password": "password123"
    }))
    if r.status_code != 200:
        print("FATAL: Cannot login. Aborting.")
        sys.exit(1)
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test duplicate registration
    r = p("POST /auth/register (duplicate)", requests.post(f"{API}/auth/register", json={
        "email": "todd@eves.co.nz", "password": "testtest", "full_name": "Test"
    }))
    if r.status_code == 409:
        print("    (Expected 409 conflict)")

    # ── People ──
    print("\n── People ──")
    r = p("GET /people/", requests.get(f"{API}/people/", headers=headers))
    people = r.json()
    print(f"    Found {len(people)} people")

    r = p("GET /people/ (filter tier=A)", requests.get(f"{API}/people/?tier=A", headers=headers))
    a_tier = r.json()
    print(f"    A-tier: {len(a_tier)} people")

    r = p("GET /people/ (search=Sarah)", requests.get(f"{API}/people/?search=Sarah", headers=headers))
    search_results = r.json()
    print(f"    Search 'Sarah': {len(search_results)} results")

    r = p("GET /people/search?phone=+64211234567", requests.get(
        f"{API}/people/search?phone=%2B64211234567", headers=headers
    ))

    r = p("GET /people/1", requests.get(f"{API}/people/1", headers=headers))
    if r.status_code == 200:
        person = r.json()
        print(f"    Person: {person['first_name']} {person['last_name']}, cadence={person['cadence_status']}")

    # Create a new person
    r = p("POST /people/ (new)", requests.post(f"{API}/people/", headers=headers, json={
        "first_name": "Test", "last_name": "Person", "phone": "+64220000001",
        "tier": "C", "relationship_type": "buyer"
    }))
    if r.status_code == 201:
        new_person_id = r.json()["id"]
        # Update
        r = p(f"PUT /people/{new_person_id}", requests.put(
            f"{API}/people/{new_person_id}", headers=headers,
            json={"notes": "Updated via test script"}
        ))
        # Delete
        r = p(f"DELETE /people/{new_person_id}", requests.delete(
            f"{API}/people/{new_person_id}", headers=headers
        ))

    # ── Properties ──
    print("\n── Properties ──")
    r = p("GET /properties/", requests.get(f"{API}/properties/", headers=headers))
    print(f"    Found {len(r.json())} properties")

    r = p("GET /properties/ (suburb=Papamoa)", requests.get(
        f"{API}/properties/?suburb=Papamoa", headers=headers
    ))
    print(f"    Papamoa properties: {len(r.json())}")

    r = p("GET /properties/1", requests.get(f"{API}/properties/1", headers=headers))

    # Create, update, delete
    r = p("POST /properties/ (new)", requests.post(f"{API}/properties/", headers=headers, json={
        "address": "99 Test Street, Tauranga", "suburb": "Tauranga", "bedrooms": 2, "bathrooms": 1
    }))
    if r.status_code == 201:
        new_prop_id = r.json()["id"]
        r = p(f"PUT /properties/{new_prop_id}", requests.put(
            f"{API}/properties/{new_prop_id}", headers=headers,
            json={"bedrooms": 3}
        ))
        r = p(f"DELETE /properties/{new_prop_id}", requests.delete(
            f"{API}/properties/{new_prop_id}", headers=headers
        ))

    # ── Activities ──
    print("\n── Activities ──")
    r = p("GET /activities/", requests.get(f"{API}/activities/", headers=headers))
    print(f"    Found {len(r.json())} activities")

    r = p("GET /activities/ (type=open_home_attendance)", requests.get(
        f"{API}/activities/?interaction_type=open_home_attendance", headers=headers
    ))
    print(f"    Open home attendances: {len(r.json())}")

    # Quick-log
    r = p("POST /activities/quick-log", requests.post(f"{API}/activities/quick-log", headers=headers, json={
        "person_id": 1, "interaction_type": "phone_call", "notes": "Quick test call"
    }))

    # Full create
    r = p("POST /activities/ (full)", requests.post(f"{API}/activities/", headers=headers, json={
        "person_id": 2, "property_id": 1, "interaction_type": "coffee_meeting",
        "notes": "Test meeting", "is_meaningful": True
    }))

    # ── Email Threads ──
    print("\n── Email Threads ──")
    r = p("GET /email-threads/", requests.get(f"{API}/email-threads/", headers=headers))
    print(f"    Found {len(r.json())} email threads")

    r = p("GET /email-threads/?person_id=1", requests.get(
        f"{API}/email-threads/?person_id=1", headers=headers
    ))

    # Test opt-in enforcement (person 4 = Mark Thompson, not a relationship asset)
    r = p("POST /email-threads/ (should fail: not opted in)", requests.post(
        f"{API}/email-threads/", headers=headers, json={
            "person_id": 4, "subject_line": "Test",
            "first_message_date": "2026-03-01T00:00:00Z",
            "last_message_date": "2026-03-01T00:00:00Z",
            "message_count": 1
        }
    ))
    if r.status_code == 403:
        print("    (Expected 403: opt-in required)")

    # ── Open Home Kiosk ──
    print("\n── Open Home Kiosk ──")
    # New person check-in
    r = p("POST /open-home/checkin (new person)", requests.post(
        f"{API}/open-home/checkin", headers=headers, json={
            "phone": "+64229999999", "first_name": "Kiosk", "last_name": "Visitor",
            "property_id": 1
        }
    ))
    if r.status_code == 201:
        checkin = r.json()
        print(f"    New person: {checkin['is_new_person']}, person_id={checkin['person_id']}")

    # Existing person check-in
    r = p("POST /open-home/checkin (existing person)", requests.post(
        f"{API}/open-home/checkin", headers=headers, json={
            "phone": "+64211234567", "first_name": "Sarah", "last_name": "Mitchell",
            "property_id": 2
        }
    ))
    if r.status_code == 201:
        checkin = r.json()
        print(f"    New person: {checkin['is_new_person']}, person_id={checkin['person_id']}")

    # ── Dashboard ──
    print("\n── Dashboard ──")
    r = p("GET /dashboard", requests.get(f"{API}/dashboard", headers=headers))
    if r.status_code == 200:
        dash = r.json()
        print(f"    A-tier drifting: {len(dash['a_tier_drifting'])} people")
        for d in dash['a_tier_drifting']:
            print(f"      - {d['first_name']} {d['last_name']}: {d['days_since_last_meaningful']} days")
        print(f"    Due for contact: {len(dash['due_for_contact_this_week'])} people")
        for d in dash['due_for_contact_this_week']:
            print(f"      - {d['first_name']} {d['last_name']}: {d['days_until_deadline']} days left")
        print(f"    Callbacks needed: {len(dash['open_home_callbacks_needed'])} people")
        for d in dash['open_home_callbacks_needed']:
            print(f"      - {d['first_name']} {d['last_name']}")
        print(f"    Repeat attendees: {len(dash['repeat_open_home_attendees'])} people")
        for d in dash['repeat_open_home_attendees']:
            print(f"      - {d['first_name']} {d['last_name']}: {d['attendance_count']} visits")
        print(f"    Cadence statuses: {len(dash['cadence_statuses'])} people")
        greens = sum(1 for c in dash['cadence_statuses'] if c['cadence_status'] == 'green')
        ambers = sum(1 for c in dash['cadence_statuses'] if c['cadence_status'] == 'amber')
        reds = sum(1 for c in dash['cadence_statuses'] if c['cadence_status'] == 'red')
        print(f"      Green: {greens}, Amber: {ambers}, Red: {reds}")

    # ── AI Suggestions ──
    print("\n── AI Suggestions ──")
    r = p("GET /ai/suggestions", requests.get(f"{API}/ai/suggestions", headers=headers))
    if r.status_code == 200:
        suggestions = r.json()["suggestions"]
        print(f"    Got {len(suggestions)} suggestions")
        for s in suggestions:
            print(f"      - [{s['suggestion_type']}] {s['title']} (confidence: {s['confidence']})")

    # ── Error handling ──
    print("\n── Error Handling ──")
    r = p("GET /people/99999 (not found)", requests.get(f"{API}/people/99999", headers=headers))
    if r.status_code == 404:
        print("    (Expected 404)")

    r = p("GET /people/ (no auth)", requests.get(f"{API}/people/"))
    if r.status_code == 401:
        print("    (Expected 401)")

    r = p("GET /people/ (bad token)", requests.get(f"{API}/people/", headers={"Authorization": "Bearer invalid"}))
    if r.status_code == 401:
        print("    (Expected 401)")

    print("\n" + "=" * 60)
    print("Test suite complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
