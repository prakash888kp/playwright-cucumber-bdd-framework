@ui @cart
Feature: Shopping cart
  Verify products can be added to the cart

  @regression @TC_UI_003
  Scenario: Add a product to the cart
    Given I load login data for "TC_UI_001"
    And I login with the loaded credentials
    When I add product for "TC_UI_003" to the cart
    Then the cart badge should show 1 item
