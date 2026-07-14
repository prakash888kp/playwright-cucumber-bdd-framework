const { BasePage } = require('./basePage');
const SEL = require('../selectors/loginSelectors');

class LoginPage extends BasePage {
  async goto() {
    await this.open('/');
    await this.expectVisible(SEL.LOGO, 'App logo');
  }

  async login(username, password) {
    await this.fill(SEL.USERNAME_INPUT, username, 'Username');
    await this.fill(SEL.PASSWORD_INPUT, password, 'Password', { mask: true });
    await this.click(SEL.LOGIN_BUTTON, 'Login button');
  }

  async verifyError(expectedMessage) {
    await this.expectVisible(SEL.ERROR_MESSAGE, 'Login error');
    await this.expectContainsText(SEL.ERROR_MESSAGE, expectedMessage, 'Login error');
  }
}

module.exports = { LoginPage };
