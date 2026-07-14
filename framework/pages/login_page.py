from ..selectors import login_selectors as SEL
from .base_page import BasePage


class LoginPage(BasePage):
    def goto(self):
        self.open("/")
        self.expect_visible(SEL.LOGO, "App logo")

    def login(self, username: str, password: str):
        self.fill(SEL.USERNAME_INPUT, username, "Username")
        self.fill(SEL.PASSWORD_INPUT, password, "Password", mask=True)
        self.click(SEL.LOGIN_BUTTON, "Login button")

    def verify_error(self, expected_message: str):
        self.expect_visible(SEL.ERROR_MESSAGE, "Login error")
        self.expect_contains_text(SEL.ERROR_MESSAGE, expected_message, "Login error")
