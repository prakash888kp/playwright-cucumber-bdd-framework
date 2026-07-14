@ui @login
Feature: SauceDemo Login
  As a registered user
  I want to log in to the store
  So that I can browse and purchase products

  @smoke @TC_UI_001
  Scenario: Successful login with valid credentials
    Given I load login data for "TC_UI_001"
    When I login with the loaded credentials
    Then I should land on the inventory page
    And the page should match the visual baseline "inventory"

  @regression @TC_UI_002
  Scenario: Login fails with locked out user
    Given I load login data for "TC_UI_002"
    When I login with the loaded credentials
    Then I should see the login error from test data
