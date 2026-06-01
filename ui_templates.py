"""
Shared UI Template System for r0gr / agentworx Backends.

Provides:
- Database-backed design tokens (colors, fonts, spacing, etc.)
- CSS Custom Property generation
- Template loading with caching
- Validation of all token values
- JSON API for external agents

Usage:
    from ui_templates import (
        TemplateConfig, TemplateManager, TemplateCache,
        render_css_variables, validate_css_variables, get_fallback_template
    )
"""

import os
import re
import json
import time
from typing import Dict, Optional, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading

# Try to import psycopg2, but allow fallback for testing
try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False


# ──────────────────────────────────────────────
# Configuration & Constants
# ──────────────────────────────────────────────

DEFAULT_CACHE_TTL = 300  # 5 minutes

ALLOWED_COLOR_PATTERN = re.compile(
    r'^(#[0-9a-fA-F]{3,8}|rgba?\([^)]+\)|hsla?\([^)]+\)|transparent|inherit)$'
)

ALLOWED_FONT_PATTERN = re.compile(
    r"^[\w\s,'\-()]+$"
)

ALLOWED_SIZE_PATTERN = re.compile(
    r'^(\d+(\.\d+)?(px|em|rem|%|vh|vw|ex|ch|cm|mm|in|pt|pc)|0|auto|inherit)$'
)

ALLOWED_URL_PATTERN = re.compile(
    r'^(https?://[^\s<>"{}|\\^`\[\]]+|[/][^\s<>"{}|\\^`\[\]]*)$'
)


# ──────────────────────────────────────────────
# Data Classes
# ──────────────────────────────────────────────

@dataclass
class TemplateConfig:
    """Validated, immutable template configuration."""
    template_key: str
    version: int
    name: str
    family: str
    tokens: Dict[str, Any] = field(default_factory=dict)
    assets: Dict[str, Any] = field(default_factory=dict)
    menu: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_color(self, key: str, fallback: str = '') -> str:
        """Get color value by key, e.g. 'accent', 'bg-primary'."""
        colors = self.tokens.get('colors', {})
        return colors.get(key, fallback)

    def get_font(self, key: str = 'primary') -> str:
        """Get font value by key."""
        fonts = self.tokens.get('fonts', {})
        return fonts.get(key, 'system-ui, sans-serif')

    def get_spacing(self, key: str = 'md') -> str:
        """Get spacing value by key."""
        spacing = self.tokens.get('spacing', {})
        return spacing.get(key, '16px')

    def get_logo_url(self) -> Optional[str]:
        """Get logo URL from assets."""
        logo = self.assets.get('logo', {})
        return logo.get('url')


# ──────────────────────────────────────────────
# Validation
# ──────────────────────────────────────────────

class TokenValidator:
    """Validates all design token values."""

    @staticmethod
    def validate_color(value: str) -> bool:
        return bool(ALLOWED_COLOR_PATTERN.match(value))

    @staticmethod
    def validate_font(value: str) -> bool:
        return bool(ALLOWED_FONT_PATTERN.match(value))

    @staticmethod
    def validate_size(value: str) -> bool:
        return bool(ALLOWED_SIZE_PATTERN.match(value))

    @staticmethod
    def validate_url(value: str) -> bool:
        if not value:
            return True
        return bool(ALLOWED_URL_PATTERN.match(value))


def validate_css_variables(variables: Dict[str, Any]) -> List[str]:
    """
    Validate CSS variable values. Returns list of error messages (empty if valid).
    """
    errors = []
    validator = TokenValidator()

    # Validate colors
    colors = variables.get('colors', {})
    for key, value in colors.items():
        if not validator.validate_color(str(value)):
            errors.append(f"Invalid color.{key}: {value}")

    # Validate fonts
    fonts = variables.get('fonts', {})
    for key, value in fonts.items():
        if 'size' in key or 'weight' in key or 'height' in key:
            continue  # Numeric values are OK
        if not validator.validate_font(str(value)):
            errors.append(f"Invalid font.{key}: {value}")

    # Validate spacing
    spacing = variables.get('spacing', {})
    for key, value in spacing.items():
        if not validator.validate_size(str(value)):
            errors.append(f"Invalid spacing.{key}: {value}")

    # Validate radii
    radii = variables.get('radii', {})
    for key, value in radii.items():
        if not validator.validate_size(str(value)) and str(value) not in ('0', '9999px'):
            errors.append(f"Invalid radii.{key}: {value}")

    # Validate z-index
    z_index = variables.get('z-index', {})
    for key, value in z_index.items():
        if not str(value).isdigit():
            errors.append(f"Invalid z-index.{key}: {value}")

    return errors


