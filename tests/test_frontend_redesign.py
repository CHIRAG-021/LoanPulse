"""Comprehensive automated tests for LoanPulse frontend redesign and new user entry flows."""
import pytest
from src.models import LoanApplication


def test_landing_page_unauthenticated(client, seeded_db):
    """Verify public landing page renders when unauthenticated."""
    res = client.get("/")
    assert res.status_code == 200
    assert b"Loan operations" in res.data
    assert b"simplified." in res.data
    assert b"Get Started" in res.data
    assert b"Log In" in res.data
    assert b"Core Platform Capabilities" in res.data
    assert b"The LoanPulse Operational Lifecycle" in res.data


def test_landing_page_accessible_for_all_users(client, seeded_db):
    """Verify landing page at root / is always accessible (200 OK) for both logged-out and logged-in users."""
    # 1. Customer logged in - visiting / still shows public landing page
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res_cust = client.get("/", follow_redirects=False)
    assert res_cust.status_code == 200
    assert b"LoanPulse" in res_cust.data
    client.post("/logout")

    # 2. Officer logged in - visiting / still shows public landing page
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    res_off = client.get("/", follow_redirects=False)
    assert res_off.status_code == 200
    assert b"LoanPulse" in res_off.data
    client.post("/logout")

    # 3. Manager logged in - visiting / still shows public landing page
    client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    res_mgr = client.get("/", follow_redirects=False)
    assert res_mgr.status_code == 200
    assert b"LoanPulse" in res_mgr.data
    client.post("/logout")


def test_role_selection_page(client, seeded_db):
    """Verify role selection gateway displays all three roles with links to login."""
    res = client.get("/select-role")
    assert res.status_code == 200
    assert b"How are you using LoanPulse?" in res.data
    assert b"Continue as Customer" in res.data
    assert b"Continue as Loan Officer" in res.data
    assert b"Continue as Loan Manager" in res.data

    # Also verify aliases
    assert client.get("/role-select").status_code == 200
    assert client.get("/get-started").status_code == 200


def test_login_page_role_context(client, seeded_db):
    """Verify login page displays dedicated portal views based on role/portal parameters."""
    res_cust = client.get("/login?role=CUSTOMER")
    assert res_cust.status_code == 200
    assert b"Welcome back" in res_cust.data
    assert b"Sign in to manage your LoanPulse account" in res_cust.data
    assert b"Sign up" in res_cust.data

    res_off = client.get("/login?role=LOAN_OFFICER")
    assert res_off.status_code == 200
    assert b"Administration Login" in res_off.data
    assert b"Secure access for authorized Loan Officers and Loan Managers" in res_off.data

    res_mgr = client.get("/login?role=LOAN_MANAGER")
    assert res_mgr.status_code == 200
    assert b"Administration Login" in res_mgr.data
    assert b"Secure access for authorized Loan Officers and Loan Managers" in res_mgr.data


def test_kpi_cards_and_dark_components_render(client, seeded_db):
    """Verify dashboards render their respective KPI metric cards and styled elements."""
    # Customer
    client.post("/login", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    dash_cust = client.get("/customer/dashboard")
    assert dash_cust.status_code == 200
    assert b"Total Applications" in dash_cust.data
    assert b"In Review / Processing" in dash_cust.data
    assert b"Approved Applications" in dash_cust.data
    client.post("/logout")

    # Officer
    client.post("/login", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    queue_off = client.get("/officer/queue")
    assert queue_off.status_code == 200
    assert b"Total Queue Volume" in queue_off.data
    assert b"Pending Officer Review" in queue_off.data
    assert b"Forwarded to Manager" in queue_off.data
    client.post("/logout")

    # Manager
    client.post("/login", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    queue_mgr = client.get("/manager/queue")
    assert queue_mgr.status_code == 200
    assert b"Pending Manager Decisions" in queue_mgr.data
    assert b"Approved Portfolio" in queue_mgr.data
    assert b"Rejected Applications" in queue_mgr.data
    client.post("/logout")
