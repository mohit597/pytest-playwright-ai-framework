from playwright.sync_api import Page, expect
from .base_page import BasePage


class PartsListPage(BasePage):
    """Page object for InvenTree Parts list/category view (React frontend)."""

    URL_PATH = "/web/part"
    PARTS_TAB_URL = "/web/part/category/index/parts"

    NAV_PARTS_LINK = "a[href='/web/part']"
    BREADCRUMB_PARTS = "[aria-label='breadcrumb-0-parts']"

    def __init__(self, page: Page):
        super().__init__(page)

    def open(self):
        self.navigate(self.URL_PATH)
        self.wait_for_load()
        return self

    def open_parts_tab(self):
        self.navigate(self.PARTS_TAB_URL)
        self.wait_for_load()
        return self

    def click_part_by_name(self, name: str):
        link = self.page.get_by_role("link", name=name).first
        expect(link).to_be_visible()
        link.click()
        self.wait_for_load()
        return self

    def assert_part_in_list(self, name: str):
        expect(self.page.get_by_text(name).first).to_be_visible()

    def assert_part_not_in_list(self, name: str):
        expect(self.page.get_by_text(name)).not_to_be_visible()
