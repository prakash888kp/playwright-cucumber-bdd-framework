@api @users
Feature: Users API
  Contract checks against the users service

  @smoke @TC_API_001
  Scenario: Get a single user
    Given I load API data for "TC_API_001"
    When I send a GET request to the endpoint from test data
    Then the response status should match the expected status
    And the response field "name" should not be empty

  @regression @TC_API_002
  Scenario: Create a new post
    Given I load API data for "TC_API_002"
    When I send a POST request with the payload from test data
    Then the response status should match the expected status
    And the response field "id" should not be empty
