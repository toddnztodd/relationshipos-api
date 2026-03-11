"""Create context_nodes tables and context_node_suggestions."""
import psycopg2
import os

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://neondb_owner:npg_HvYka2b5nPOZ@ep-autumn-sound-a7om89h2-pooler.ap-southeast-2.aws.neon.tech/neondb?sslmode=require",
)

conn = psycopg2.connect(DB_URL)
conn.autocommit = True
cur = conn.cursor()

statements = [
    # Enum for context node type
    """
    DO $$ BEGIN
        CREATE TYPE context_node_type AS ENUM (
            'community', 'school', 'sport', 'location', 'interest', 'network', 'other'
        );
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
    """,

    # Enum for suggestion status (reuse pattern)
    """
    DO $$ BEGIN
        CREATE TYPE context_suggestion_status AS ENUM ('suggested', 'accepted', 'dismissed');
    EXCEPTION WHEN duplicate_object THEN NULL;
    END $$;
    """,

    # context_nodes table
    """
    CREATE TABLE IF NOT EXISTS context_nodes (
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL,
        type context_node_type NOT NULL DEFAULT 'other',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,

    # person_context_nodes join table
    """
    CREATE TABLE IF NOT EXISTS person_context_nodes (
        id SERIAL PRIMARY KEY,
        context_node_id INTEGER NOT NULL REFERENCES context_nodes(id) ON DELETE CASCADE,
        person_id INTEGER NOT NULL REFERENCES people(id) ON DELETE CASCADE,
        UNIQUE (context_node_id, person_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_pcn_context_node_id ON person_context_nodes(context_node_id);",
    "CREATE INDEX IF NOT EXISTS idx_pcn_person_id ON person_context_nodes(person_id);",

    # property_context_nodes join table
    """
    CREATE TABLE IF NOT EXISTS property_context_nodes (
        id SERIAL PRIMARY KEY,
        context_node_id INTEGER NOT NULL REFERENCES context_nodes(id) ON DELETE CASCADE,
        property_id INTEGER NOT NULL REFERENCES properties(id) ON DELETE CASCADE,
        UNIQUE (context_node_id, property_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_propcn_context_node_id ON property_context_nodes(context_node_id);",
    "CREATE INDEX IF NOT EXISTS idx_propcn_property_id ON property_context_nodes(property_id);",

    # relationship_group_context_nodes join table
    """
    CREATE TABLE IF NOT EXISTS relationship_group_context_nodes (
        id SERIAL PRIMARY KEY,
        context_node_id INTEGER NOT NULL REFERENCES context_nodes(id) ON DELETE CASCADE,
        relationship_group_id INTEGER NOT NULL,
        UNIQUE (context_node_id, relationship_group_id)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_rgcn_context_node_id ON relationship_group_context_nodes(context_node_id);",
    "CREATE INDEX IF NOT EXISTS idx_rgcn_rg_id ON relationship_group_context_nodes(relationship_group_id);",

    # context_node_suggestions table
    """
    CREATE TABLE IF NOT EXISTS context_node_suggestions (
        id SERIAL PRIMARY KEY,
        person_id INTEGER REFERENCES people(id) ON DELETE SET NULL,
        activity_id INTEGER REFERENCES activities(id) ON DELETE CASCADE,
        user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        suggested_name TEXT NOT NULL,
        suggested_type context_node_type NOT NULL DEFAULT 'other',
        status context_suggestion_status NOT NULL DEFAULT 'suggested',
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_cns_person_id ON context_node_suggestions(person_id);",
    "CREATE INDEX IF NOT EXISTS idx_cns_activity_id ON context_node_suggestions(activity_id);",
    "CREATE INDEX IF NOT EXISTS idx_cns_user_id ON context_node_suggestions(user_id);",
]

for sql in statements:
    try:
        cur.execute(sql)
        print(f"OK: {sql.strip()[:60]}...")
    except Exception as e:
        print(f"WARN: {e}")

cur.close()
conn.close()
print("\nAll context_nodes migrations complete.")
