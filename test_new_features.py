"""Test script for all 4 new backend features."""

import requests
import json
import sys

BASE = "http://localhost:8000/api/v1"
passed = 0
failed = 0


def test(name, response, expected_status):
    global passed, failed
    ok = response.status_code == expected_status
    if ok:
        passed += 1
        print(f"  PASS  {name} -> {response.status_code}")
    else:
        failed += 1
        print(f"  FAIL  {name} -> {response.status_code} (expected {expected_status})")
        try:
            print(f"        Body: {response.json()}")
        except Exception:
            print(f"        Body: {response.text[:200]}")
    return response


# ── Setup: register + login ──────────────────────────────────────────────────

print("\n=== SETUP ===")
r = requests.post(f"{BASE}/auth/register", json={
    "email": "test_features@test.com",
    "password": "password123",
    "full_name": "Test User",
})
if r.status_code == 409:
    print("  User already exists, logging in...")

r = requests.post(f"{BASE}/auth/login", json={
    "email": "test_features@test.com",
    "password": "password123",
})
token = r.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}
print(f"  Logged in. Token: {token[:20]}...")

# Create two people
r1 = requests.post(f"{BASE}/people/", json={
    "first_name": "Alice", "last_name": "Smith", "phone": "+6421111test",
    "tier": "A",
}, headers=headers)
person_a = r1.json()["id"]

r2 = requests.post(f"{BASE}/people/", json={
    "first_name": "Bob", "last_name": "Jones", "phone": "+6421112test",
    "tier": "B",
}, headers=headers)
person_b = r2.json()["id"]

# Create a property
r3 = requests.post(f"{BASE}/properties/", json={
    "address": "42 Test Street, Auckland",
    "suburb": "Ponsonby",
    "bedrooms": 3,
    "garaging": "Double",
    "section_size_sqm": 450.5,
    "perceived_value": "$1.2M",
}, headers=headers)
property_id = r3.json()["id"]
print(f"  Created person_a={person_a}, person_b={person_b}, property={property_id}")

# ── 1. Person Relationships ──────────────────────────────────────────────────

print("\n=== 1. PERSON RELATIONSHIPS ===")

r = test("Create relationship",
    requests.post(f"{BASE}/people/{person_a}/relationships", json={
        "person_b_id": person_b,
        "relationship_type": "Spouse",
        "notes": "Married 2020",
    }, headers=headers), 201)
rel_id = r.json()["id"]
print(f"        Relationship ID: {rel_id}, Names: {r.json()['person_a_name']} <-> {r.json()['person_b_name']}")

test("List relationships for person A",
    requests.get(f"{BASE}/people/{person_a}/relationships", headers=headers), 200)

test("List relationships for person B (should also show)",
    requests.get(f"{BASE}/people/{person_b}/relationships", headers=headers), 200)

test("Delete relationship",
    requests.delete(f"{BASE}/people/{person_a}/relationships/{rel_id}", headers=headers), 204)

test("List after delete (should be empty)",
    requests.get(f"{BASE}/people/{person_a}/relationships", headers=headers), 200)

# ── 2. Property-Person Links ─────────────────────────────────────────────────

print("\n=== 2. PROPERTY-PERSON LINKS ===")

r = test("Link person to property",
    requests.post(f"{BASE}/properties/{property_id}/people", json={
        "person_id": person_a,
        "role": "Vendor",
        "notes": "Primary vendor",
    }, headers=headers), 201)
link_id = r.json()["id"]
print(f"        Link ID: {link_id}, Person: {r.json()['person_name']}, Property: {r.json()['property_address']}")

r = test("Link second person",
    requests.post(f"{BASE}/properties/{property_id}/people", json={
        "person_id": person_b,
        "role": "Buyer Enquiry",
    }, headers=headers), 201)
link_id_2 = r.json()["id"]

r = test("List people for property",
    requests.get(f"{BASE}/properties/{property_id}/people", headers=headers), 200)
print(f"        People linked: {len(r.json())}")

r = test("List properties for person",
    requests.get(f"{BASE}/people/{person_a}/properties", headers=headers), 200)
print(f"        Properties linked: {len(r.json())}")

test("Unlink person from property",
    requests.delete(f"{BASE}/properties/{property_id}/people/{link_id_2}", headers=headers), 204)

# ── 3. Important Dates (v2) ──────────────────────────────────────────────────

print("\n=== 3. IMPORTANT DATES (v2) ===")

