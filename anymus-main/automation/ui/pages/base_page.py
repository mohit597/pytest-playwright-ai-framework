import os
from playwright.sync_api import Page, expect


class BasePage:
    """Base page object providing common actions for all InvenTree pages."""

    def __init__(self, page: Page):
        self.page = page
        self.base_url = os.getenv("INVENTREE_URL", "http://inventree.localhost")

    def navigate(self, path: str = ""):
        self.page.goto(f"{self.base_url}{path}")

    def wait_for_load(self):
        self.page.wait_for_load_state("networkidle")

    def click(self, selector: str):
        locator = self.page.locator(selector)
        expect(locator).to_be_visible()
        locator.click()

    def fill(self, selector: str, value: str):
        locator = self.page.locator(selector)
        expect(locator).to_be_visible()
        locator.fill(value)

    def select_option(self, selector: str, value: str):
        self.page.locator(selector).select_option(value)

    def get_text(self, selector: str) -> str:
        return self.page.locator(selector).inner_text()

    def is_visible(self, selector: str) -> bool:
        return self.page.locator(selector).is_visible()

    def wait_for_selector(self, selector: str):
        self.page.wait_for_selector(selector)

    def wait_for_url(self, url_pattern: str):
        self.page.wait_for_url(url_pattern)

    def get_alert_text(self) -> str:
        return self.page.locator(".alert, .notification, [role='alert']").inner_text()

    def dismiss_modal(self):
        close = self.page.locator("button[data-dismiss='modal'], button.btn-close")
        if close.is_visible():
            close.click()
