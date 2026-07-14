"""UI step definitions — pure orchestration via context.pages, no locators.
@step matches any Gherkin keyword (same text is reused as Given/When across features).
"""
from pytest_bdd import parsers, step

from framework.helpers import data_manager
from framework.helpers.visual import assert_visual_match


@step(parsers.parse('I load login data for "{tc_id}"'))
def load_login_data(context, tc_id):
    context.data["login"] = data_manager.get_data("LoginData", tc_id)
    context.log.info(f"Loaded login data for {tc_id} (user: {context.data['login']['Username']})")


@step("I login with the loaded credentials")
def login_with_loaded_credentials(context):
    context.pages.login_page.goto()
    context.pages.login_page.login(
        context.data["login"]["Username"], context.data["login"]["Password"]
    )


@step("I should land on the inventory page")
def should_land_on_inventory(context):
    context.pages.inventory_page.verify_loaded()


@step("I should see the login error from test data")
def should_see_login_error(context):
    context.pages.login_page.verify_error(context.data["login"]["ExpectedError"])


@step(parsers.parse('I add product for "{tc_id}" to the cart'))
def add_product_to_cart(context, tc_id):
    row = data_manager.get_data("CartData", tc_id)
    context.pages.inventory_page.add_item_to_cart(row["ProductName"])


@step(parsers.parse("the cart badge should show {count:d} item"))
def cart_badge_should_show(context, count):
    context.pages.inventory_page.verify_cart_count(count)


@step(parsers.parse('the page should match the visual baseline "{name}"'))
def page_matches_visual_baseline(context, name):
    assert_visual_match(context.page, name, context)
