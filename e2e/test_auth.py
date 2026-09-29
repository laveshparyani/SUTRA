"""Sign-in, rejection and sign-out, driven through the interface."""

from conftest import ADMIN, VIEWER, sign_in


def test_valid_credentials_reach_the_application(page, server):
    sign_in(page, server, *ADMIN)
    assert page.locator("nav a[href='/']").is_visible()
    assert page.locator(".stat-row").count() >= 1, "overview did not render its headline figures"
    assert not page.uncaught_errors, page.uncaught_errors


def test_wrong_password_is_refused_and_stays_on_login(page, server):
    page.goto(f"{server}/login", wait_until="commit")
    page.wait_for_selector("input[placeholder='username']")
    page.fill("input[placeholder='username']", ADMIN[0])
    page.fill("input[placeholder='password']", "definitely-not-the-password")
    page.click("button:has-text('Sign In')")
    page.wait_for_timeout(2500)

    assert page.locator("input[placeholder='password']").count() == 1, \
        "a failed sign-in must leave the operator on the login form"
    assert page.locator("nav a[href='/']").count() == 0, "application shell must not render"


def test_sign_out_returns_to_login(page, server):
    sign_in(page, server, *VIEWER)
    page.click("button:has-text('Sign Out')")
    page.wait_for_selector("input[placeholder='username']", timeout=20000)
    assert page.locator("nav a[href='/']").count() == 0
