"""PageManager — lazy page-object factory, one per scenario.

Steps never construct a page: use `context.pages.login_page` etc. Instances
are created on first access, cached for the scenario, and share the
scenario-scoped logger so page actions appear under the scenario label.

Adding a page: import it and add one property.
"""
from ..pages.inventory_page import InventoryPage
from ..pages.login_page import LoginPage


class PageManager:
    def __init__(self, page, log):
        self.page = page
        self.log = log
        self._cache = {}

    def _get(self, name, ctor):
        if name not in self._cache:
            self._cache[name] = ctor(self.page, self.log)
        return self._cache[name]

    @property
    def login_page(self) -> LoginPage:
        return self._get("login_page", LoginPage)

    @property
    def inventory_page(self) -> InventoryPage:
        return self._get("inventory_page", InventoryPage)
