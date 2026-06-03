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

    def get_component(self, key: str, fallback: str = '') -> str:
        components = self.tokens.get('components', {})
        return components.get(key, fallback)

    def get_page_title(self) -> str:
        return self.metadata.get('page_title', self.name)

    def get_favicon_url(self) -> Optional[str]:
        favicon = self.assets.get('favicon', {})
        return favicon.get('url') if isinstance(favicon, dict) else favicon

    def get_brand_name(self) -> str:
        return self.metadata.get('brand_name', self.name)


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
    Generate CSS custom properties + component classes from template configuration.
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
        skip_keys = {'derived', 'components'}
        for key, value in data.items():
            if key in skip_keys:
                continue
            mapped_key = singular_map.get(key, key)
            full_key = f"{prefix}-{mapped_key}" if prefix else mapped_key
            if isinstance(value, dict):
                _flatten_dict(value, full_key)
            elif isinstance(value, str):
                var_name = f"--{full_key}"
                lines.append(f"  {var_name}: {value};")

    if config.tokens:
        _flatten_dict(config.tokens)

    # Generate derived rgba colors
    derived = config.tokens.get('derived', {})
    for key, value in derived.items():
        lines.append(f"  --derived-{key}: {value};")

    # Add logo URL as CSS variable
    logo_url = config.get_logo_url()
    if logo_url:
        lines.append(f"  --asset-logo-url: url('{logo_url}');")

    lines.append("}")

    return "\n".join(lines)


def render_component_css(config: TemplateConfig) -> str:
    return "\n".join(_generate_component_css(config))


def render_page_css(config: TemplateConfig) -> str:
    fonts = config.tokens.get('fonts', {})
    spacing = config.tokens.get('spacing', {})
    layout = config.tokens.get('layout', {})

    def _color(key: str, fallback: str) -> str:
        return config.get_color(key, fallback)

    def _font_size(key: str, fallback: str) -> str:
        return fonts.get(key, fallback)

    def _spacing(key: str, fallback: str) -> str:
        return spacing.get(key, fallback)

    content_max_width = layout.get('content-max-width', _spacing('container-max', '1400px'))
    content_padding = layout.get('content-padding', _spacing('container-padding', '24px'))

    return "\n".join([
        "body {",
        f"  background: {_color('bg-primary', 'var(--color-bg-primary)')};",
        f"  color: {_color('text-primary', 'var(--color-text-primary)')};",
        f"  font-family: {config.get_font()};",
        f"  min-height: 100vh;",
        f"  line-height: {fonts.get('line-height', '1.5')};",
        "}",
        "h1, h2, h3 {",
        f"  color: {_color('text-heading', _color('text-primary', 'var(--color-text-primary)'))};",
        f"  letter-spacing: 0.01em;",
        "}",
        "h1 {",
        f"  font-size: {_font_size('size-h1', '2rem')};",
        f"  font-weight: {fonts.get('weight-bold', '700')};",
        f"  margin: {_spacing('lg', '24px')} 0 {_spacing('sm', '8px')};",
        "}",
        "h2 {",
        f"  font-size: {_font_size('size-h2', '1.5rem')};",
        f"  font-weight: {fonts.get('weight-bold', '700')};",
        f"  margin: {_spacing('md', '16px')} 0 {_spacing('sm', '8px')};",
        "}",
        "h3 {",
        f"  font-size: {_font_size('size-h3', '1.125rem')};",
        f"  font-weight: {fonts.get('weight-medium', '600')};",
        f"  margin: {_spacing('md', '16px')} 0 {_spacing('xs', '4px')};",
        "}",
        "a {",
        f"  color: {_color('accent', 'var(--color-accent)')};",
        "  text-decoration: none;",
        "  transition: color 0.2s ease, text-decoration-color 0.2s ease;",
        "}",
        "a:hover {",
        "  text-decoration: underline;",
        f"  color: {_color('accent-hover', 'var(--color-accent-hover)')};",
        "}",
        ".container, .site-content {",
        f"  max-width: {content_max_width};",
        "  margin: 0 auto;",
        f"  padding: 0 {content_padding};",
        "}",
        ".app {",
        f"  max-width: {content_max_width};",
        "  margin: 0 auto;",
        f"  padding: {content_padding};",
        "}",
        ".page-header {",
        f"  margin-bottom: {_spacing('lg', '24px')};",
        f"  padding-bottom: {_spacing('sm', '8px')};",
        f"  border-bottom: 1px solid {_color('border', 'var(--color-border)')};",
        "}",
    ])


