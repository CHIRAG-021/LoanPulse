"""Automated tests for Light Mode and Dark Mode support and Theme Toggle.

Verifies:
1. Light Mode is default theme for the application.
2. Head contains inline script to restore saved theme from localStorage and prevent FOUC.
3. Theme toggle button with sun and moon icons is rendered on:
   - Unauthenticated pages (Landing, Login)
   - Authenticated Customer Dashboard
   - Authenticated Loan Officer Queue
   - Authenticated Loan Manager Queue
4. Theme toggle button is neatly aligned in .nav-right-cluster alongside the profile area.
5. Theme toggle button has accessible aria-label and tooltip.
6. CSS stylesheet defines:
   - :root and html[data-theme="light"] light tokens
   - html[data-theme="dark"] dark tokens
   - Preserved dark navbar styling across all themes
   - Sun icon visible in light mode, moon icon visible in dark mode
   - Component refinements for tables, forms, alerts, badges, and profile dropdown
"""
import pytest
from src.models import User


def test_theme_toggle_on_public_pages(client, seeded_db):
    """Public pages should have theme toggle button and head theme script."""
    res = client.get("/")
    assert res.status_code == 200

    # Inline script in head for FOUC prevention and default to light
    assert b"loanpulse_theme" in res.data
    assert b"document.documentElement.setAttribute('data-theme', theme)" in res.data

    # Toggle button present in public navbar
    assert b'id="themeToggleBtnPublic"' in res.data
    assert b'class="btn-theme-toggle"' in res.data
    assert b'class="theme-icon-sun"' in res.data
    assert b'class="theme-icon-moon"' in res.data
    assert b'aria-label="Switch to Dark Mode"' in res.data
    assert b'title="Switch to Dark Mode"' in res.data


def test_theme_toggle_on_login_page(client, seeded_db):
    """Login page should include theme toggle button."""
    res = client.get("/login")
    assert res.status_code == 200
    assert b'class="btn-theme-toggle"' in res.data
    assert b'class="theme-icon-sun"' in res.data
    assert b'class="theme-icon-moon"' in res.data


def test_customer_dashboard_theme_toggle_and_alignment(client, seeded_db):
    """Customer dashboard renders theme toggle beside profile area in top-right cluster."""
    login_res = client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    assert login_res.status_code == 200

    dash_res = client.get("/customer/dashboard")
    assert dash_res.status_code == 200

    # Theme toggle button present
    assert b'id="themeToggleBtn"' in dash_res.data
    assert b'class="btn-theme-toggle"' in dash_res.data
    assert b'class="theme-icon-sun"' in dash_res.data
    assert b'class="theme-icon-moon"' in dash_res.data
    assert b'aria-label="Switch to Dark Mode"' in dash_res.data

    # Both theme toggle and profile area present in nav-right-cluster
    assert b'class="nav-right-cluster"' in dash_res.data
    assert b'id="profileArea"' in dash_res.data
    assert b'id="profileDropdownBtn"' in dash_res.data

    # Order check: theme toggle button is in the top-right cluster alongside profile area
    cluster_idx = dash_res.data.find(b'class="nav-right-cluster"')
    toggle_idx = dash_res.data.find(b'id="themeToggleBtn"')
    profile_idx = dash_res.data.find(b'id="profileArea"')
    assert cluster_idx < toggle_idx < profile_idx

    client.post("/logout")


def test_officer_dashboard_theme_toggle(client, seeded_db):
    """Loan Officer dashboard renders theme toggle beside profile area."""
    login_res = client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    assert login_res.status_code == 200

    queue_res = client.get("/officer/queue")
    assert queue_res.status_code == 200

    assert b'id="themeToggleBtn"' in queue_res.data
    assert b'class="btn-theme-toggle"' in queue_res.data
    assert b'id="profileArea"' in queue_res.data
    assert b'class="profile-role-label">Officer</span>' in queue_res.data

    client.post("/logout")


def test_manager_dashboard_theme_toggle(client, seeded_db):
    """Loan Manager dashboard renders theme toggle beside profile area."""
    login_res = client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    assert login_res.status_code == 200

    queue_res = client.get("/manager/queue")
    assert queue_res.status_code == 200

    assert b'id="themeToggleBtn"' in queue_res.data
    assert b'class="btn-theme-toggle"' in queue_res.data
    assert b'id="profileArea"' in queue_res.data
    assert b'class="profile-role-label">Manager</span>' in queue_res.data

    client.post("/logout")


