"""Generates the two framework workbooks:
  config/execution-control.xlsx — flip Run to YES/NO per scenario
  config/testdata.xlsx          — one sheet per module, rows keyed by TC_ID

Re-running OVERWRITES both files — commit your edits or back them up first.
"""
from pathlib import Path

from openpyxl import Workbook

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
CONFIG_DIR.mkdir(exist_ok=True)

EXECUTION_ROWS = [
    {"Feature": "SauceDemo Login", "ScenarioID": "TC_UI_001", "ScenarioName": "Successful login with valid credentials", "Type": "UI", "Run": "YES"},
    {"Feature": "SauceDemo Login", "ScenarioID": "TC_UI_002", "ScenarioName": "Login fails with locked out user", "Type": "UI", "Run": "YES"},
    {"Feature": "Shopping cart", "ScenarioID": "TC_UI_003", "ScenarioName": "Add a product to the cart", "Type": "UI", "Run": "YES"},
    {"Feature": "Users API", "ScenarioID": "TC_API_001", "ScenarioName": "Get a single user", "Type": "API", "Run": "YES"},
    {"Feature": "Users API", "ScenarioID": "TC_API_002", "ScenarioName": "Create a new post", "Type": "API", "Run": "YES"},
    {"Feature": "RAG Knowledge Base", "ScenarioID": "TC_RAG_001", "ScenarioName": "Answer is grounded and covers expected keywords", "Type": "RAG", "Run": "NO"},
    {"Feature": "RAG Knowledge Base", "ScenarioID": "TC_RAG_002", "ScenarioName": "Answer passes LLM-as-judge evaluation", "Type": "RAG", "Run": "NO"},
]

TESTDATA_SHEETS = {
    "LoginData": [
        {"TC_ID": "TC_UI_001", "Username": "standard_user", "Password": "secret_sauce", "ExpectedError": ""},
        {"TC_ID": "TC_UI_002", "Username": "locked_out_user", "Password": "secret_sauce", "ExpectedError": "Sorry, this user has been locked out."},
    ],
    "CartData": [
        {"TC_ID": "TC_UI_003", "ProductName": "Sauce Labs Backpack", "Quantity": 1},
    ],
    "APIData": [
        {"TC_ID": "TC_API_001", "Method": "GET", "Endpoint": "/users/1", "Payload": "", "ExpectedStatus": 200},
        {"TC_ID": "TC_API_002", "Method": "POST", "Endpoint": "/posts", "Payload": '{"title":"qa post","body":"created by framework","userId":1}', "ExpectedStatus": 201},
    ],
    "RAGData": [
        {"TC_ID": "TC_RAG_001", "Question": "What is our refund policy?", "ExpectedKeywords": "refund;30 days;original payment method", "KnowledgeBaseId": ""},
        {"TC_ID": "TC_RAG_002", "Question": "How do I reset my password?", "ExpectedKeywords": "reset;password;email", "KnowledgeBaseId": ""},
    ],
}


def write_sheet(ws, rows):
    headers = list(rows[0].keys())
    ws.append(headers)
    for row in rows:
        ws.append([row[h] for h in headers])
    for idx, header in enumerate(headers, start=1):
        width = max(len(str(header)) + 2, *(len(str(r[header])) + 2 for r in rows), 12)
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = width


control_wb = Workbook()
control_ws = control_wb.active
control_ws.title = "ExecutionControl"
write_sheet(control_ws, EXECUTION_ROWS)
control_wb.save(CONFIG_DIR / "execution-control.xlsx")
print("Created config/execution-control.xlsx")

data_wb = Workbook()
data_wb.remove(data_wb.active)
for sheet_name, rows in TESTDATA_SHEETS.items():
    write_sheet(data_wb.create_sheet(sheet_name), rows)
data_wb.save(CONFIG_DIR / "testdata.xlsx")
print("Created config/testdata.xlsx")
