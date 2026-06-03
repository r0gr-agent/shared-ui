"""
TDD Tests for shared-ui/ui_templates.py

Run: pytest shared-ui/tests/test_ui_templates.py -v
"""
import pytest
import sys
import os

# Add shared-ui to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from ui_templates import (
    TemplateConfig,
    TokenValidator,
    TemplateManager,
    TemplateCache,
    render_css_variables,
    render_component_css,
    render_page_css,
    validate_css_variables,
    get_fallback_template,
    ALLOWED_COLOR_PATTERN,
    ALLOWED_SIZE_PATTERN,
)


# ──────────────────────────────────────────────
# Tests for TemplateConfig dataclass
# ──────────────────────────────────────────────

class TestTemplateConfig:
    def test_create_template_config(self):
        """TemplateConfig should store template metadata and tokens."""
        config = TemplateConfig(
            template_key='agentworx',
            version=1,
            name='Agentworx Standard',
            family='agentworx',
            tokens={
                'colors': {'accent': '#83ce00', 'bg': '#1a1d21'},
                'fonts': {'primary': 'system-ui'},
                'spacing': {'md': '16px'},
            },
            assets={'logo': {'url': 'https://example.com/logo.png'}},
            menu={'style': 'horizontal'},
        )
        assert config.template_key == 'agentworx'
        assert config.version == 1
        assert config.name == 'Agentworx Standard'
        assert config.family == 'agentworx'

    def test_get_color_existing(self):
        """Should return color value for existing key."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            tokens={'colors': {'accent': '#83ce00', 'bg': '#1a1d21'}}
        )
        assert config.get_color('accent') == '#83ce00'
        assert config.get_color('bg') == '#1a1d21'

    def test_get_color_fallback(self):
        """Should return default/fallback for missing color."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            tokens={'colors': {}}
        )
        assert config.get_color('missing') == ''  # Empty string as default

    def test_get_font(self):
        """Should return font value."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            tokens={'fonts': {'primary': 'system-ui, sans-serif'}}
        )
        assert config.get_font() == 'system-ui, sans-serif'

    def test_get_spacing(self):
        """Should return spacing value."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            tokens={'spacing': {'md': '16px', 'lg': '24px'}}
        )
        assert config.get_spacing('md') == '16px'
        assert config.get_spacing('lg') == '24px'

    def test_get_logo_url(self):
        """Should return logo URL from assets."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            assets={'logo': {'url': 'https://example.com/logo.png'}}
        )
        assert config.get_logo_url() == 'https://example.com/logo.png'

    def test_get_logo_url_missing(self):
        """Should return None if logo not configured."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            assets={}
        )
        assert config.get_logo_url() is None

    def test_get_component_and_metadata_helpers(self):
        config = TemplateConfig(
            template_key='test',
            version=1,
            name='Test Name',
            family='test',
            tokens={'components': {'button-primary-bg': '#123456'}},
            assets={'favicon': {'url': 'https://example.com/favicon.ico'}},
            metadata={'brand_name': 'My Brand'},
        )
        assert config.get_component('button-primary-bg') == '#123456'
        assert config.get_component('missing', 'fallback') == 'fallback'
        assert config.get_favicon_url() == 'https://example.com/favicon.ico'
        assert config.get_brand_name() == 'My Brand'

    def test_metadata_helpers_default_to_name(self):
        config = TemplateConfig(
            template_key='test', version=1, name='Test Name', family='test'
        )
        assert config.get_brand_name() == 'Test Name'
        assert config.get_favicon_url() is None


# ──────────────────────────────────────────────
# Tests for validation
# ──────────────────────────────────────────────

