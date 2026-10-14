"""Automated tests for mobile and tablet responsiveness across LoanPulse.

Verifies:
1. Viewport meta tag configuration across public and authenticated screens.
2. Responsive media queries in style.css covering 1024px, 768px, 640px, 480px, and 360px.
3. Contained table scrolling (.table-responsive with overflow-x: auto).
4. Responsive layout grids (calculator, review rows, statistics cards, capabilities).
5. Global horizontal overflow prevention (html and body overflow-x: hidden, media scaling).
6. Multi-column form stacking on narrow viewports.
7. Mobile preview bar, header, and toolbar wrapping.
"""
import pytest
from src.models import User


def test_viewport_meta_tag_present(client, seeded_db):
    """Viewport meta tag is properly configured for responsive rendering on all screens."""
    # Test public landing
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in html

    # Test calculator
    res = client.get("/calculator")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in html

    # Test login
    res = client.get("/login")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in html

    # Test customer dashboard
    client.post("/login/user", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res = client.get("/customer/dashboard")
    assert res.status_code == 200
    html = res.data.decode("utf-8")
    assert '<meta name="viewport" content="width=device-width, initial-scale=1.0">' in html
    client.post("/logout")


def test_css_responsive_breakpoints_defined(client):
    """CSS defines dedicated breakpoints for tablets, phablets, standard mobile, and compact mobile."""
    res = client.get("/static/css/style.css")
    assert res.status_code == 200
    css = res.data.decode("utf-8")

    # 1. Tablet landscape / small desktop (<= 1024px)
    assert "@media (max-width: 1024px)" in css

    # 2. Medium tablet (<= 900px)
    assert "@media (max-width: 900px)" in css

    # 3. Tablet portrait & mobile drawer (<= 768px)
    assert "@media (max-width: 768px)" in css

    # 4. Phablets / large phones (<= 640px)
    assert "@media (max-width: 640px)" in css

    # 5. Standard mobile phones (<= 480px: 430px, 390px, 375px)
    assert "@media (max-width: 480px)" in css

    # 6. Compact mobile phones (<= 360px: 360px, 320px)
    assert "@media (max-width: 360px)" in css


def test_contained_table_scrolling_css(client):
    """Tables are wrapped in .table-responsive with contained horizontal scrolling."""
    res = client.get("/static/css/style.css")
    assert res.status_code == 200
    css = res.data.decode("utf-8")

    assert ".table-responsive {" in css
    assert "overflow-x: auto;" in css
    assert "-webkit-overflow-scrolling: touch;" in css
    assert ".table-responsive table {" in css
    assert "min-width: 540px;" in css


def test_responsive_grid_helpers(client):
    """Responsive grid classes and collapsing rules are defined for calculator, review, and cards."""
    res = client.get("/static/css/style.css")
    assert res.status_code == 200
    css = res.data.decode("utf-8")

    # Calculator grid
    assert ".calculator-grid {" in css
    assert ".calculator-figures-grid {" in css

    # Review rows & 2-column forms
    assert ".form-row-2col," in css or ".form-row-2col" in css
    assert ".review-row-grid" in css

    # Collapsing rules for 1fr on narrow viewports
    assert "grid-template-columns: 1fr !important;" in css


def test_global_horizontal_overflow_prevention(client):
    """Root html and body have overflow-x prevention, full width, and responsive media constraints."""
    res = client.get("/static/css/style.css")
    assert res.status_code == 200
    css = res.data.decode("utf-8")

    assert "overflow-x: hidden;" in css
    assert "max-width: 100vw;" in css
    assert "img, svg, video, canvas {" in css
    assert "max-width: 100%;" in css


def test_mobile_preview_and_header_wrapping(client):
    """Preview bar, toolbars, and card headers have flex-wrap and responsive padding."""
    res = client.get("/static/css/style.css")
    assert res.status_code == 200
    css = res.data.decode("utf-8")

    # Preview bar wrap
    assert ".preview-bar {" in css
    assert "flex-wrap: wrap;" in css

    # Head and dashboard toolbar on mobile
    assert ".dashboard-toolbar {" in css
    assert ".search-box-wrap {" in css
