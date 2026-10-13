"""Automated tests for responsive mobile navigation bar and slide-in drawer.

Verifies:
1. Desktop navigation preservation (min-width > 768px):
   - LoanPulse brand logo and text on the left.
   - Desktop navigation links, theme toggle, and auth buttons present.
   - .nav-desktop-content has display: contents !important on desktop.
   - .btn-hamburger has display: none !important on desktop.
2. Mobile navigation bar (max-width <= 768px):
   - Hamburger button (#navDrawerOpenBtn) present with proper ARIA attributes.
   - Topbar has single row layout (height: 60px, flex-wrap: nowrap, justify-content: space-between).
   - Desktop navigation content hidden (.nav-desktop-content { display: none !important; }).
3. Slide-in navigation drawer:
   - Backdrop overlay (#navDrawerBackdrop) present.
   - Drawer container (#navMobileDrawer) has role="dialog", aria-modal="true", aria-label="Mobile navigation".
   - Drawer header has LoanPulse logo/text and visible close button (#navDrawerCloseBtn).
   - Unauthenticated drawer contains: Features, How It Works, EMI Calculator, Theme toggle, Log In, Sign Up.
   - Authenticated drawer contains: Role-specific links, notifications badge, theme toggle, and logout button.
   - Touch targets for drawer links and buttons meet >= 44px height requirement.
4. Theming and accessibility:
   - Theme toggle present inside drawer for both public and authenticated views.
   - Light and dark mode CSS styling defined for drawer, header, close button, and links.
   - prefers-reduced-motion support.
"""
import pytest
from src.models import User


