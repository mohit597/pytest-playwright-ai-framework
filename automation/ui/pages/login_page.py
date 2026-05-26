import os
from playwright.sync_api import Page, expect
from .base_page import BasePage


class LoginPage(BasePage):
    """
    Page object for the InvenTree login screen (React frontend, Mantine UI).

    Selectors use aria-label attributes — stable across React re-renders.
    InvenTree v1.3.0+ uses aria-label instead of Django-template id attributes.
    """

    URL_PATH = "/web/login"

    USERNAME_INPUT = "[aria-label='login-username']"
    PASSWORD_INPUT = "[aria-label='login-password']"
    SUBMIT_BUTTON  = "button[type='submit']"

    def open(self):
        self.navigate(self.URL_PATH)
        self.page.wait_for_selector(self.USERNAME_INPUT, timeout=15000)
        return self

    def fill_credentials(self, username: str, password: str):
        self.page.fill(self.USERNAME_INPUT, username)
        self.page.fill(self.PASSWORD_INPUT, password)
        return self

    def submit(self):
        self.page.click(self.SUBMIT_BUTTON)
        self.page.wait_for_load_state("networkidle")
        return self

    def login(self, username: str | None = None, password: str | None = None):
        """Full login flow using env var credentials if not explicitly provided."""
        user = username or os.getenv("INVENTREE_USER", "admin")
        pwd  = password or os.getenv("INVENTREE_PASS", "inventree")
        self.open()
        self.fill_credentials(user, pwd)
        self.submit()
        self.assert_logged_in()
        return self

    def assert_logged_in(self):
        """Fail fast if login did not succeed — prevents confusing downstream errors."""
        still_on_login = (
            "/web/login" in self.page.url
            or self.page.locator(self.USERNAME_INPUT).is_visible()
        )
        if still_on_login:
            user = os.getenv("INVENTREE_USER", "admin")
            raise AssertionError(
                f"Login failed for user '{user}'. "
                "Verify INVENTREE_USER and INVENTREE_PASS environment variables."
            )

    def assert_login_error_shown(self):
        expect(
            self.page.locator("[role='alert'], .mantine-Alert-root").first
        ).to_be_visible(timeout=5000)
