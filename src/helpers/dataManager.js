/**
 * Test data manager — serves rows from config/testdata.xlsx keyed by TC_ID.
 * Sheets are cached per process; each sheet must have a TC_ID column.
 *
 * Usage in steps:  const data = dataManager.getData('LoginData', 'TC_UI_001');
 */
const path = require('path');
const { readSheet } = require('./excelReader');
const { logger } = require('./logger');

const TESTDATA_FILE = path.resolve(__dirname, '..', '..', 'config', 'testdata.xlsx');
const cache = new Map();

function getSheet(sheetName) {
  if (!cache.has(sheetName)) {
    cache.set(sheetName, readSheet(TESTDATA_FILE, sheetName));
    logger.debug(`Loaded test data sheet "${sheetName}" (${cache.get(sheetName).length} rows)`);
  }
  return cache.get(sheetName);
}

/** Get a single row by TC_ID. Throws if missing so bad data fails fast. */
function getData(sheetName, tcId) {
  const row = getSheet(sheetName).find((r) => String(r.TC_ID).trim() === String(tcId).trim());
  if (!row) {
    throw new Error(`No test data row with TC_ID="${tcId}" in sheet "${sheetName}"`);
  }
  return row;
}

/** Get all rows of a sheet (for data-driven loops). */
function getAll(sheetName) {
  return getSheet(sheetName);
}

module.exports = { getData, getAll, TESTDATA_FILE };
