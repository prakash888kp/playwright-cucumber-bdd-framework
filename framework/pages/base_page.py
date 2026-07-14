"""BasePage — shared engine for all page objects.

 - locate(descriptor): resolves selector descriptors from framework/selectors/
   files into Playwright locators, keeping role/label-first priority.
 - Reusable, auto-logged action wrappers (click, fill, get_text, ...) so
   page objects stay declarative and every interaction lands in the log.

Playwright auto-waiting is relied on throughout — no arbitrary timeouts.
"""
import json
import os
from urllib.parse import urljoin

from playwright.sync_api import Locator, expect

from ..helpers.logger import logger


class BasePage:
    def __init__(self, page, log=logger):
        self.page = page
        self.log = log

    # ---------- Locator resolution ----------

    def locate(self, descriptor) -> Locator:
        """Resolve a selector descriptor into a Locator.
        Accepts: str (css/xpath) | {"role","name"} | {"label"} | {"placeholder"}
                 {"text"} | {"testId"} | {"css"} — optionally {"nth": n} or Locator passthrough.
        """
        if isinstance(descriptor, str):
            return self.page.locator(descriptor)
        if isinstance(descriptor, Locator):
            return descriptor

        if descriptor.get("role"):
            name = descriptor.get("name")
            loc = self.page.get_by_role(descriptor["role"], name=name) if name else self.page.get_by_role(descriptor["role"])
        elif descriptor.get("label"):
            loc = self.page.get_by_label(descriptor["label"])
        elif descriptor.get("placeholder"):
            loc = self.page.get_by_placeholder(descriptor["placeholder"])
        elif descriptor.get("text"):
            loc = self.page.get_by_text(descriptor["text"], exact=descriptor.get("exact", False))
        elif descriptor.get("testId"):
            loc = self.page.locator(f'[data-test="{descriptor["testId"]}"]')
        elif descriptor.get("css"):
            loc = self.page.locator(descriptor["css"])
        else:
            raise ValueError(f"Unknown selector descriptor: {descriptor}")

        nth = descriptor.get("nth")
        return loc.nth(nth) if nth is not None else loc

    @staticmethod
    def describe(descriptor) -> str:
        return descriptor if isinstance(descriptor, str) else json.dumps(descriptor)

    # ---------- Navigation ----------

    def open(self, pathname: str = "/"):
        url = urljoin(os.environ.get("BASE_URL", ""), pathname)
        self.log.info(f"Navigate: {url}")
        self.page.goto(url)

    def wait_for_load(self, state: str = "domcontentloaded"):
        self.page.wait_for_load_state(state)

    def title(self) -> str:
        return self.page.title()

    # ---------- Actions (auto-logged) ----------

    def click(self, descriptor, element_name: str = ""):
        self.log.info(f"Click: {element_name or self.describe(descriptor)}")
        self.locate(descriptor).click()

    def fill(self, descriptor, value, element_name: str = "", mask: bool = False):
        shown = "******" if mask else value
        self.log.info(f'Fill: {element_name or self.describe(descriptor)} = "{shown}"')
        self.locate(descriptor).fill(str(value))

    def select_by_value(self, descriptor, value, element_name: str = ""):
        self.log.info(f"Select: {element_name or self.describe(descriptor)} -> {value}")
        self.locate(descriptor).select_option(value)

    def hover(self, descriptor, element_name: str = ""):
        self.log.info(f"Hover: {element_name or self.describe(descriptor)}")
        self.locate(descriptor).hover()

    def press(self, descriptor, key: str, element_name: str = ""):
        self.log.info(f'Press "{key}" on {element_name or self.describe(descriptor)}')
        self.locate(descriptor).press(key)

    # ---------- Reads ----------

    def get_text(self, descriptor) -> str:
        text = self.locate(descriptor).text_content()
        return text.strip() if text else ""

    def is_visible(self, descriptor) -> bool:
        return self.locate(descriptor).is_visible()

    def count(self, descriptor) -> int:
        return self.locate(descriptor).count()

    # ---------- Assertions (auto-logged, auto-retrying via expect) ----------

    def expect_visible(self, descriptor, element_name: str = ""):
        self.log.info(f"Assert visible: {element_name or self.describe(descriptor)}")
        expect(self.locate(descriptor)).to_be_visible()

    def expect_text(self, descriptor, expected, element_name: str = ""):
        self.log.info(f'Assert text: {element_name or self.describe(descriptor)} = "{expected}"')
        expect(self.locate(descriptor)).to_have_text(str(expected))

    def expect_contains_text(self, descriptor, expected, element_name: str = ""):
        self.log.info(f'Assert contains: {element_name or self.describe(descriptor)} ~ "{expected}"')
        expect(self.locate(descriptor)).to_contain_text(str(expected))

    def expect_url(self, pattern):
        self.log.info(f"Assert URL matches: {pattern}")
        expect(self.page).to_have_url(pattern)
