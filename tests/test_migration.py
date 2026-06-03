"""
TDD Tests for DB schema migration

These tests verify that the migration SQL creates the expected schema
and that seed data is correct.

Run: pytest shared-ui/tests/test_migration.py -v
Requires: PostgreSQL running locally with DB 'r0gr'
"""
import pytest
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ──────────────────────────────────────────────
# DB Connection helpers
# ──────────────────────────────────────────────

def get_db_connection():
    """Get a connection to the test database."""
    # Try to get password from centralized helper
    password = ''
    try:
        sys.path.insert(0, '/home/roger/.hermes/scripts')
        import db_password
        password = db_password.get_db_password()
    except ImportError:
        pass
    
    return psycopg2.connect(
        host='localhost',
        port='5432',
        dbname='r0gr',
        user='r0gr',
        password=password,
        cursor_factory=RealDictCursor
    )


# ──────────────────────────────────────────────
# Tests for schema existence
# ──────────────────────────────────────────────

class TestSchemaExists:
    def test_ui_schema_exists(self):
        """The 'ui' schema should exist after migration."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT schema_name 
                    FROM information_schema.schemata 
                    WHERE schema_name = 'ui'
                """)
                result = cur.fetchone()
                assert result is not None, "Schema 'ui' does not exist"
                assert result['schema_name'] == 'ui'
        finally:
            conn.close()

    def test_templates_table_exists(self):
        """The ui.templates table should exist."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'ui' AND table_name = 'templates'
                """)
                result = cur.fetchone()
                assert result is not None, "Table 'ui.templates' does not exist"
        finally:
            conn.close()

    def test_assignments_table_exists(self):
        """The ui.assignments table should exist."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'ui' AND table_name = 'assignments'
                """)
                result = cur.fetchone()
                assert result is not None, "Table 'ui.assignments' does not exist"
        finally:
            conn.close()

    def test_audit_log_table_exists(self):
        """The ui.audit_log table should exist."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'ui' AND table_name = 'audit_log'
                """)
                result = cur.fetchone()
                assert result is not None, "Table 'ui.audit_log' does not exist"
        finally:
            conn.close()


# ──────────────────────────────────────────────
# Tests for table structure
# ──────────────────────────────────────────────

class TestTableStructure:
    def test_templates_columns(self):
        """ui.templates should have the expected columns."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type 
                    FROM information_schema.columns 
                    WHERE table_schema = 'ui' AND table_name = 'templates'
                    ORDER BY ordinal_position
                """)
                columns = {row['column_name']: row['data_type'] for row in cur.fetchall()}
                
                assert 'template_key' in columns
                assert 'version' in columns
                assert 'name' in columns
                assert 'family' in columns
                assert 'tokens' in columns  # JSONB
                assert 'assets' in columns   # JSONB
                assert 'menu' in columns   # JSONB
                assert 'metadata' in columns # JSONB
                assert 'created_at' in columns
        finally:
            conn.close()

    def test_templates_primary_key(self):
        """ui.templates should have a composite primary key."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT ccu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.constraint_column_usage ccu 
                        ON tc.constraint_name = ccu.constraint_name
                    WHERE tc.table_schema = 'ui' 
                      AND tc.table_name = 'templates'
                      AND tc.constraint_type = 'PRIMARY KEY'
                    ORDER BY ccu.column_name
                """)
                columns = [row['column_name'] for row in cur.fetchall()]
                assert 'template_key' in columns
                assert 'version' in columns
        finally:
            conn.close()

    def test_assignments_foreign_key(self):
        """ui.assignments should have a foreign key to ui.templates."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tc.constraint_name, kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                    WHERE tc.table_schema = 'ui'
                      AND tc.table_name = 'assignments'
                      AND tc.constraint_type = 'FOREIGN KEY'
                """)
                result = cur.fetchone()
                assert result is not None, "No foreign key constraint found"
        finally:
            conn.close()


# ──────────────────────────────────────────────
# Tests for seed data
# ──────────────────────────────────────────────