# ──────────────────────────────────────────────
# Cache
# ──────────────────────────────────────────────

class TemplateCache:
    """Thread-safe cache with TTL."""

    def __init__(self, ttl_seconds: int = DEFAULT_CACHE_TTL):
        self._cache: Dict[str, tuple] = {}  # key -> (config, expiry_time)
        self._lock = threading.RLock()
        self._ttl = ttl_seconds

    def get(self, key: str) -> Optional[TemplateConfig]:
        with self._lock:
            if key in self._cache:
                config, expiry = self._cache[key]
                if datetime.now() < expiry:
                    return config
                del self._cache[key]
            return None

    def set(self, key: str, config: TemplateConfig):
        with self._lock:
            self._cache[key] = (config, datetime.now() + timedelta(seconds=self._ttl))

    def invalidate(self, key: Optional[str] = None):
        with self._lock:
            if key:
                # Remove all entries starting with this key prefix
                keys_to_remove = [k for k in self._cache if k.startswith(key)]
                for k in keys_to_remove:
                    del self._cache[k]
            else:
                self._cache.clear()

    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                'entries': len(self._cache),
                'ttl_seconds': self._ttl
            }


# ──────────────────────────────────────────────
# CSS Rendering
# ──────────────────────────────────────────────

def render_css_variables(config: TemplateConfig, selector: str = ':root') -> str:
    """
    Generate CSS custom properties from template configuration.

    Output example:
        :root {
          --color-accent: #83ce00;
          --color-bg: #1a1d21;
          --font-primary: system-ui, ...;
          --spacing-md: 16px;
        }
    """
    lines = [f"{selector} {{"]

    def _flatten_dict(data: dict, prefix: str = ''):
        singular_map = {
            'colors': 'color',
            'fonts': 'font',
            'radii': 'radius',
            'shadows': 'shadow',
            'transitions': 'transition',
        }
        for key, value in data.items():
            mapped_key = singular_map.get(key, key)
            full_key = f"{prefix}-{mapped_key}" if prefix else mapped_key
            if isinstance(value, dict):
                _flatten_dict(value, full_key)
            elif isinstance(value, str):
                var_name = f"--{full_key}"
                lines.append(f"  {var_name}: {value};")

    if config.tokens:
        _flatten_dict(config.tokens)

    # Add logo URL as CSS variable
    logo_url = config.get_logo_url()
    if logo_url:
        lines.append(f"  --asset-logo-url: url('{logo_url}');")

    lines.append("}")
    return "\n".join(lines)


# ──────────────────────────────────────────────
# Fallback Templates
# ──────────────────────────────────────────────

