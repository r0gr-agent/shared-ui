# UI Template System (shared-ui)

Centralized database-backed UI template engine for all r0gr.de services.

## Overview

This module provides a shared template system that allows dynamic theming across all Flask backends via CSS Custom Properties (variables). Templates and their assignments to applications are stored in PostgreSQL, enabling runtime theme switching without code changes.

## Architecture

### Database Schema

**ui.templates** — Stores theme definitions
- `template_name` (PK) — e.g., `'r0gr'`, `'agentworx'`
- `family` — Design family grouping
- `tokens` (JSONB) — CSS custom property values (colors, fonts, spacing)
- `is_active` — Whether the template is available for use

**ui.assignments** — Maps apps to templates
- `app_name` (PK) — e.g., `'audit-viewer'`, `'agentworx-content'`
- `template_name` (FK) — The active template for this app
- `updated_at` — Last change timestamp

**ui.audit_log** — Tracks all template changes for accountability

### Module: `ui_templates.py`

#### `TemplateConfig`
Represents a single template with token validation and CSS generation.

#### `TemplateManager`
Handles database access with two-level caching:
1. **In-memory cache** — 5-minute TTL per process
2. **Database fallback** — Hardcoded defaults if DB is unreachable

Methods:
- `get_template(app_name)` → Returns `TemplateConfig` for the assigned template
- `get_all_templates()` → List all active templates
- `assign_template(app_name, template_name)` → Update assignment + log
- `render_css_variables(template)` → Generate `<style>` block with `:root` variables

#### `get_fallback_template(family)`
Returns a hardcoded fallback template (no DB required). Used for:
- Bootstrapping before DB is available
- Hermes auth library (shared across apps)
- Emergency fallback when DB is down

## Usage in Flask Apps

### 1. Import the module

```python
import sys
sys.path.insert(0, "/home/roger/services/shared-ui")
from ui_templates import TemplateManager, get_fallback_template
```

### 2. Inject CSS into every response

```python
@app.context_processor
def inject_ui_css():
    manager = TemplateManager()
    template = manager.get_template('your-app-name')
    if template is None:
        template = get_fallback_template('r0gr')
    return {'ui_css_block': manager.render_css_variables(template)}
```

### 3. Use CSS variables in your styles

```css
body {
  background: var(--color-bg-primary);
  color: var(--color-text-primary);
}
```

## Auth Pages

The `hermes_auth_lib` module uses this system for login/TOTP pages. By default it loads the `'hermes-auth'` template (falling back to `'r0gr'`).

Apps can override this by passing `template_name` to render functions:

```python
from hermes_auth_lib import render_pw_page

# Use the app's own theme for auth pages
render_pw_page(..., template_name='r0gr')  # for audit-viewer
render_pw_page(..., template_name='agentworx')  # for agentworx-content
```

## Testing

Run the shared UI tests:

```bash
cd /home/roger/services/shared-ui
python -m pytest tests/ -v
```

Tests cover:
- Template validation (62 tests)
- Database integration (17 tests)
- CSS generation (14 tests)

## Available Templates

| Template | Family | Primary Color | Used By |
|----------|--------|---------------|---------|
| `r0gr` | r0gr | Orange (#f09a3a) | audit-viewer, console-hub, fitness-dashboard |
| `agentworx` | agentworx | Green (#00cc77) | agentworx-content |

## Adding a New Template

1. Insert into `ui.templates` with desired tokens
2. Assign to app via `ui.assignments`
3. The change is live immediately (next request picks it up due to cache TTL)

## Troubleshooting

**Auth pages show wrong colors:**
- Check that the app passes `template_name` to render functions
- Verify `ui.assignments` has the correct mapping

**CSS variables not applied:**
- Ensure `inject_ui_css()` is registered as context_processor
- Check browser dev tools for `--color-*` variables in `:root`
