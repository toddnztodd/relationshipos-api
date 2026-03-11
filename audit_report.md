# Backend Schema Audit Report

**Date:** 2026-03-11
**Mode:** Read-Only Analysis

This report audits the current state of the RelationshipOS backend database schema against the specified architectural requirements for the Relate project. No changes have been made to the codebase or database.

---

### 1. Current State Analysis

An analysis of the existing SQLAlchemy models (`app/models/models.py`) and Pydantic schemas (`app/schemas/`) reveals the following structure relevant to the audit questions.

#### Activity Model (`activities` table)

The `Activity` model is the central record for interactions. Its current structure is as follows:

| Field | Data Type | Nullable | Requirement Match |
| :--- | :--- | :--- | :--- |
| `id` | Integer (PK) | No | **Yes** |
| `user_id` | Integer (FK) | No | **Yes** (as `created_by`) |
| `person_id` | Integer (FK) | No | **Partial** (Requirement is nullable) |
| `property_id` | Integer (FK) | Yes | **Yes** |
| `interaction_type` | Enum | No | **Partial** (as `activity_type`, enum needs expansion) |
| `date` | DateTime | No | **Yes** (as `created_at`) |
| `notes` | Text | Yes | **Yes** (as `note_content`/`transcription`) |
| `source` | String(100) | Yes | **Yes** |
| `created_at` | DateTime | No | **Yes** |

#### People & Relationships (`people` table)

The `Person` model does not contain a direct `relationship_group_id`. However, a separate `PersonRelationship` model exists, creating a many-to-many link between two `Person` records. This serves the functional purpose of grouping contacts.

#### Interaction History Tables

Besides the primary `activities` table, the following models and their corresponding tables also store interaction-like data:

- **`EmailThread`**: Captures email conversations, including subject, message count, and body. This functions as a separate interaction history for emails.
- **`DoorKnockSession`**: Records door knocking events, including address, notes, and marketing materials left. This is another distinct interaction history.
- **`WeeklyTracking`**: Stores aggregate weekly counts of activities (e.g., `phone_calls_daily`, `connects_count`). It does not store individual interactions and is therefore not in conflict with the single timeline rule.

---

### 2. Gaps & Conflicts Found

Based on the analysis, the following gaps and conflicts with the specified architecture were identified.

1.  **Activity-Contact Link is Not Nullable**: The `activities.person_id` column is non-nullable (`nullable=False`). The requirement is for this field to be optional to allow for activities that are linked only to a property (e.g., a note about a listing) but not a specific person.

2.  **Activity Type Enum is Limited**: The current `InteractionType` enum is missing several required values for the Voice Capture feature, such as `voice_note`, `meeting_note`, `appraisal_note`, and `system_event`.

3.  **No Direct Household Grouping Field**: The `people` table lacks a simple `relationship_group_id`. While the existing `PersonRelationship` table is more flexible, it may be more complex to query for simple household groups compared to a shared ID.

4.  **Multiple Interaction History Tables**: The existence of `EmailThread` and `DoorKnockSession` tables conflicts directly with the principle of a single, unified activity timeline. All interactions, regardless of their origin, should ideally be stored in the `activities` table with a corresponding `activity_type`.

---

### 3. Recommended Minimal Changes

To align the schema with the architectural requirements for Voice Capture Phase 1, the following minimal, non-breaking changes are recommended.

1.  **Make `activities.person_id` Nullable**: Modify the `person_id` column in the `activities` table to allow `NULL` values. This is the most critical change to support property-only activities.
    - **SQL:** `ALTER TABLE activities ALTER COLUMN person_id DROP NOT NULL;`

2.  **Expand the `InteractionType` Enum**: Add the new, required activity types to the enum definition in `app/models/models.py`. This is a straightforward code change.
    - **Add:** `voice_note`, `meeting_note`, `appraisal_note`, `conversation_update`, `system_event`.

3.  **Consolidate Interaction Tables (Long-Term)**: For future phases, a data migration should be planned to move records from `email_threads` and `door_knock_sessions` into the `activities` table. The original tables can then be deprecated and removed. This is a larger effort and is **not** required for Voice Capture Phase 1 to proceed.

---

### 4. Conclusion & Next Steps

**Voice Capture Phase 1 should wait for a small schema update before proceeding.**

The most immediate blocker is the non-nullable `activities.person_id` field. Making this field nullable is a simple, low-risk change that is essential for creating activities that may not be linked to a contact, which is a core requirement.

Once that single database column is updated and the `InteractionType` enum is expanded in the code, development on the Voice Capture feature can begin without being blocked by larger architectural consolidation efforts.