DEFAULT_TEMPLATES = {
    'agentworx': TemplateConfig(
        template_key='agentworx',
        version=0,
        name='Agentworx Default (Offline)',
        family='agentworx',
        tokens={
            'colors': {
                'accent': '#83ce00',
                'bg': '#1a1d21',
                'bg-surface': '#21252a',
                'border': '#2a2f35',
                'text-primary': '#c4c9ce',
                'text-secondary': '#6a7078',
                'warn': '#d29922',
                'error': '#e0555a',
                'success': '#6a9955',
                'info': '#539bf5',
            },
            'fonts': {
                'primary': 'system-ui, -apple-system, sans-serif',
                'size-base': '14px'
            },
            'spacing': {'md': '16px', 'lg': '24px'},
            'radii': {'md': '6px'},
            'shadows': {'md': '0 2px 8px rgba(0,0,0,0.3)'}
        },
        assets={'logo': {'url': 'https://agentworx.agency/assets/images/agentworx-logo-white.png'}},
        menu={'style': 'horizontal', 'position': 'top'}
    ),
    'r0gr': TemplateConfig(
        template_key='r0gr',
        version=0,
        name='r0gr Default (Offline)',
        family='r0gr',
        tokens={
            'colors': {
                'accent': '#f09a3a',
                'bg': '#0f0a08',
                'bg-surface': '#1a1410',
                'border': '#2a1f15',
                'text-primary': '#c4c9ce',
                'text-secondary': '#8a7f70',
                'warn': '#e0a030',
                'error': '#ff5544',
                'success': '#00cc77',
                'info': '#5aafdf',
            },
            'fonts': {
                'primary': 'system-ui, -apple-system, sans-serif',
                'size-base': '14px'
            },
            'spacing': {'md': '16px', 'lg': '24px'},
            'radii': {'md': '6px'},
            'shadows': {'md': '0 2px 8px rgba(0,0,0,0.4)'}
        },
        assets={'logo': {'url': None}},
        menu={'style': 'horizontal', 'position': 'top'}
    )
}


def get_fallback_template(family: str) -> TemplateConfig:
    """Get a fallback template when DB is unavailable."""
    return DEFAULT_TEMPLATES.get(family, DEFAULT_TEMPLATES['agentworx'])


# ──────────────────────────────────────────────
# Database Operations
# ──────────────────────────────────────────────

def _get_db_password() -> str:
    """Get database password from centralized source."""
    try:
        import sys
        sys.path.insert(0, '/home/roger/.hermes/scripts')
        import db_password
        return db_password.get_db_password()
    except (ImportError, AttributeError):
        pass

    if os.environ.get('DB_PASSWORD'):
        return os.environ['DB_PASSWORD']

    try:
        with open(os.path.expanduser('~/.pgpass'), 'r') as f:
            for line in f:
                parts = line.strip().split(':')
                if len(parts) >= 5:
                    return parts[4]
    except FileNotFoundError:
        pass

    return ''


def _get_db_connection():
    """Create a database connection."""
    if not HAS_PSYCOPG2:
        raise RuntimeError("psycopg2 is required for database operations")

    password = _get_db_password()
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', '5432')),
        dbname=os.environ.get('DB_NAME', 'r0gr'),
        user=os.environ.get('DB_USER', 'r0gr'),
        password=password,
        cursor_factory=RealDictCursor
    )


def _fetch_template_from_db(template_key: str, version: int) -> Optional[TemplateConfig]:
    """Fetch a specific template version from the database."""
    conn = None
    try:
        conn = _get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT template_key, version, name, family,
                       tokens, assets, menu, metadata
                FROM ui.templates
                WHERE template_key = %s AND version = %s
            """, (template_key, version))
            row = cur.fetchone()
            if not row:
                return None
            return TemplateConfig(
                template_key=row['template_key'],
                version=row['version'],
                name=row['name'],
                family=row['family'],
                tokens=row['tokens'] or {},
                assets=row['assets'] or {},
                menu=row['menu'] or {},
                metadata=row['metadata'] or {}
            )
    finally:
        if conn:
            conn.close()


def _fetch_template_by_name_from_db(name: str) -> Optional[TemplateConfig]:
    """Fetch the latest version of a template by its human-readable name."""
    conn = None
    try:
        conn = _get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT template_key, version, name, family,
                       tokens, assets, menu, metadata
                FROM ui.templates
                WHERE name = %s
                ORDER BY version DESC
                LIMIT 1
            """, (name,))
            row = cur.fetchone()
            if not row:
                return None
            return TemplateConfig(
                template_key=row['template_key'],
                version=row['version'],
                name=row['name'],
                family=row['family'],
                tokens=row['tokens'] or {},
                assets=row['assets'] or {},
                menu=row['menu'] or {},
                metadata=row['metadata'] or {}
            )
    finally:
        if conn:
            conn.close()


