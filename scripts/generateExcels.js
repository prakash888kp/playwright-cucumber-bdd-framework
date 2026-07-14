/**
 * Generates the two framework workbooks:
 *   config/execution-control.xlsx — flip Run to YES/NO per scenario
 *   config/testdata.xlsx          — one sheet per module, rows keyed by TC_ID
 *
 * Re-running OVERWRITES both files — commit your edits or back them up first.
 */
const XLSX = require('xlsx');
const path = require('path');
const fs = require('fs');

const configDir = path.resolve(__dirname, '..', 'config');
fs.mkdirSync(configDir, { recursive: true });

// ---------- 1. Execution control ----------
const executionRows = [
  { Feature: 'SauceDemo Login', ScenarioID: 'TC_UI_001', ScenarioName: 'Successful login with valid credentials', Type: 'UI', Run: 'YES' },
  { Feature: 'SauceDemo Login', ScenarioID: 'TC_UI_002', ScenarioName: 'Login fails with locked out user', Type: 'UI', Run: 'YES' },
  { Feature: 'Shopping cart', ScenarioID: 'TC_UI_003', ScenarioName: 'Add a product to the cart', Type: 'UI', Run: 'YES' },
  { Feature: 'Users API', ScenarioID: 'TC_API_001', ScenarioName: 'Get a single user', Type: 'API', Run: 'YES' },
  { Feature: 'Users API', ScenarioID: 'TC_API_002', ScenarioName: 'Create a new post', Type: 'API', Run: 'YES' },
  { Feature: 'RAG Knowledge Base', ScenarioID: 'TC_RAG_001', ScenarioName: 'Answer is grounded and covers expected keywords', Type: 'RAG', Run: 'NO' },
  { Feature: 'RAG Knowledge Base', ScenarioID: 'TC_RAG_002', ScenarioName: 'Answer passes LLM-as-judge evaluation', Type: 'RAG', Run: 'NO' },
];

const controlWb = XLSX.utils.book_new();
const controlWs = XLSX.utils.json_to_sheet(executionRows);
controlWs['!cols'] = [{ wch: 22 }, { wch: 14 }, { wch: 50 }, { wch: 8 }, { wch: 8 }];
XLSX.utils.book_append_sheet(controlWb, controlWs, 'ExecutionControl');
XLSX.writeFile(controlWb, path.join(configDir, 'execution-control.xlsx'));
console.log('Created config/execution-control.xlsx');

// ---------- 2. Test data ----------
const loginData = [
  { TC_ID: 'TC_UI_001', Username: 'standard_user', Password: 'secret_sauce', ExpectedError: '' },
  { TC_ID: 'TC_UI_002', Username: 'locked_out_user', Password: 'secret_sauce', ExpectedError: 'Sorry, this user has been locked out.' },
];

const cartData = [
  { TC_ID: 'TC_UI_003', ProductName: 'Sauce Labs Backpack', Quantity: 1 },
];

const apiData = [
  { TC_ID: 'TC_API_001', Method: 'GET', Endpoint: '/users/1', Payload: '', ExpectedStatus: 200 },
  { TC_ID: 'TC_API_002', Method: 'POST', Endpoint: '/posts', Payload: '{"title":"qa post","body":"created by framework","userId":1}', ExpectedStatus: 201 },
];

const ragData = [
  { TC_ID: 'TC_RAG_001', Question: 'What is our refund policy?', ExpectedKeywords: 'refund;30 days;original payment method', KnowledgeBaseId: '' },
  { TC_ID: 'TC_RAG_002', Question: 'How do I reset my password?', ExpectedKeywords: 'reset;password;email', KnowledgeBaseId: '' },
];

const dataWb = XLSX.utils.book_new();
for (const [sheetName, rows] of Object.entries({
  LoginData: loginData,
  CartData: cartData,
  APIData: apiData,
  RAGData: ragData,
})) {
  const ws = XLSX.utils.json_to_sheet(rows);
  ws['!cols'] = Object.keys(rows[0]).map((k) => ({
    wch: Math.max(k.length + 2, ...rows.map((r) => String(r[k]).length + 2), 12),
  }));
  XLSX.utils.book_append_sheet(dataWb, ws, sheetName);
}
XLSX.writeFile(dataWb, path.join(configDir, 'testdata.xlsx'));
console.log('Created config/testdata.xlsx');
