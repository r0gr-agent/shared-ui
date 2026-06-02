#!/usr/bin/env python3
"""Emergency migration: create v5 templates and switch console to agentworx."""
import sys
sys.path.insert(0, '/home/roger/services/shared-ui')
from ui_templates import _get_db_connection
import psycopg2

# Read r0gr v4 as base for agentworx v5 (console look)
conn = _get_db_connection()
cur = conn.cursor()

# Fetch r0gr v4
cur.execute("SELECT * FROM ui.templates WHERE template_key='r0gr' AND version=4")
r0gr = cur.fetchone()

# Fetch agentworx v4 for assets
cur.execute("SELECT * FROM ui.templates WHERE template_key='agentworx' AND version=4")
agentworx = cur.fetchone()

# Build agentworx v5: r0gr colors + agentworx assets + components
agentworx_v5_tokens = dict(r0gr['tokens'])
agentworx_v5_tokens['components'] = {
    "button-primary-bg": "var(--color-accent)",
    "button-primary-color": "var(--color-accent-contrast)",
    "button-primary-hover": "var(--color-accent-hover)",
    "button-secondary-bg": "transparent",
    "button-secondary-color": "var(--color-accent)",
    "button-secondary-border": "1px solid var(--color-border)",
    "button-secondary-hover-bg": "var(--derived-accent-8)",
    "button-danger-bg": "var(--color-error)",
    "button-danger-color": "#fff",
    "button-danger-hover": "#ff6666",
    "button-ghost-bg": "transparent",
    "button-ghost-color": "var(--color-text-secondary)",
    "button-ghost-hover-color": "var(--color-text-primary)",
    "card-bg": "var(--color-bg-surface)",
    "card-border": "1px solid var(--color-border)",
    "card-radius": "var(--radius-md)",
    "card-padding": "20px",
    "input-bg": "var(--color-bg-primary)",
    "input-border": "1px solid var(--color-border)",
    "input-focus-border": "var(--color-accent)",
    "modal-overlay": "rgba(0,0,0,0.7)",
    "modal-radius": "var(--radius-md)",
    "modal-padding": "24px",
    "table-header-bg": "var(--color-bg-elevated)",
    "table-row-hover": "var(--derived-accent-5)",
    "tag-radius": "var(--radius-sm)",
    "badge-radius": "var(--radius-sm)",
    "kpi-bg": "var(--color-bg-surface)",
    "kpi-border": "1px solid var(--color-border)",
    "kpi-radius": "var(--radius-md)",
    "kpi-padding": "20px",
    "range-btn-active-bg": "var(--derived-accent-10)",
    "range-btn-active-color": "var(--color-accent)",
    "range-btn-active-border": "var(--color-accent)",
    "filter-pill-active-bg": "var(--derived-accent-10)",
    "filter-pill-active-color": "var(--color-accent)",
    "filter-pill-active-border": "var(--color-accent)",
    "nav-item-padding": "8px 14px",
    "nav-item-radius": "6px",
    "nav-item-font-size": "0.85em",
    "section-header-font-size": "0.85em",
    "section-header-color": "var(--color-text-secondary)",
    "section-header-transform": "uppercase",
    "section-header-spacing": "0.08em",
    "section-header-weight": "600"
}

agentworx_v5_assets = {
    "logo": {
        "url": "https://agentworx.agency/assets/images/agentworx-logo-white.png",
        "alt": "agentworx",
        "height": "28px"
    },
    "favicon": {
        "url": "https://agentworx.agency/assets/favicon/favicon.ico",
        "type": "image/x-icon"
    }
}

agentworx_v5_metadata = {
    "author": "system",
    "created": "2026-06-02",
    "description": "Agentworx Unified Design System (aligned with console)",
    "page_title": "agentworx Console",
    "brand_name": "agentworx"
}

# Insert agentworx v5
cur.execute("""
    INSERT INTO ui.templates (template_key, version, name, family, tokens, assets, menu, metadata)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""", (
    'agentworx', 5, 'Agentworx Unified', 'agentworx',
    psycopg2.extras.Json(agentworx_v5_tokens),
    psycopg2.extras.Json(agentworx_v5_assets),
    psycopg2.extras.Json(dict(r0gr['menu'])),
    psycopg2.extras.Json(agentworx_v5_metadata)
))

# Build r0gr v5: r0gr v4 + components
r0gr_v5_tokens = dict(r0gr['tokens'])
r0gr_v5_tokens['components'] = dict(agentworx_v5_tokens['components'])

r0gr_v5_assets = {
    "logo": {
        "url": None,
        "alt": "r0gr",
        "height": "36px",
        "border-radius": "50%",
        "border": "2px solid var(--color-accent)"
    },
    "favicon": {
        "url": "/favicon.ico",
        "type": "image/x-icon"
    }
}

r0gr_v5_metadata = {
    "author": "system",
    "created": "2026-06-02",
    "description": "r0gr Unified Design System",
    "page_title": "r0gr Hub",
    "brand_name": "r0gr"
}

# Insert r0gr v5
cur.execute("""
    INSERT INTO ui.templates (template_key, version, name, family, tokens, assets, menu, metadata)
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
""", (
    'r0gr', 5, 'r0gr Unified', 'r0gr',
    psycopg2.extras.Json(r0gr_v5_tokens),
    psycopg2.extras.Json(r0gr_v5_assets),
    psycopg2.extras.Json(dict(r0gr['menu'])),
    psycopg2.extras.Json(r0gr_v5_metadata)
))

# Update assignments: console-hub -> agentworx v5
# audit-viewer -> agentworx v5
# agentworx-content -> agentworx v5
# fitness-dashboard -> r0gr v5
cur.execute("UPDATE ui.assignments SET template_key='agentworx', version=5 WHERE app_key='console-hub'")
cur.execute("UPDATE ui.assignments SET version=5 WHERE app_key='audit-viewer'")
cur.execute("UPDATE ui.assignments SET version=5 WHERE app_key='agentworx-content'")
cur.execute("UPDATE ui.assignments SET template_key='r0gr', version=5 WHERE app_key='fitness-dashboard'")

conn.commit()
conn.close()
print("Migration complete.")
print("Assignments:")
print("  console-hub -> agentworx v5")
print("  audit-viewer -> agentworx v5")
print("  agentworx-content -> agentworx v5")
print("  fitness-dashboard -> r0gr v5")