def _fetch_assignment_from_db(app_key: str, environment: str = 'production') -> Optional[Dict[str, Any]]:
    """Fetch the active template assignment for an app."""
    conn = None
    try:
        conn = _get_db_connection()
        with conn.cursor() as cur:
            cur.execute("""
                SELECT template_key, version
                FROM ui.assignments
                WHERE app_key = %s AND environment = %s AND active = TRUE
            """, (app_key, environment))
            return cur.fetchone()
    finally:
        if conn:
            conn.close()


# ──────────────────────────────────────────────
# Template Manager
# ──────────────────────────────────────────────

class TemplateManager:
    """
    Central class for template loading, caching and CSS generation.
    """

    def __init__(self, db_config: Optional[Dict[str, str]] = None, cache_ttl: int = DEFAULT_CACHE_TTL):
        self.db_config = db_config or {}
        self.cache_ttl = cache_ttl
        self._cache = TemplateCache(ttl_seconds=cache_ttl)

    def get_template(
        self,
        app_key: str,
        environment: str = 'production',
        use_cache: bool = True
    ) -> Optional[TemplateConfig]:
        """
        Get the active template configuration for an application.
        """
        cache_key = f"{app_key}:{environment}"

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        # Fetch assignment from DB
        assignment = _fetch_assignment_from_db(app_key, environment)
        if not assignment:
            return None

        # Fetch template
        template = _fetch_template_from_db(assignment['template_key'], assignment['version'])
        if not template:
            return None

        # Cache
        if use_cache:
            self._cache.set(cache_key, template)

        return template

    def get_template_by_key(
        self,
        template_key: str,
        version: int,
        use_cache: bool = True
    ) -> Optional[TemplateConfig]:
        """Get a specific template by key and version."""
        cache_key = f"template:{template_key}:{version}"

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        template = _fetch_template_from_db(template_key, version)
        if template and use_cache:
            self._cache.set(cache_key, template)

        return template

    def get_template_by_name(
        self,
        name: str,
        use_cache: bool = True
    ) -> Optional[TemplateConfig]:
        """Get the latest version of a template by its human-readable name."""
        cache_key = f"template_name:{name}"

        if use_cache:
            cached = self._cache.get(cache_key)
            if cached:
                return cached

        template = _fetch_template_by_name_from_db(name)
        if template and use_cache:
            self._cache.set(cache_key, template)

        return template

    def invalidate_cache(self, app_key: Optional[str] = None):
        """Invalidate cache for an app or all apps."""
        if app_key:
            self._cache.invalidate(f"{app_key}:")
        else:
            self._cache.invalidate()

    def render_css_variables(self, config: TemplateConfig) -> str:
        """Generate CSS :root block from template."""
        return render_css_variables(config)

    def render_menu_css(self, config: TemplateConfig) -> str:
        """Generate menu-specific CSS rules."""
        menu = config.menu
        if not menu:
            return ""

        lines = ["/* Menu Styles */", ".site-nav {"]

        if 'background' in menu:
            lines.append(f"  background: {menu['background']};")
        if 'height' in menu:
            lines.append(f"  height: {menu['height']};")
        if 'border-bottom' in menu:
            lines.append(f"  border-bottom: {menu['border-bottom']};")

        lines.append("}")

        # Active indicator
        if menu.get('active-indicator') == 'bottom-border':
            lines.append("""
.site-nav .nav-item.active {
  border-bottom: 2px solid var(--color-accent);
}
""")

        return "\n".join(lines)

    def to_json(self, config: TemplateConfig) -> Dict[str, Any]:
        """Export template as JSON for API."""
        return {
            "template_key": config.template_key,
            "version": config.version,
            "name": config.name,
            "family": config.family,
            "tokens": config.tokens,
            "assets": config.assets,
            "menu": config.menu,
            "metadata": config.metadata
        }


# ──────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────

_manager_instance: Optional[TemplateManager] = None


def get_manager(db_config: Optional[Dict[str, str]] = None) -> TemplateManager:
    """Get a singleton TemplateManager instance."""
    global _manager_instance
    if _manager_instance is None:
        if db_config is None:
            db_config = {
                'host': 'localhost',
                'port': '5432',
                'dbname': 'r0gr',
                'user': 'r0gr',
            }
        _manager_instance = TemplateManager(db_config)
    return _manager_instance