class TestValidation:
    def test_validate_hex_color(self):
        """Should accept valid hex colors."""
        assert ALLOWED_COLOR_PATTERN.match('#83ce00')
        assert ALLOWED_COLOR_PATTERN.match('#1a1d21')
        assert ALLOWED_COLOR_PATTERN.match('#fff')
        assert ALLOWED_COLOR_PATTERN.match('#FFFFFF')

    def test_validate_invalid_color(self):
        """Should reject invalid color values."""
        assert not ALLOWED_COLOR_PATTERN.match('javascript:alert(1)')
        assert not ALLOWED_COLOR_PATTERN.match('</style>')
        assert not ALLOWED_COLOR_PATTERN.match('red; display:none')

    def test_validate_spacing(self):
        """Should accept valid spacing values."""
        assert ALLOWED_SIZE_PATTERN.match('16px')
        assert ALLOWED_SIZE_PATTERN.match('1.5rem')
        assert ALLOWED_SIZE_PATTERN.match('100%')
        assert ALLOWED_SIZE_PATTERN.match('10vh')

    def test_validate_invalid_spacing(self):
        """Should reject invalid spacing."""
        assert not ALLOWED_SIZE_PATTERN.match('16')
        assert not ALLOWED_SIZE_PATTERN.match('abc')

    def test_validate_css_variables_valid(self):
        """Should return empty errors for valid tokens."""
        tokens = {
            'colors': {'accent': '#83ce00', 'bg': '#1a1d21'},
            'fonts': {'family': 'system-ui, sans-serif'},
            'spacing': {'md': '16px'},
            'radius': {'md': '6px'},
            'shadow': {'md': '0 2px 8px rgba(0,0,0,0.3)'},
            'z-index': {'modal': '300'},
        }
        errors = validate_css_variables(tokens)
        assert errors == []

    def test_validate_css_variables_invalid_color(self):
        """Should detect invalid color values."""
        tokens = {
            'colors': {'accent': 'javascript:alert(1)', 'bg': '#1a1d21'},
        }
        errors = validate_css_variables(tokens)
        assert len(errors) >= 1
        assert any('accent' in e for e in errors)

    def test_validate_css_variables_invalid_font(self):
        """Should detect invalid font values."""
        tokens = {
            'fonts': {'family': '<script>alert(1)</script>'},
        }
        errors = validate_css_variables(tokens)
        assert len(errors) >= 1

    def test_validate_css_variables_invalid_spacing(self):
        """Should detect invalid spacing values."""
        tokens = {
            'spacing': {'md': 'abc'},
        }
        errors = validate_css_variables(tokens)
        assert len(errors) >= 1


# ──────────────────────────────────────────────
# Tests for CSS variable rendering
# ──────────────────────────────────────────────

