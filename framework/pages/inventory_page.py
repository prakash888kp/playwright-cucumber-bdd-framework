import re

from ..selectors import inventory_selectors as SEL
from .base_page import BasePage


class InventoryPage(BasePage):
    def verify_loaded(self):
        self.expect_url(re.compile(r"inventory\.html"))
        self.expect_text(SEL.PAGE_HEADER, "Products", "Page header")

    def add_item_to_cart(self, item_name: str):
        item = self.locate(SEL.INVENTORY_ITEM).filter(has_text=item_name)
        self.log.info(f'Add to cart: "{item_name}"')
        item.get_by_role("button", name="Add to cart").click()

    def verify_cart_count(self, count):
        self.expect_text(SEL.CART_BADGE, str(count), "Cart badge")

    def sort_by(self, value: str):
        self.select_by_value(SEL.SORT_DROPDOWN, value, "Sort dropdown")
