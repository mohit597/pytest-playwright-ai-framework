from playwright.sync_api import Page, expect
from .base_page import BasePage


class CategoryPage(BasePage):
    """Page object for InvenTree Part Category views (React frontend)."""

    URL_PATH = "/web/part/category/index/"
    SUBCATEGORIES_TAB_URL = "/web/part/category/index/subcategories"

    # Create category: direct action button on subcategories tab (no dropdown menu)
    ADD_CATEGORY_BUTTON = "[aria-label='action-button-add-part-category']"

    MODAL = "[role='dialog']"
    SUBMIT_BUTTON = "[role='dialog'] button:has-text('Submit')"

    # Category detail action menu
    CATEGORY_ACTIONS_MENU = "[aria-label='action-menu-category-actions']"
    DELETE_ITEM = "[aria-label='action-menu-category-actions-delete']"

    def __init__(self, page: Page):
        super().__init__(page)

    def open(self):
        self.navigate(self.URL_PATH)
        self.wait_for_load()
        return self

    def open_category(self, category_pk: int):
        self.navigate(f"/web/part/category/{category_pk}/")
        self.wait_for_load()
        self.page.wait_for_selector(self.CATEGORY_ACTIONS_MENU, timeout=10000)
        return self

    def open_category_parts_tab(self, category_pk: int):
        """Navigate directly to the Parts sub-tab of a category."""
        self.navigate(f"/web/part/category/{category_pk}/parts")
        self.wait_for_load()
        # Wait for table or empty-state indicator — confirms tab content has rendered
        self.page.wait_for_selector(
            "table, [role='grid'], .mantine-Table-root, [data-testid='no-items']",
            timeout=10000,
        )
        return self

    def create_category(self, name: str, description: str = "", parent_pk: int = None):
        if parent_pk:
            # Navigate to parent category subcategories tab
            self.navigate(f"/web/part/category/{parent_pk}/subcategories")
        else:
            self.navigate(self.SUBCATEGORIES_TAB_URL)
        self.wait_for_load()

        self.page.wait_for_selector(self.ADD_CATEGORY_BUTTON, timeout=15000)
        self.page.locator(self.ADD_CATEGORY_BUTTON).click()
        self.page.wait_for_selector(self.MODAL, timeout=8000)

        modal = self.page.locator(self.MODAL)
        modal.locator("[aria-label='text-field-name']").fill(name)
        if description:
            modal.locator("[aria-label='text-field-description']").fill(description)

        self.page.locator(self.SUBMIT_BUTTON).click()
        self.wait_for_load()
        return self

    def delete_current_category(self):
        self.page.locator(self.CATEGORY_ACTIONS_MENU).click()
        self.page.wait_for_selector(self.DELETE_ITEM, timeout=5000)
        self.page.locator(self.DELETE_ITEM).click()
        # Wait for modal AND for the Delete button inside it to be visible
        delete_confirm = self.page.locator("[role='dialog'] button:has-text('Delete')")
        delete_confirm.wait_for(state="visible", timeout=10000)
        delete_confirm.click()
        # Wait for modal to disappear (deletion processed) then wait for page to settle
        self.page.wait_for_selector(self.MODAL, state="detached", timeout=10000)
        self.wait_for_load()
        return self

    def get_breadcrumb_text(self) -> str:
        return self.page.locator("nav[aria-label='breadcrumb'], .mantine-Breadcrumbs-root").inner_text()

    def assert_category_visible(self, name: str):
        expect(self.page.get_by_text(name).first).to_be_visible()

    def assert_error_shown(self):
        expect(self.page.locator("[role='alert'], .mantine-Alert-root").first).to_be_visible()
