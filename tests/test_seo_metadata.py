"""Tests for SEO metadata, meta descriptions, and robots directives."""
import re
import pytest
from flask import render_template_string
from src.app import create_app


def extract_meta_descriptions(html: str) -> list[str]:
    """Helper to extract all meta description contents from rendered HTML."""
    return re.findall(
        r'<meta\s+name=["\']description["\']\s+content=["\'](.*?)["\']\s*>',
        html,
        re.IGNORECASE,
    )


def extract_robots_directives(html: str) -> list[str]:
    """Helper to extract all robots meta tag contents from rendered HTML."""
    return re.findall(
        r'<meta\s+name=["\']robots["\']\s+content=["\'](.*?)["\']\s*>',
        html,
        re.IGNORECASE,
    )


def test_landing_page_renders_single_non_empty_meta_description(client, seeded_db):
    """Verify that the landing page renders exactly one non-empty meta description tag."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    metas = extract_meta_descriptions(html)
    assert len(metas) == 1, f"Expected exactly 1 meta description tag, found {len(metas)}: {metas}"
    desc = metas[0].strip()
    assert len(desc) > 0, "Meta description should not be empty"
    assert "LoanPulse" in desc
    assert "fintech" in desc.lower() or "loan" in desc.lower()


def test_public_pages_render_unique_meta_descriptions(client, seeded_db):
    """Verify public pages render exactly one relevant, non-empty meta description without duplicates."""
    public_endpoints = [
        ("/", "Discover LoanPulse"),
        ("/login", "LoanPulse"),
        ("/login/user", "customer account"),
        ("/login/admin", "administration login"),
        ("/signup", "customer account"),
        ("/role-select", "operating persona"),
        ("/calculator", "calculator"),
    ]

    seen_descriptions = set()

    for endpoint, keyword in public_endpoints:
        res = client.get(endpoint)
        assert res.status_code == 200, f"Expected 200 OK for {endpoint}, got {res.status_code}"
        html = res.data.decode("utf-8")

        metas = extract_meta_descriptions(html)
        assert len(metas) == 1, f"Expected exactly 1 meta description on {endpoint}, got {len(metas)}"
        desc = metas[0].strip()
        assert len(desc) > 10, f"Meta description for {endpoint} is too short"
        assert keyword.lower() in desc.lower(), f"Expected keyword '{keyword}' in meta description for {endpoint}"
        seen_descriptions.add(desc)

    # Verify that multiple unique descriptions were used across different public pages
    assert len(seen_descriptions) >= 5, "Expected distinct, page-specific descriptions across public routes"


def test_default_meta_description_fallback():
    """Verify base template renders the exact required default meta description when no override is provided."""
    app = create_app("testing")
    expected_default = (
        "LoanPulse is a transparent, rule-based loan management platform for submitting applications, "
        "review eligibility, tracking application status, and managing loan workflows."
    )
    # Note: Requirement default text:
    # 'LoanPulse is a transparent, rule-based loan management platform for submitting applications, reviewing eligibility, tracking application status, and managing loan workflows.'
    required_text = (
        "LoanPulse is a transparent, rule-based loan management platform for submitting applications, "
        "reviewing eligibility, tracking application status, and managing loan workflows."
    )

    with app.test_request_context("/"):
        rendered = render_template_string('{% extends "base.html" %}{% block content %}Hello{% endblock %}')
        metas = extract_meta_descriptions(rendered)
        assert len(metas) == 1
        assert metas[0] == required_text


def test_template_variable_overrides_meta_description():
    """Verify meta description can be customized via template context variable."""
    app = create_app("testing")
    custom_desc = "Custom dynamic description passed via template context variable."

    with app.test_request_context("/"):
        rendered = render_template_string(
            '{% extends "base.html" %}{% block content %}Hello{% endblock %}',
            meta_description=custom_desc,
        )
        metas = extract_meta_descriptions(rendered)
        assert len(metas) == 1
        assert metas[0] == custom_desc


def test_jinja_block_overrides_meta_description():
    """Verify meta description can be customized via Jinja block override."""
    app = create_app("testing")
    custom_block_desc = "Custom block-level meta description for specific page."

    template_code = (
        '{% extends "base.html" %}'
        '{% block meta_description %}' + custom_block_desc + '{% endblock %}'
        '{% block content %}Hello{% endblock %}'
    )

    with app.test_request_context("/"):
        rendered = render_template_string(template_code)
        metas = extract_meta_descriptions(rendered)
        assert len(metas) == 1
        assert metas[0] == custom_block_desc


def test_authenticated_dashboard_has_noindex_nofollow_directive(client, seeded_db):
    """Verify authenticated pages include noindex, nofollow and do not expose private user/loan data in metadata."""
    login_res = client.post(
        "/login",
        data={"email": "borrower01@example.test", "password": "demo123"},
        follow_redirects=True,
    )
    assert login_res.status_code == 200

    dash_res = client.get("/customer/dashboard")
    assert dash_res.status_code == 200
    html = dash_res.data.decode("utf-8")

    # Verify robots directive is present and blocks indexing
    robots = extract_robots_directives(html)
    assert len(robots) >= 1
    assert "noindex" in robots[0].lower()
    assert "nofollow" in robots[0].lower()

    # Verify meta description exists (exactly 1) and does not leak private customer data
    metas = extract_meta_descriptions(html)
    assert len(metas) == 1
    desc = metas[0]
    assert "borrower01@example.test" not in desc
    assert "Test Borrower 01" not in desc
    assert "APP-" not in desc


def test_error_page_has_noindex_nofollow_directive(client):
    """Verify error pages include noindex, nofollow directive."""
    res = client.get("/nonexistent-page-testing-404")
    assert res.status_code == 404
    html = res.data.decode("utf-8")

    robots = extract_robots_directives(html)
    assert len(robots) >= 1
    assert "noindex" in robots[0].lower()
    assert "nofollow" in robots[0].lower()


def test_existing_head_elements_preserved(client, seeded_db):
    """Verify existing title tags, favicon, stylesheets, and CSRF meta tag are preserved."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Title tag preserved
    assert "<title>LoanPulse — Smarter Loan Operations. Clearer Decisions.</title>" in html

    # Favicon links preserved
    assert 'rel="icon" type="image/png"' in html
    assert 'rel="shortcut icon" type="image/png"' in html
    assert 'rel="apple-touch-icon"' in html
    assert "loanpulse.png" in html

    # Stylesheet & fonts preserved
    assert 'rel="stylesheet"' in html
    assert "style.css" in html
    assert "fonts.googleapis.com" in html

    # CSRF meta tag preserved
    assert 'name="csrf-token"' in html