class TestRenderCSSVariables:
    def test_render_basic_colors(self):
        """Should generate :root block with color variables."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            tokens={
                'colors': {'accent': '#83ce00', 'bg': '#1a1d21'},
            }
        )
        css = render_css_variables(config)
        assert ':root {' in css
        assert '--color-accent: #83ce00;' in css
        assert '--color-bg: #1a1d21;' in css
        assert '}' in css

    def test_render_nested_tokens(self):
        """Should flatten nested token structure."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            tokens={
                'colors': {'accent': '#83ce00'},
                'fonts': {'primary': 'system-ui'},
                'spacing': {'md': '16px'},
            }
        )
        css = render_css_variables(config)
        assert '--color-accent: #83ce00;' in css
        assert '--font-primary: system-ui;' in css
        assert '--spacing-md: 16px;' in css

    def test_render_with_logo(self):
        """Should include logo URL as CSS variable."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            tokens={},
            assets={'logo': {'url': 'https://example.com/logo.png'}}
        )
        css = render_css_variables(config)
        assert '--asset-logo-url' in css


class TestRenderComponentCSS:
    def test_render_component_css_contains_expected_selectors(self):
        config = TemplateConfig(
            template_key='test',
            version=1,
            name='Test',
            family='test',
            tokens={
                'components': {
                    'button-primary-bg': '#111111',
                    'button-primary-color': '#ffffff',
                    'button-primary-hover': '#222222',
                    'button-secondary-bg': '#333333',
                    'button-secondary-color': '#eeeeee',
                    'button-secondary-border': '1px solid #444444',
                    'button-secondary-hover-bg': '#555555',
                    'button-danger-bg': '#660000',
                    'button-danger-color': '#ffffff',
                    'button-danger-hover': '#770000',
                    'button-ghost-bg': 'transparent',
                    'button-ghost-color': '#999999',
                    'button-ghost-hover-color': '#aaaaaa',
                    'card-bg': '#101010',
                    'card-border': '1px solid #202020',
                    'card-radius': '12px',
                    'card-padding': '20px',
                    'input-bg': '#151515',
                    'input-border': '1px solid #252525',
                    'input-focus-border': '#3366ff',
                    'modal-overlay': 'rgba(0, 0, 0, 0.7)',
                    'modal-radius': '14px',
                    'modal-padding': '24px',
                    'table-header-bg': '#1a1a1a',
                    'table-row-hover': '#222222',
                    'tag-radius': '9999px',
                    'badge-radius': '9999px',
                    'kpi-bg': '#101010',
                    'kpi-border': '1px solid #222222',
                    'kpi-radius': '10px',
                    'kpi-padding': '16px',
                    'range-btn-active-bg': '#ff8800',
                    'range-btn-active-color': '#000000',
                    'range-btn-active-border': '#ff8800',
                    'filter-pill-active-bg': '#00aa88',
                    'filter-pill-active-color': '#ffffff',
                    'filter-pill-active-border': '#00aa88',
                    'nav-item-padding': '8px 12px',
                    'nav-item-radius': '8px',
                    'nav-item-font-size': '14px',
                    'section-header-font-size': '18px',
                    'section-header-color': '#f0f0f0',
                    'section-header-transform': 'uppercase',
                    'section-header-spacing': '0.08em',
                    'section-header-weight': '700',
                }
            },
        )
        css = render_component_css(config)
        expected_selectors = [
            '.btn-primary {', '.btn-primary:hover {', '.btn-secondary {', '.btn-danger {', '.btn-ghost {',
            '.btn-sm {', '.card {', '.card-header {', '.card-body {', '.card-footer {',
            '.input, input[type="text"], input[type="password"], select, textarea {',
            '.input:focus, input[type="text"]:focus, input[type="password"]:focus, select:focus, textarea:focus {',
            '.modal-overlay {', '.modal {', '.modal-header {', '.modal-title {', '.modal-close {', '.modal-body {',
            'th, .table-header {', 'tr:hover, .table-row:hover {', '.tag, .badge {', '.kpi-card {',
            '.kpi-label {', '.kpi-value {', '.kpi-delta {', '.range-btn {', '.range-btn.active {', '.range-btn:hover {',
            '.filter-pill {', '.filter-pill.active {', '.filter-pill:hover {', '.nav-item {', '.view-toggle button {',
            '.view-toggle button.active {', '.section-header {',
        ]
        for selector in expected_selectors:
            assert selector in css


class TestRenderPageCSS:
    def test_render_page_css_contains_expected_selectors(self):
        config = TemplateConfig(
            template_key='test',
            version=1,
            name='Test',
            family='test',
            tokens={
                'colors': {
                    'bg-primary': '#111111',
                    'text-primary': '#eeeeee',
                    'accent': '#ff9900',
                    'accent-hover': '#ffaa33',
                    'border': '#222222',
                },
                'fonts': {
                    'primary': 'system-ui, sans-serif',
                    'line-height': '1.6',
                    'size-h1': '32px',
                    'size-h2': '24px',
                    'size-h3': '18px',
                    'weight-bold': '700',
                    'weight-medium': '600',
                },
                'spacing': {
                    'md': '16px',
                    'lg': '24px',
                    'sm': '8px',
                    'container-max': '1200px',
                    'container-padding': '20px',
                },
                'layout': {
                    'content-max-width': '1200px',
                    'content-padding': '20px',
                },
            },
        )
        css = render_page_css(config)
        for selector in ['body {', 'h1, h2, h3 {', 'h1 {', 'h2 {', 'h3 {', 'a {', 'a:hover {', '.container, .site-content {', '.app {', '.page-header {']:
            assert selector in css
        assert 'background: #111111;' in css
        assert 'color: #eeeeee;' in css
        assert 'font-size: 32px;' in css


# ──────────────────────────────────────────────
# Tests for TemplateCache
# ──────────────────────────────────────────────

class TestTemplateCache:
    def test_cache_store_and_retrieve(self):
        """Should store and retrieve template from cache."""
        cache = TemplateCache(ttl_seconds=300)
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test'
        )
        cache.set('audit-viewer:production', config)
        retrieved = cache.get('audit-viewer:production')
        assert retrieved is not None
        assert retrieved.template_key == 'test'

    def test_cache_miss(self):
        """Should return None for uncached key."""
        cache = TemplateCache(ttl_seconds=300)
        result = cache.get('unknown:production')
        assert result is None

    def test_cache_expiry(self):
        """Should expire entries after TTL."""
        cache = TemplateCache(ttl_seconds=0)  # Immediate expiry
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test'
        )
        cache.set('test:production', config)
        # Should expire immediately
        retrieved = cache.get('test:production')
        assert retrieved is None

    def test_cache_invalidate_single(self):
        """Should invalidate single cache entry."""
        cache = TemplateCache(ttl_seconds=300)
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test'
        )
        cache.set('app1:production', config)
        cache.set('app2:production', config)
        cache.invalidate('app1')
        assert cache.get('app1:production') is None
        assert cache.get('app2:production') is not None

    def test_cache_invalidate_all(self):
        """Should invalidate all cache entries."""
        cache = TemplateCache(ttl_seconds=300)
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test'
        )
        cache.set('app1:production', config)
        cache.set('app2:production', config)
        cache.invalidate()
        assert cache.get('app1:production') is None
        assert cache.get('app2:production') is None


# ──────────────────────────────────────────────
# Tests for fallback templates
# ──────────────────────────────────────────────

class TestFallbackTemplates:
    def test_fallback_agentworx(self):
        """Should return agentworx fallback template."""
        template = get_fallback_template('agentworx')
        assert template.template_key == 'agentworx'
        assert template.family == 'agentworx'
        assert template.tokens['colors']['accent'] == '#83ce00'

    def test_fallback_r0gr(self):
        """Should return r0gr fallback template."""
        template = get_fallback_template('r0gr')
        assert template.template_key == 'r0gr'
        assert template.family == 'r0gr'
        assert template.tokens['colors']['accent'] == '#f09a3a'

    def test_fallback_unknown_defaults_to_agentworx(self):
        """Should default to agentworx for unknown family."""
        template = get_fallback_template('unknown')
        assert template.template_key == 'agentworx'


# ──────────────────────────────────────────────
# Tests for TemplateManager (with mocked DB)
# ──────────────────────────────────────────────

class TestTemplateManager:
    def test_manager_initialization(self):
        """Should initialize with db_config and cache_ttl."""
        db_config = {
            'host': 'localhost',
            'port': '5432',
            'dbname': 'r0gr',
            'user': 'r0gr',
        }
        manager = TemplateManager(db_config, cache_ttl=300)
        assert manager.db_config == db_config
        assert manager.cache_ttl == 300

    def test_render_menu_css(self):
        """Should generate menu CSS from config."""
        db_config = {'host': 'localhost', 'port': '5432', 'dbname': 'r0gr', 'user': 'r0gr'}
        manager = TemplateManager(db_config)
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            menu={'style': 'horizontal', 'height': '56px', 'background': '#21252a'}
        )
        css = manager.render_menu_css(config)
        assert 'nav {' in css
        assert 'height: var(--layout-nav-height, 56px);' in css
        assert '@media (max-width: 768px)' in css


# ──────────────────────────────────────────────
# Edge case tests
# ──────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_tokens(self):
        """Should handle empty tokens gracefully."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            tokens={}
        )
        css = render_css_variables(config)
        assert ':root {' in css
        assert '}' in css

    def test_special_characters_in_values(self):
        """Should handle CSS values with commas and spaces."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            tokens={
                'fonts': {
                    'primary': '-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif'
                }
            }
        )
        css = render_css_variables(config)
        assert '--font-primary: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, sans-serif;' in css

    def test_rgba_colors(self):
        """Should handle rgba color values."""
        config = TemplateConfig(
            template_key='test', version=1, name='Test', family='test',
            tokens={
                'colors': {
                    'overlay': 'rgba(0, 0, 0, 0.7)',
                    'focus': 'rgba(131, 206, 0, 0.3)',
                }
            }
        )
        css = render_css_variables(config)
        assert '--color-overlay: rgba(0, 0, 0, 0.7);' in css