r = test("Create birthday",
    requests.post(f"{BASE}/people/{person_a}/important-dates", json={
        "label": "Birthday",
        "date": "1985-06-15",
        "is_recurring": True,
        "notes": "Loves chocolate cake",
    }, headers=headers), 201)
date_id = r.json()["id"]
print(f"        Date ID: {date_id}, Label: {r.json()['label']}, Date: {r.json()['date']}")

r = test("Create anniversary",
    requests.post(f"{BASE}/people/{person_a}/important-dates", json={
        "label": "Wedding Anniversary",
        "date": "2020-03-20",
        "is_recurring": True,
    }, headers=headers), 201)

r = test("List dates for person",
    requests.get(f"{BASE}/people/{person_a}/important-dates", headers=headers), 200)
print(f"        Dates: {len(r.json())}")

r = test("Update date",
    requests.put(f"{BASE}/people/{person_a}/important-dates/{date_id}", json={
        "notes": "Loves chocolate cake and red wine",
    }, headers=headers), 200)
print(f"        Updated notes: {r.json()['notes']}")

test("Delete date",
    requests.delete(f"{BASE}/people/{person_a}/important-dates/{date_id}", headers=headers), 204)

# ── 4. Listing Checklist ─────────────────────────────────────────────────────

print("\n=== 4. LISTING CHECKLIST ===")

r = test("Create checklist items (batch)",
    requests.post(f"{BASE}/properties/{property_id}/checklist", json=[
        {"phase": "Pre-Listing", "step_name": "CMA completed", "sort_order": 1, "sale_method": "Auction"},
        {"phase": "Pre-Listing", "step_name": "Photography booked", "sort_order": 2, "sale_method": "Auction"},
        {"phase": "Marketing", "step_name": "Signboard installed", "sort_order": 3, "sale_method": "Auction"},
        {"phase": "Auction", "step_name": "Auction date confirmed", "sort_order": 4, "sale_method": "Auction"},
    ], headers=headers), 201)
items = r.json()
print(f"        Created {len(items)} items")
item_id = items[0]["id"]

r = test("List checklist",
    requests.get(f"{BASE}/properties/{property_id}/checklist", headers=headers), 200)
print(f"        Items: {len(r.json())}")

r = test("Toggle item complete",
    requests.patch(f"{BASE}/properties/{property_id}/checklist/{item_id}", json={
        "is_completed": True,
    }, headers=headers), 200)
print(f"        Completed: {r.json()['is_completed']}, completed_at: {r.json()['completed_at']}")

r = test("Add notes to item",
    requests.patch(f"{BASE}/properties/{property_id}/checklist/{item_id}", json={
        "notes": "Done by Todd on Monday",
    }, headers=headers), 200)

test("Delete single item",
    requests.delete(f"{BASE}/properties/{property_id}/checklist/{items[3]['id']}", headers=headers), 204)

r = test("List after delete",
    requests.get(f"{BASE}/properties/{property_id}/checklist", headers=headers), 200)
print(f"        Items remaining: {len(r.json())}")

test("Clear all checklist items",
    requests.delete(f"{BASE}/properties/{property_id}/checklist", headers=headers), 204)

r = test("List after clear",
    requests.get(f"{BASE}/properties/{property_id}/checklist", headers=headers), 200)
print(f"        Items remaining: {len(r.json())}")

# ── 5. New fields on existing models ─────────────────────────────────────────

print("\n=== 5. NEW FIELDS ON EXISTING MODELS ===")

r = test("Update person with AML fields",
    requests.put(f"{BASE}/people/{person_a}", json={
        "drivers_licence_number": "AB123456",
        "aml_status": "verified",
        "perceived_value": "$800K buyer",
    }, headers=headers), 200)
print(f"        AML status: {r.json()['aml_status']}, Licence: {r.json()['drivers_licence_number']}")

r = test("Update property with new fields",
    requests.put(f"{BASE}/properties/{property_id}", json={
        "garaging": "Triple",
        "house_size_sqm": 220.0,
        "land_value": "$650,000",
    }, headers=headers), 200)
print(f"        Garaging: {r.json()['garaging']}, House size: {r.json()['house_size_sqm']}")

# ── Summary ──────────────────────────────────────────────────────────────────

print(f"\n{'='*60}")
print(f"RESULTS: {passed} passed, {failed} failed out of {passed + failed} tests")
print(f"{'='*60}")
sys.exit(0 if failed == 0 else 1)
