from playwright.sync_api import Page, expect
from .base_page import BasePage


class PartCreatePage(BasePage):
    """
    Page object for creating a new Part in InvenTree React frontend.

    The Create Part form is a modal launched from the Parts table via
    an ActionDropdown. The parts table lives at the 'Parts' sub-tab of
    the category index page.

    Flow:
        1. Navigate to /web/part/category/index/details/parts
        2. Click ActionDropdown: aria-label='action-menu-add-parts'
        3. Click menu item: aria-label='action-menu-add-parts-create-part'
        4. Modal opens — fill fields by label
        5. Submit
    """

    URL_PATH = "/web/part/category/index/parts"

    ADD_PARTS_MENU = "[aria-label='action-menu-add-parts']"
    CREATE_PART_ITEM = "[aria-label='action-menu-add-parts-create-part']"
    MODAL = "[role='dialog']"
    SUBMIT_BUTTON = "[role='dialog'] button:has-text('Submit')"
    CANCEL_BUTTON = "[role='dialog'] button:has-text('Cancel')"
    FORM_ERRORS = ".mantine-TextInput-error, [role='alert']"

    def __init__(self, page: Page):
        super().__init__(page)

    def open(self):
        self.navigate(self.URL_PATH)
        self.wait_for_load()
        self.page.wait_for_selector(self.ADD_PARTS_MENU, timeout=15000)
        self.page.locator(self.ADD_PARTS_MENU).click()
        self.page.wait_for_selector(self.CREATE_PART_ITEM, timeout=5000)
        self.page.locator(self.CREATE_PART_ITEM).click()
        self.page.wait_for_selector(self.MODAL, timeout=10000)
        return self

    def _modal(self):
        return self.page.locator(self.MODAL)

    def fill_name(self, name: str):
        self._modal().locator("[aria-label='text-field-name']").fill(name)
        return self

    def fill_description(self, description: str):
        self._modal().locator("[aria-label='text-field-description']").fill(description)
        return self

    def fill_ipn(self, ipn: str):
        self._modal().locator("[aria-label='text-field-IPN']").fill(ipn)
        return self

    def fill_revision(self, revision: str):
        self._modal().locator("[aria-label='text-field-revision']").fill(revision)
        return self

    def fill_keywords(self, keywords: str):
        self._modal().locator("[aria-label='text-field-keywords']").fill(keywords)
        return self

    def fill_units(self, units: str):
        self._modal().locator("[aria-label='text-field-units']").fill(units)
        return self

    def select_category(self, category_name: str):
        """Type category name in the react-select dropdown and pick the match."""
        cat_input = self._modal().locator("[aria-label='related-field-category']")
        cat_input.fill(category_name)
        self.page.wait_for_selector(f"[role='option']:has-text('{category_name}')", timeout=5000)
        self.page.locator(f"[role='option']:has-text('{category_name}')").first.click()
        return self

    def submit(self):
        self.page.locator(self.SUBMIT_BUTTON).click()
        self.wait_for_load()
        return self

    def create_part(self, name: str, description: str, **kwargs):
        self.open()
        self.fill_name(name)
        self.fill_description(description)
        if "ipn" in kwargs:
            self.fill_ipn(kwargs["ipn"])
        if "revision" in kwargs:
            self.fill_revision(kwargs["revision"])
        if "keywords" in kwargs:
            self.fill_keywords(kwargs["keywords"])
        if "units" in kwargs:
            self.fill_units(kwargs["units"])
        self.submit()
        return self

    def assert_validation_error(self):
        expect(self.page.locator(self.FORM_ERRORS).first).to_be_visible()

    def assert_ipn_error(self):
        expect(self.page.locator(self.FORM_ERRORS).first).to_be_visible()

    def assert_name_error(self):
        expect(self.page.locator(self.FORM_ERRORS).first).to_be_visible()
