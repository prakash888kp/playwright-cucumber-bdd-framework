@rag @bedrock
Feature: RAG answer validation via Amazon Bedrock Knowledge Base
  Validate that the RAG pipeline returns grounded, relevant answers

  @regression @TC_RAG_001
  Scenario: Answer is grounded and covers expected keywords
    Given I load RAG data for "TC_RAG_001"
    When I query the Bedrock knowledge base with the question from test data
    Then the RAG answer should contain the expected keywords
    And the RAG answer should include citations

  @regression @TC_RAG_002
  Scenario: Answer passes LLM-as-judge faithfulness evaluation
    Given I load RAG data for "TC_RAG_002"
    When I query the Bedrock knowledge base with the question from test data
    Then the RAG answer should pass the LLM judge evaluation
