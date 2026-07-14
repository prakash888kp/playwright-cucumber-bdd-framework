/**
 * Login page selectors — the ONLY place login locators live.
 * Descriptor types resolved by BasePage.locate():
 *   { role, name } | { label } | { placeholder } | { text } | { testId } | { css } | 'raw-string'
 * Prefer role/label/placeholder (resilient); fall back to testId, then css.
 */
module.exports = {
  USERNAME_INPUT: { placeholder: 'Username' },
  PASSWORD_INPUT: { placeholder: 'Password' },
  LOGIN_BUTTON: { role: 'button', name: 'Login' },
  ERROR_MESSAGE: { testId: 'error' },
  LOGO: { css: '.login_logo' },
};