def test_theme_css_definitions_and_navbar_preservation(client):
    """CSS file must define light mode default, dark mode, navbar preservation, and toggle styles."""
    res = client.get("/static/css/style.css")
    assert res.status_code == 200
    css_content = res.data.decode("utf-8")

    # Light Mode default tokens
    assert 'html[data-theme="light"]' in css_content
    assert "--bg-page: #f8fafc" in css_content
    assert "--bg-surface: #ffffff" in css_content
    assert "--bg-card: #ffffff" in css_content
    assert "--text-primary: #0f172a" in css_content

    # Dark Mode tokens preserved
    assert 'html[data-theme="dark"]' in css_content
    assert "--bg-page: #070b14" in css_content
    assert "--bg-surface: #0d1320" in css_content
    assert "--bg-card: #0e1526" in css_content

    # Topbar / Navbar preservation rule
    assert ".topbar {" in css_content
    assert "background: rgba(11, 17, 30, 0.85) !important;" in css_content
    assert "border-bottom: 1px solid #1e2c47 !important;" in css_content

    # Toggle button and icon display rules
    assert ".btn-theme-toggle" in css_content
    assert ".theme-icon-sun" in css_content
    assert ".theme-icon-moon" in css_content
    assert 'html[data-theme="light"] .theme-icon-sun' in css_content
    assert 'html[data-theme="light"] .theme-icon-moon' in css_content
    assert 'html[data-theme="dark"] .theme-icon-sun' in css_content
    assert 'html[data-theme="dark"] .theme-icon-moon' in css_content

    # Light mode profile dropdown rules
    assert 'html[data-theme="light"] .profile-dropdown' in css_content
    assert 'html[data-theme="light"] .profile-details-section' in css_content


def test_landing_page_light_theme_contrast(client):
    """Verify landing page elements use high-contrast light theme tokens and scoped dark overrides."""
    # 1. Check HTML output
    res = client.get("/")
    assert res.status_code == 200
    html_content = res.data.decode("utf-8")

    # Verify hero elements
    assert "hero-pill" in html_content
    assert "hero-title" in html_content
    assert "gradient" in html_content
    assert "hero-desc" in html_content

    # Verify preview and CTA classes
    assert "preview-app-title" in html_content
    assert "preview-stat-num" in html_content
    assert "preview-stat-success" in html_content
    assert "landing-cta-banner" in html_content

    # Verify no hardcoded white text on light landing page surfaces
    assert 'color: #ffffff;">Personal Term Loan Evaluation' not in html_content
    assert 'color: #ffffff;">₹2,50,000' not in html_content
    assert 'color: #ffffff;">Ready to Get Started?' not in html_content

    # 2. Check CSS definitions
    css_res = client.get("/static/css/style.css")
    assert css_res.status_code == 200
    css = css_res.data.decode("utf-8")

    # Hero title contrast
    assert ".hero-title" in css
    assert "color: #2563eb;" in css
    assert 'html[data-theme="dark"] .hero-title' in css
    assert "color: #60a5fa;" in css

    # Hero gradient contrast
    assert 'html[data-theme="dark"] .hero-title span.gradient' in css
    assert "-webkit-background-clip: text;" in css
    assert "background-clip: text;" in css
    assert "-webkit-text-fill-color: transparent;" in css

    # Hero pill badge contrast
    assert ".hero-pill {" in css
    assert "color: var(--primary-hover);" in css
    assert 'html[data-theme="dark"] .hero-pill' in css

    # Section headings contrast
    assert ".section-head h2 {" in css
    assert 'html[data-theme="dark"] .section-head h2 {\n    color: #ffffff;' in css

    # Capability icons and workflow step numbers
    assert ".capability-icon {" in css
    assert 'html[data-theme="dark"] .capability-icon' in css
    assert ".workflow-step-num {" in css
    assert 'html[data-theme="dark"] .workflow-step-num' in css

    # Product preview mockup and CTA banner
    assert ".preview-app-title {" in css
    assert ".preview-stat-num {" in css
    assert ".preview-stat-success {" in css
    assert ".landing-cta-banner {" in css
    assert 'html[data-theme="dark"] .landing-cta-banner' in css

    # 3. Mathematical contrast check (WCAG AA)
    def rel_lum(hex_color):
        hex_color = hex_color.lstrip('#')
        rgb = [int(hex_color[i:i+2], 16) / 255.0 for i in (0, 2, 4)]
        lum = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
        return 0.2126 * lum[0] + 0.7152 * lum[1] + 0.0722 * lum[2]

    def contrast(c1, c2):
        l1, l2 = rel_lum(c1), rel_lum(c2)
        return (max(l1, l2) + 0.05) / (min(l1, l2) + 0.05)

    # Hero title on light page: #2563eb on #f8fafc >= 4.5:1
    assert contrast("2563eb", "f8fafc") >= 4.5
    # Hero title on dark page: #60a5fa on #070b14 >= 4.5:1, and fallback #2563eb on #070b14 >= 3.0:1
    assert contrast("60a5fa", "070b14") >= 4.5
    assert contrast("2563eb", "070b14") >= 3.0

    # Badge pill text on badge background: #1d4ed8 on #eff6ff >= 4.5:1
    assert contrast("1d4ed8", "eff6ff") >= 4.5

    # Hero gradient start & end on light page: #2563eb and #7c3aed on #f8fafc >= 3:1 (large text)
    assert contrast("2563eb", "f8fafc") >= 3.0
    assert contrast("7c3aed", "f8fafc") >= 3.0

    # Stat success color on white card: #047857 on #ffffff >= 4.5:1
    assert contrast("047857", "ffffff") >= 4.5