class TestSeedData:
    def test_agentworx_template_exists(self):
        """The agentworx template should exist with version 1."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT template_key, version, name, family
                    FROM ui.templates
                    WHERE template_key = 'agentworx' AND version = 1
                """)
                result = cur.fetchone()
                assert result is not None, "agentworx template not found"
                assert result['name'] == 'agentworx'
                assert result['family'] == 'agentworx'
        finally:
            conn.close()

    def test_r0gr_template_exists(self):
        """The r0gr template should exist with version 1."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT template_key, version, name, family
                    FROM ui.templates
                    WHERE template_key = 'r0gr' AND version = 1
                """)
                result = cur.fetchone()
                assert result is not None, "r0gr template not found"
                assert result['name'] == 'r0gr'
                assert result['family'] == 'r0gr'
        finally:
            conn.close()

    def test_agentworx_colors(self):
        """agentworx template should have correct accent color."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tokens->'colors'->>'accent' as accent
                    FROM ui.templates
                    WHERE template_key = 'agentworx' AND version = 1
                """)
                result = cur.fetchone()
                assert result is not None
                assert result['accent'] == '#83ce00', f"Expected #83ce00, got {result['accent']}"
        finally:
            conn.close()

    def test_r0gr_colors(self):
        """r0gr template should have correct accent color."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tokens->'colors'->>'accent' as accent
                    FROM ui.templates
                    WHERE template_key = 'r0gr' AND version = 1
                """)
                result = cur.fetchone()
                assert result is not None
                assert result['accent'] == '#f09a3a', f"Expected #f09a3a, got {result['accent']}"
        finally:
            conn.close()

    def test_all_assignments_exist(self):
        """All 4 app assignments should exist."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT app_key, domain, template_key, version
                    FROM ui.assignments
                    WHERE active = TRUE
                    ORDER BY app_key
                """)
                rows = cur.fetchall()
                apps = {row['app_key'] for row in rows}
                
                expected = {'audit-viewer', 'agentworx-content', 'console-hub', 'fitness-dashboard'}
                assert apps == expected, f"Missing apps: {expected - apps}"
        finally:
            conn.close()

    def test_audit_viewer_assignment(self):
        """audit-viewer should be assigned to agentworx template."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT template_key, version
                    FROM ui.assignments
                    WHERE app_key = 'audit-viewer' AND active = TRUE
                """)
                result = cur.fetchone()
                assert result is not None
                assert result['template_key'] == 'agentworx'
                assert result['version'] >= 1
        finally:
            conn.close()

    def test_console_hub_assignment(self):
        """console-hub should be assigned to r0gr template."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT template_key, version
                    FROM ui.assignments
                    WHERE app_key = 'console-hub' AND active = TRUE
                """)
                result = cur.fetchone()
                assert result is not None
                assert result['template_key'] == 'r0gr'
                assert result['version'] >= 1
        finally:
            conn.close()


# ──────────────────────────────────────────────
# Tests for JSON structure
# ──────────────────────────────────────────────

class TestJSONStructure:
    def test_agentworx_has_all_token_categories(self):
        """agentworx template should have all expected token categories."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT tokens
                    FROM ui.templates
                    WHERE template_key = 'agentworx' AND version = 1
                """)
                result = cur.fetchone()
                assert result is not None
                tokens = result['tokens']
                assert 'colors' in tokens
                assert 'fonts' in tokens
                assert 'spacing' in tokens
                assert 'radii' in tokens
                assert 'shadows' in tokens
                assert 'transitions' in tokens
        finally:
            conn.close()

    def test_agentworx_menu_config(self):
        """agentworx template should have menu configuration."""
        conn = get_db_connection()
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT menu->>'style' as style, menu->>'position' as position
                    FROM ui.templates
                    WHERE template_key = 'agentworx' AND version = 1
                """)
                result = cur.fetchone()
                assert result is not None
                assert result['style'] == 'horizontal'
                assert result['position'] == 'top'
        finally:
            conn.close()


# ──────────────────────────────────────────────
# Cleanup helper (for development)
# ──────────────────────────────────────────────

def cleanup_test_data():
    """Remove test data. Use with caution!"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM ui.audit_log")
            cur.execute("DELETE FROM ui.assignments")
            cur.execute("DELETE FROM ui.templates")
            conn.commit()
    finally:
        conn.close()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
