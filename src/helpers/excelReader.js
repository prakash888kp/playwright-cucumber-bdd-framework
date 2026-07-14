/**
 * Excel reader — thin wrapper over `xlsx` used by both the execution-control
 * runner and the test-data manager.
 */
const XLSX = require('xlsx');
const fs = require('fs');

/** Read a sheet into an array of row objects (header row = keys). */
function readSheet(filePath, sheetName) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Excel file not found: ${filePath}. Run "npm run generate:excel" first.`);
  }
  const workbook = XLSX.readFile(filePath);
  const sheet = workbook.Sheets[sheetName];
  if (!sheet) {
    throw new Error(
      `Sheet "${sheetName}" not found in ${filePath}. Available: ${workbook.SheetNames.join(', ')}`
    );
  }
  return XLSX.utils.sheet_to_json(sheet, { defval: '' });
}

/** List sheet names in a workbook. */
function sheetNames(filePath) {
  return XLSX.readFile(filePath).SheetNames;
}

module.exports = { readSheet, sheetNames };