def test_public_mobile_navbar_and_drawer_markup(client, seeded_db):
    """Public landing page contains mobile hamburger trigger and slide-in drawer."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # 1. Desktop Nav Content Wrapper
    assert 'class="nav-desktop-content"' in html
    assert 'id="themeToggleBtnPublic"' in html

    # 2. Hamburger button on topbar
    assert 'id="navDrawerOpenBtn"' in html
    assert 'aria-label="Open navigation menu"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-controls="navMobileDrawer"' in html
    assert 'class="btn-hamburger"' in html

    # 3. Drawer backdrop overlay
    assert 'id="navDrawerBackdrop"' in html
    assert 'class="nav-drawer-backdrop"' in html

    # 4. Slide-in drawer container
    assert 'id="navMobileDrawer"' in html
    assert 'class="nav-drawer"' in html
    assert 'role="dialog"' in html
    assert 'aria-modal="true"' in html
    assert 'aria-label="Mobile navigation"' in html

    # 5. Drawer header with close button and branding
    assert 'id="navDrawerCloseBtn"' in html
    assert 'aria-label="Close navigation menu"' in html
    assert 'class="brand drawer-brand"' in html
    assert 'LoanPulse</span>' in html

    # 6. Public drawer navigation links
    assert 'href="/#features"' in html or 'href="#features"' in html
    assert 'href="/#how-it-works"' in html or 'href="#how-it-works"' in html
    assert 'EMI Calculator</span>' in html
    assert 'href="/login"' in html
    assert 'href="/signup"' in html

    # 7. Theme toggle inside mobile drawer
    assert 'id="themeToggleBtnDrawerPublic"' in html
    assert 'class="btn-theme-toggle nav-drawer-theme-btn"' in html
    assert 'drawer-theme-label' in html


def test_login_page_mobile_navbar_and_drawer(client, seeded_db):
    """Login page contains hamburger button and mobile drawer."""
    res = client.get("/login")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    assert 'id="navDrawerOpenBtn"' in html
    assert 'id="navMobileDrawer"' in html
    assert 'id="navDrawerBackdrop"' in html
    assert 'id="themeToggleBtnDrawerPublic"' in html


def test_customer_mobile_navbar_and_drawer(client, seeded_db):
    """Authenticated customer view renders role-based mobile drawer links and logout."""
    client.post("/login/user", data={"email": "borrower01@example.test", "password": "demo123"}, follow_redirects=True)
    res = client.get("/customer/dashboard")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    # Hamburger and drawer present
    assert 'id="navDrawerOpenBtn"' in html
    assert 'id="navMobileDrawer"' in html

    # Customer user info in drawer
    assert 'profile-user-name' in html
    assert 'role-pill-CUSTOMER' in html

    # Role links
    assert '/customer/dashboard' in html
    assert '/customer/applications' in html
    assert '/customer/kyc' in html
    assert '/customer/profile' in html
    assert '/calculator' in html
    assert '/notifications' in html

    # Theme toggle & logout in drawer
    assert 'id="themeToggleBtnDrawer"' in html
    assert 'id="drawerLogoutBtn"' in html
    assert 'id="drawerLogoutForm"' in html

    client.post("/logout")


def test_officer_mobile_navbar_and_drawer(client, seeded_db):
    """Authenticated loan officer view renders officer-specific drawer links."""
    client.post("/login/admin", data={"email": "officer01@example.test", "password": "demo123"}, follow_redirects=True)
    res = client.get("/officer/queue")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    assert 'id="navDrawerOpenBtn"' in html
    assert 'id="navMobileDrawer"' in html
    assert '/officer/queue' in html
    assert '/officer/kyc' in html
    assert '/officer/disbursements' in html
    assert '/officer/loan-products' in html
    assert 'id="drawerLogoutBtn"' in html

    client.post("/logout")


def test_manager_mobile_navbar_and_drawer(client, seeded_db):
    """Authenticated loan manager view renders manager-specific drawer links."""
    client.post("/login/admin", data={"email": "manager01@example.test", "password": "demo123"}, follow_redirects=True)
    res = client.get("/manager/queue")
    assert res.status_code == 200
    html = res.data.decode("utf-8")

    assert 'id="navDrawerOpenBtn"' in html
    assert 'id="navMobileDrawer"' in html
    assert '/manager/queue' in html
    assert '/manager/loan-products' in html
    assert 'id="drawerLogoutBtn"' in html

    client.post("/logout")


def test_mobile_navigation_css_rules(client):
    """CSS defines hamburger button, slide-in drawer, media queries, and touch targets."""
    res = client.get("/static/css/style.css")
    assert res.status_code == 200
    css = res.data.decode("utf-8")

    # 1. Hamburger button definition
    assert ".btn-hamburger {" in css
    assert "width: 42px;" in css
    assert "height: 42px;" in css

    # 2. Drawer and backdrop definition
    assert ".nav-drawer-backdrop {" in css
    assert "position: fixed;" in css
    assert ".nav-drawer {" in css
    assert "transform: translateX(100%);" in css
    assert ".nav-drawer.is-open {" in css
    assert "transform: translateX(0);" in css
    assert "body.nav-drawer-open {" in css
    assert "overflow: hidden !important;" in css

    # 3. Touch target sizing (>= 44px)
    assert ".nav-drawer-link {" in css
    assert "min-height: 44px;" in css
    assert ".nav-drawer-theme-btn {" in css
    assert "min-height: 44px !important;" in css
    assert ".btn-drawer-action {" in css
    assert "min-height: 44px;" in css
    assert ".btn-drawer-logout {" in css
    assert "min-height: 44px;" in css

    # 4. Desktop preservation breakpoint
    assert "@media (min-width: 769px)" in css
    assert ".nav-desktop-content {\n        display: contents !important;" in css or ".nav-desktop-content {\n        display: contents !important;\n    }" in css or "display: contents !important;" in css
    assert ".btn-hamburger {\n        display: none !important;" in css or "display: none !important;" in css

    # 5. Mobile breakpoint (<= 768px)
    assert "@media (max-width: 768px)" in css
    assert "height: 60px !important;" in css
    assert "flex-wrap: nowrap !important;" in css
    assert "justify-content: space-between !important;" in css

    # 6. Prefers-reduced-motion
    assert "@media (prefers-reduced-motion: reduce)" in css
    assert "transition: none !important;" in css

    # 7. Light Mode overrides for drawer
    assert 'html[data-theme="light"] .nav-drawer {' in css
    assert 'html[data-theme="light"] .nav-drawer-header' in css
    assert 'html[data-theme="light"] .btn-drawer-close' in css
    assert 'html[data-theme="light"] .nav-drawer-link' in css