def render_chart_js_colors(config: TemplateConfig) -> str:
    """Generate a small JS snippet that reads CSS chart palette variables
    into global window.CHART_COLORS for use by Chart.js configs."""
    palette = config.tokens.get('chart_palette', {})
    if not palette:
        return ""
    vars_js = ",\n        ".join(
        f"{k}: getComputedStyle(document.documentElement).getPropertyValue('--chart_palette-{k}').trim()"
        for k in palette.keys()
    )
    return (
        "<script>\n"
        "  (function() {\n"
        "    var root = document.documentElement;\n"
        "    window.CHART_COLORS = {\n"
        "        " + vars_js + "\n"
        "    };\n"
        "  })();\n"
        "</script>"
    )


def _generate_component_css(config: TemplateConfig) -> list:
    """Generate CSS utility classes for common components."""
    css_lines = []
    components = config.tokens.get('components', {})

    def _component(key: str, fallback: str) -> str:
        return components.get(key, fallback)

    def _base_button(selector: str, bg: str, color: str, hover_selector: str, hover_bg: str, hover_color: Optional[str] = None, border: str = 'none'):
        css_lines.extend([
            f"{selector} {{",
            f"  background: {bg};",
            f"  color: {color};",
            f"  border: {border};",
            f"  border-radius: {_component('button-radius', _component('card-radius', 'var(--radius-md)'))};",
            f"  padding: {_component('button-padding', '0.7rem 1rem')};",
            f"  font-family: inherit;",
            f"  font-weight: {_component('button-font-weight', '600')};",
            f"  font-size: {_component('button-font-size', 'inherit')};",
            f"  cursor: pointer;",
            f"  transition: all 0.15s ease;",
            f"  -webkit-appearance: none;",
            "}",
            f"{hover_selector} {{",
            f"  background: {hover_bg};",
        ])
        if hover_color is not None:
            css_lines.append(f"  color: {hover_color};")
        css_lines.extend([
            "  transform: translateY(-1px);",
            "}",
        ])

    _base_button(
        '.btn-primary',
        _component('button-primary-bg', 'var(--color-accent)'),
        _component('button-primary-color', 'var(--color-accent-contrast)'),
        '.btn-primary:hover',
        _component('button-primary-hover', 'var(--color-accent-hover)'),
    )

    _base_button(
        '.btn-secondary',
        _component('button-secondary-bg', 'transparent'),
        _component('button-secondary-color', 'var(--color-text-primary)'),
        '.btn-secondary:hover',
        _component('button-secondary-hover-bg', 'var(--color-bg-elevated)'),
        border=_component('button-secondary-border', '1px solid var(--color-border)'),
    )

    _base_button(
        '.btn-danger',
        _component('button-danger-bg', 'var(--color-error)'),
        _component('button-danger-color', '#ffffff'),
        '.btn-danger:hover',
        _component('button-danger-hover', 'rgba(224, 85, 90, 0.9)'),
    )

    css_lines.extend([
        ".btn-ghost {",
        f"  background: {_component('button-ghost-bg', 'transparent')};",
        f"  color: {_component('button-ghost-color', 'var(--color-accent)')};",
        f"  border: {_component('button-ghost-border', 'none')};",
        f"  border-radius: {_component('button-radius', _component('card-radius', 'var(--radius-md)'))};",
        f"  padding: {_component('button-padding', '0.7rem 1rem')};",
        f"  font-family: inherit;",
        f"  font-weight: {_component('button-font-weight', '600')};",
        f"  font-size: {_component('button-font-size', 'inherit')};",
        f"  cursor: pointer;",
        f"  transition: all 0.15s ease;",
        f"  -webkit-appearance: none;",
        "}",
        ".btn-ghost:hover {",
        f"  color: {_component('button-ghost-hover-color', 'var(--color-accent-hover)')};",
        f"  transform: translateY(-1px);",
        "}",
    ])

    css_lines.extend([
        ".btn-sm {",
            f"  padding: 0.45rem 0.7rem;",
            f"  font-size: 0.875rem;",
            f"  border-radius: {_component('button-radius', _component('card-radius', 'var(--radius-md)'))};",
            "}",
        ".card {",
        f"  background: {_component('card-bg', 'var(--color-bg-surface)')};",
        f"  border: {_component('card-border', '1px solid var(--color-border)')};",
        f"  border-radius: {_component('card-radius', 'var(--radius-lg)')};",
        f"  padding: {_component('card-padding', '1rem')};",
        f"  overflow: hidden;",
        "}",
        ".card-header {",
        f"  padding: 0 0 {_component('card-padding', '1rem')};",
        f"  margin-bottom: {_component('card-padding', '1rem')};",
        f"  border-bottom: 1px solid {_component('card-border', 'var(--color-border)')};",
        "}",
        ".card-body {",
        f"  padding: 0;",
        "}",
        ".card-footer {",
        f"  padding: {_component('card-padding', '1rem')} 0 0;",
        f"  margin-top: {_component('card-padding', '1rem')};",
        f"  border-top: 1px solid {_component('card-border', 'var(--color-border)')};",
        "}",
        ".input, input[type=\"text\"], input[type=\"password\"], select, textarea {",
        f"  width: 100%;",
        f"  padding: 0.7rem 0.85rem;",
        f"  background: {_component('input-bg', 'var(--color-bg-primary)')};",
        f"  border: {_component('input-border', '1px solid var(--color-border)')};",
        f"  border-radius: {_component('card-radius', 'var(--radius-md)')};",
        f"  color: var(--color-text-primary);",
        f"  font-size: 0.95rem;",
        f"  font-family: inherit;",
        f"  outline: none;",
        f"  transition: border-color 0.2s, box-shadow 0.2s;",
        f"  -webkit-appearance: none;",
        "}",
        ".input:focus, input[type=\"text\"]:focus, input[type=\"password\"]:focus, select:focus, textarea:focus {",
        f"  border-color: {_component('input-focus-border', 'var(--color-accent)')};",
        f"  box-shadow: 0 0 0 3px var(--derived-accent-glow);",
        "}",
        ".modal-overlay {",
        f"  background: {_component('modal-overlay', 'rgba(0,0,0,0.7)')};",
        "}",
        ".modal {",
        f"  border-radius: {_component('modal-radius', 'var(--radius-lg)')};",
        f"  padding: {_component('modal-padding', '1.25rem')};",
        f"  background: var(--color-bg-surface);",
        f"  border: 1px solid var(--color-border);",
        "}",
        ".modal-header {",
        f"  display: flex;",
        f"  align-items: center;",
        f"  justify-content: space-between;",
        f"  gap: 0.75rem;",
        f"  margin-bottom: 1rem;",
        "}",
        ".modal-title {",
        f"  margin: 0;",
        f"  font-size: 1.125rem;",
        f"  font-weight: 600;",
        "}",
        ".modal-close {",
        f"  background: transparent;",
        f"  border: none;",
        f"  color: var(--color-text-secondary);",
        f"  cursor: pointer;",
        f"  font-size: 1.25rem;",
        "}",
        ".modal-body {",
        f"  padding: 0;",
        "}",
        "th, .table-header {",
        f"  background: {_component('table-header-bg', 'var(--color-bg-elevated)')};",
        "}",
        "tr:hover, .table-row:hover {",
        f"  background: {_component('table-row-hover', 'var(--derived-accent-5)')};",
        "}",
        ".tag, .badge {",
        f"  display: inline-flex;",
        f"  align-items: center;",
        f"  justify-content: center;",
        f"  padding: 0.25rem 0.5rem;",
        f"  font-size: 0.75rem;",
        "}",
        ".tag {",
        f"  border-radius: {_component('tag-radius', '9999px')};",
        "}",
        ".badge {",
        f"  border-radius: {_component('badge-radius', '9999px')};",
        "}",
        ".kpi-card {",
        f"  background: {_component('kpi-bg', 'var(--color-bg-surface)')};",
        f"  border: {_component('kpi-border', '1px solid var(--color-border)')};",
        f"  border-radius: {_component('kpi-radius', 'var(--radius-lg)')};",
        f"  padding: {_component('kpi-padding', '1rem')};",
        "}",
        ".kpi-label {",
        f"  display: block;",
        f"  color: var(--color-text-secondary);",
        f"  font-size: 0.875rem;",
        "}",
        ".kpi-value {",
        f"  font-size: 1.5rem;",
        f"  font-weight: 700;",
        "}",
        ".kpi-delta {",
        f"  font-size: 0.875rem;",
        "}",
        ".range-btn {",
        f"  padding: 0.5rem 0.75rem;",
        f"  border: 1px solid var(--color-border);",
        f"  background: transparent;",
        f"  color: var(--color-text-primary);",
        f"  border-radius: {_component('card-radius', 'var(--radius-md)')};",
        f"  cursor: pointer;",
        "}",
        ".range-btn.active {",
        f"  background: {_component('range-btn-active-bg', 'var(--color-accent)')};",
        f"  color: {_component('range-btn-active-color', 'var(--color-accent-contrast)')};",
        f"  border-color: {_component('range-btn-active-border', 'var(--color-accent)')};",
        "}",
        ".range-btn:hover {",
        f"  background: var(--derived-accent-5);",
        "}",
        ".filter-pill {",
        f"  padding: 0.45rem 0.75rem;",
        f"  border: 1px solid var(--color-border);",
        f"  background: transparent;",
        f"  color: var(--color-text-primary);",
        f"  border-radius: {_component('card-radius', '9999px')};",
        f"  cursor: pointer;",
        "}",
        ".filter-pill.active {",
        f"  background: {_component('filter-pill-active-bg', 'var(--color-accent)')};",
        f"  color: {_component('filter-pill-active-color', 'var(--color-accent-contrast)')};",
        f"  border-color: {_component('filter-pill-active-border', 'var(--color-accent)')};",
        "}",
        ".filter-pill:hover {",
        f"  background: var(--derived-accent-5);",
        "}",
        ".nav-item {",
        f"  display: inline-flex;",
        f"  align-items: center;",
        f"  gap: 0.5rem;",
        f"  padding: {_component('nav-item-padding', '0.5rem 0.75rem')};",
        f"  border-radius: {_component('nav-item-radius', 'var(--radius-md)')};",
        f"  font-size: {_component('nav-item-font-size', '0.95rem')};",
        f"  color: var(--color-text-primary);",
        f"  text-decoration: none;",
        "}",
        ".view-toggle button {",
        f"  padding: 0.5rem 0.75rem;",
        f"  border: 1px solid var(--color-border);",
        f"  background: transparent;",
        f"  color: var(--color-text-primary);",
        f"  cursor: pointer;",
        "}",
        ".view-toggle button.active {",
        f"  background: var(--color-accent);",
        f"  color: var(--color-accent-contrast);",
        f"  border-color: var(--color-accent);",
        "}",
        ".section-header {",
        f"  font-size: {_component('section-header-font-size', '1.25rem')};",
        f"  color: {_component('section-header-color', 'var(--color-text-primary)')};",
        f"  text-transform: {_component('section-header-transform', 'uppercase')};",
        f"  letter-spacing: {_component('section-header-spacing', '0.08em')};",
        f"  font-weight: {_component('section-header-weight', '700')};",
        "}",
    ])

    return css_lines


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
                'accent-dim': '#6a9955',
                'accent-hover': '#9be01a',
                'accent-contrast': '#1a1d21',
                'bg-primary': '#1a1d21',
                'bg-surface': '#21252a',
                'bg-elevated': '#2a2f35',
                'border': '#2a2f35',
                'text-primary': '#c4c9ce',
                'text-secondary': '#6a7078',
                'text-muted': '#4a5058',
                'text-heading': '#e8eaed',
                'warn': '#d29922',
                'error': '#e0555a',
                'success': '#6a9955',
                'info': '#539bf5',
            },
            'derived': {
                'accent-5': 'rgba(131,206,0,0.05)',
                'accent-8': 'rgba(131,206,0,0.08)',
                'accent-10': 'rgba(131,206,0,0.10)',
                'accent-12': 'rgba(131,206,0,0.12)',
                'accent-15': 'rgba(131,206,0,0.15)',
                'accent-25': 'rgba(131,206,0,0.25)',
                'accent-50': 'rgba(131,206,0,0.50)',
                'accent-glow': 'rgba(131,206,0,0.2)',
                'success-8': 'rgba(106,153,85,0.08)',
                'success-20': 'rgba(106,153,85,0.20)',
                'success-40': 'rgba(106,153,85,0.40)',
                'error-8': 'rgba(224,85,90,0.08)',
                'error-20': 'rgba(224,85,90,0.20)',
                'white-3': 'rgba(255,255,255,0.03)',
                'white-10': 'rgba(255,255,255,0.10)',
                'bg-backdrop': 'rgba(26,29,33,0.85)',
            },
            'fonts': {
                'primary': "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                'monospace': "ui-monospace, SFMono-Regular, 'SF Mono', Consolas, monospace",
                'size-base': '14px',
                'size-sm': '12px',
                'size-md': '14px',
                'size-lg': '16px',
                'size-xl': '20px',
                'size-h1': '24px',
                'size-h2': '20px',
                'size-h3': '16px',
                'weight-normal': '400',
                'weight-medium': '500',
                'weight-bold': '600',
                'line-height': '1.5',
                'line-height-tight': '1.25'
            },
            'spacing': {
                'xs': '4px',
                'sm': '8px',
                'md': '16px',
                'lg': '24px',
                'xl': '32px',
                'xxl': '48px',
                'section': '24px',
                'container-max': '1400px',
                'container-padding': '24px'
            },
            'layout': {
                'nav-height': '56px',
                'content-max-width': '1400px',
                'content-padding': '24px',
                'modal-max-width': '960px'
            },
            'radii': {
                'sm': '4px',
                'md': '8px',
                'lg': '12px',
                'pill': '9999px'
            },
            'shadows': {
                'sm': '0 1px 2px rgba(0,0,0,0.2)',
                'md': '0 4px 12px rgba(0,0,0,0.3)',
                'lg': '0 8px 24px rgba(0,0,0,0.4)',
                'glow-accent': '0 0 12px rgba(131, 206, 0, 0.2)'
            },
            'transitions': {
                'fast': '0.1s ease',
                'normal': '0.2s ease',
                'slow': '0.3s ease'
            },
            'chart_palette': {
                'primary': '#83ce00',
                'secondary': '#539bf5',
                'success': '#6a9955',
                'danger': '#e0555a',
                'neutral': '#6a7078',
                'grid': 'rgba(128,128,128,0.1)',
                'extra1': '#c9a227',
                'extra2': '#a56cc7',
                'extra3': '#4fc3f7',
                'extra4': '#ff9800'
            }
        },
        assets={
            'logo': {'url': 'https://agentworx.agency/assets/images/agentworx-logo-white.png'},
            'avatar': {'url': 'https://r0gr.de/roger-avatar.jpg'},
            'favicon': {'url': 'https://agentworx.agency/favicon.ico'}
        },
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
                'accent-dim': '#c07a2a',
                'accent-hover': '#ffaa4a',
                'accent-contrast': '#0f0a08',
                'bg-primary': '#0f0a08',
                'bg-surface': '#1a1410',
                'bg-elevated': '#2a1f15',
                'border': '#2a1f15',
                'text-primary': '#c4c9ce',
                'text-secondary': '#8a7f70',
                'text-muted': '#5a5048',
                'text-heading': '#e8eaed',
                'warn': '#e0a030',
                'error': '#ff5544',
                'success': '#00cc77',
                'info': '#5aafdf',
            },
            'derived': {
                'accent-5': 'rgba(240,154,58,0.05)',
                'accent-8': 'rgba(240,154,58,0.08)',
                'accent-10': 'rgba(240,154,58,0.10)',
                'accent-12': 'rgba(240,154,58,0.12)',
                'accent-15': 'rgba(240,154,58,0.15)',
                'accent-25': 'rgba(240,154,58,0.25)',
                'accent-50': 'rgba(240,154,58,0.50)',
                'accent-glow': 'rgba(240,154,58,0.2)',
                'success-8': 'rgba(0,204,119,0.08)',
                'success-20': 'rgba(0,204,119,0.20)',
                'success-40': 'rgba(0,204,119,0.40)',
                'error-8': 'rgba(255,85,68,0.08)',
                'error-20': 'rgba(255,85,68,0.20)',
                'white-3': 'rgba(255,255,255,0.03)',
                'white-10': 'rgba(255,255,255,0.10)',
                'bg-backdrop': 'rgba(15,10,8,0.85)',
            },
            'fonts': {
                'primary': "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
                'monospace': "ui-monospace, SFMono-Regular, 'SF Mono', Consolas, monospace",
                'size-base': '14px',
                'size-sm': '12px',
                'size-md': '14px',
                'size-lg': '16px',
                'size-xl': '20px',
                'size-h1': '24px',
                'size-h2': '20px',
                'size-h3': '16px',
                'weight-normal': '400',
                'weight-medium': '500',
                'weight-bold': '600',
                'line-height': '1.5',
                'line-height-tight': '1.25'
            },
            'spacing': {
                'xs': '4px',
                'sm': '8px',
                'md': '16px',
                'lg': '24px',
                'xl': '32px',
                'xxl': '48px',
                'section': '24px',
                'container-max': '1400px',
                'container-padding': '24px'
            },
            'layout': {
                'nav-height': '56px',
                'content-max-width': '1400px',
                'content-padding': '24px',
                'modal-max-width': '960px'
            },
            'radii': {
                'sm': '4px',
                'md': '8px',
                'lg': '12px',
                'pill': '9999px'
            },
            'shadows': {
                'sm': '0 1px 2px rgba(0,0,0,0.3)',
                'md': '0 4px 12px rgba(0,0,0,0.4)',
                'lg': '0 8px 24px rgba(0,0,0,0.5)',
                'glow-accent': '0 0 12px rgba(240, 154, 58, 0.2)'
            },
            'transitions': {
                'fast': '0.1s ease',
                'normal': '0.2s ease',
                'slow': '0.3s ease'
            },
            'chart_palette': {
                'primary': '#f09a3a',
                'secondary': '#5aafdf',
                'success': '#00cc77',
                'danger': '#ff5544',
                'neutral': '#8a7f70',
                'grid': 'rgba(128,128,128,0.1)',
                'extra1': '#ddaa33',
                'extra2': '#aa66cc',
                'extra3': '#33aaff',
                'extra4': '#ffaa33'
            }
        },
        assets={
            'logo': {'url': None},
            'avatar': {'url': 'https://r0gr.de/roger-avatar.jpg'},
            'favicon': {'url': 'https://r0gr.de/favicon.ico'}
        },
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
        return render_css_variables(config)

    def render_component_css(self, config: TemplateConfig) -> str:
        return render_component_css(config)

    def render_page_css(self, config: TemplateConfig) -> str:
        return render_page_css(config)

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
