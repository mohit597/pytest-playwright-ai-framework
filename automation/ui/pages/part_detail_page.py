from playwright.sync_api import Page, expect
from .base_page import BasePage


class PartDetailPage(BasePage):
    """
    Page object for InvenTree Part detail view (React frontend).

    Tab navigation uses direct URL paths:
      /web/part/{pk}/{tab_slug}
    Note: 'details' tab is at /web/part/{pk}/details (no nesting)
    Available tabs: details, stock, allocations, used_in, pricing,
                    suppliers, purchase_orders, related_parts,
                    parameters, attachments, notes

    Action menus (aria-label):
      action-menu-part-actions  — edit, duplicate, delete part
      action-menu-stock-actions — add stock item
      action-menu-add-parameters — add parameter to part
    """

    # Action menus
    PART_ACTIONS_MENU = "[aria-label='action-menu-part-actions']"
    STOCK_ACTIONS_MENU = "[aria-label='action-menu-stock-actions']"
    ADD_PARAMETERS_MENU = "[aria-label='action-menu-add-parameters']"

    # Part actions menu items
    EDIT_PART_ITEM = "[aria-label='action-menu-part-actions-edit']"
    DUPLICATE_PART_ITEM = "[aria-label='action-menu-part-actions-duplicate']"
    DELETE_PART_ITEM = "[aria-label='action-menu-part-actions-delete']"

    # Stock action menu items
    ADD_STOCK_ITEM = "[aria-label='action-menu-stock-actions-add-stock']"

    # Modal
    MODAL = "[role='dialog']"
    SUBMIT_BUTTON = "[role='dialog'] button:has-text('Submit')"
    DELETE_CONFIRM_BUTTON = "[role='dialog'] button:has-text('Delete')"

    # Tab name constants for assertions
    TAB_DETAILS = "Part Details"
    TAB_STOCK = "Stock"
    TAB_PARAMETERS = "Parameters"
    TAB_SUPPLIERS = "Suppliers"
    TAB_ALLOCATIONS = "Allocations"
    TAB_USED_IN = "Used In"

    # Tab names mapped to URL slugs
    TABS = {
        "details": "details",
        "stock": "stock",
        "allocations": "allocations",
        "used_in": "used_in",
        "pricing": "pricing",
        "suppliers": "suppliers",
        "purchase_orders": "purchase_orders",
        "related_parts": "related_parts",
        "parameters": "parameters",
        "attachments": "attachments",
        "notes": "notes",
    }

    def __init__(self, page: Page):
        super().__init__(page)
        self._current_pk = None

    def open(self, part_pk: int):
        self._current_pk = part_pk
        self.navigate(f"/web/part/{part_pk}/")
        self.wait_for_load()
        self.page.wait_for_selector(self.PART_ACTIONS_MENU, timeout=15000)
        return self

    def navigate_to_tab(self, tab: str):
        """Navigate to a tab by URL — most reliable approach.
        URL pattern: /web/part/{pk}/{slug}  (NOT /web/part/{pk}/details/{slug})
        Exception: 'details' tab lives at /web/part/{pk}/details
        """
        slug = self.TABS.get(tab, tab)
        self.navigate(f"/web/part/{self._current_pk}/{slug}")
        self.wait_for_load()
        # Wait for the *active* tab panel to become visible.
        # .first would grab the details panel (always first in DOM) which is
        # hidden when any other tab is active — filter to visible panels only.
        expect(self.page.locator("[role='tabpanel']:visible").first).to_be_visible(timeout=8000)
        return self

    def click_stock_tab(self):
        return self.navigate_to_tab("stock")

    def click_parameters_tab(self):
        return self.navigate_to_tab("parameters")

    def click_suppliers_tab(self):
        return self.navigate_to_tab("suppliers")

    def click_attachments_tab(self):
        return self.navigate_to_tab("attachments")

    def click_related_tab(self):
        return self.navigate_to_tab("related_parts")

    def click_allocations_tab(self):
        return self.navigate_to_tab("allocations")

    def click_used_in_tab(self):
        return self.navigate_to_tab("used_in")

    def is_tab_visible(self, tab_text: str) -> bool:
        return self.page.get_by_role("tab", name=tab_text).is_visible()

    def is_bom_tab_visible(self) -> bool:
        return self.is_tab_visible("Bill of Materials") or self.is_tab_visible("BOM")

    def is_variants_tab_visible(self) -> bool:
        return self.is_tab_visible("Variants")

    def is_suppliers_tab_visible(self) -> bool:
        return self.is_tab_visible("Suppliers")

    def is_allocated_tab_visible(self) -> bool:
        return self.is_tab_visible("Allocations")

    def open_part_actions(self):
        self.page.locator(self.PART_ACTIONS_MENU).click()
        # Wait for the first menu item to appear — confirms dropdown is open
        expect(self.page.locator(self.EDIT_PART_ITEM)).to_be_visible(timeout=5000)
        return self

    def click_edit_part(self):
        self.open_part_actions()
        self.page.locator(self.EDIT_PART_ITEM).click()
        self.page.wait_for_selector(self.MODAL, timeout=8000)
        return self

    def click_duplicate_part(self):
        self.open_part_actions()
        self.page.locator(self.DUPLICATE_PART_ITEM).click()
        self.page.wait_for_selector(self.MODAL, timeout=8000)
        return self

    def click_add_stock(self):
        """Create a new stock item. Navigate to Stock tab first, then click the add button."""
        self.navigate_to_tab("stock")
        self.page.wait_for_selector("[aria-label='action-button-add-stock-item']", timeout=10000)
        self.page.locator("[aria-label='action-button-add-stock-item']").click()
        self.page.wait_for_selector(self.MODAL, timeout=8000)
        return self

    def fill_modal_field(self, label: str, value: str):
        self.page.locator(self.MODAL).get_by_label(label).fill(value)
        return self

    def submit_modal(self):
        self.page.locator(self.SUBMIT_BUTTON).click()
        self.wait_for_load()
        return self

    def add_parameter(self, template_name: str, value: str):
        """Add a parameter to the part. template_name is the parameter template name string."""
        self.click_parameters_tab()
        self.page.wait_for_selector(self.ADD_PARAMETERS_MENU, timeout=10000)
        self.page.locator(self.ADD_PARAMETERS_MENU).click()
        # Wait for the dropdown item to be visible before clicking it
        self.page.wait_for_selector(
            "[aria-label='action-menu-add-parameters-create-parameter']", timeout=5000
        )
        add_item = self.page.locator("[aria-label='action-menu-add-parameters-create-parameter']")
        if add_item.is_visible():
            add_item.click()
        self.page.wait_for_selector(self.MODAL, timeout=8000)
        modal = self.page.locator(self.MODAL)
        # Template field is a react-select; fill by name then pick from dropdown
        template_input = modal.locator("[aria-label='related-field-template']")
        template_input.fill(template_name)
        self.page.wait_for_selector(f"[role='option']:has-text('{template_name}')", timeout=5000)
        self.page.locator(f"[role='option']:has-text('{template_name}')").first.click()
        modal.locator("[aria-label='text-field-data']").fill(value)
        self.submit_modal()
        return self

    def assert_tab_visible(self, tab_text: str):
        expect(self.page.get_by_role("tab", name=tab_text)).to_be_visible()

    def assert_tab_not_visible(self, tab_text: str):
        expect(self.page.get_by_role("tab", name=tab_text)).not_to_be_visible()
