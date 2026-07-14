/**
 * Local execution dashboard — run mode 4.
 *
 *   npm run dashboard   →  http://localhost:4444
 *
 * Zero extra dependencies (plain node:http). Provides:
 *   GET  /                  dashboard UI (scripts/dashboard/index.html)
 *   GET  /api/scenarios     rows from config/execution-control.xlsx
 *   GET  /api/history       reports/run-history.json (newest first)
 *   GET  /api/status        { running, mode, startedAt }
 *   GET  /api/logs          SSE stream of the live run's console output
 *   POST /api/run           { mode, tags[], profile, env, browser, headless, screenshots }
 *   POST /api/stop          kill the in-flight run
 *   GET  /reports/*         static serving of report archives (dashboards, traces)
 *
 * Runs are spawned through the same funnel as every other mode
 * (scripts/run.js / excelRunner), so timestamped archives + run-history
 * keep working exactly the same.
 */
const http = require('http');
const path = require('path');
const fs = require('fs');
const { spawn, execSync } = require('child_process');
const { readSheet } = require('../src/helpers/excelReader');

const ROOT = path.resolve(__dirname, '..');
const REPORTS_DIR = path.join(ROOT, 'reports');
const CONTROL_XLSX = path.join(ROOT, 'config', 'execution-control.xlsx');
const UI_FILE = path.join(__dirname, 'dashboard', 'index.html');
const PORT = Number(process.env.DASHBOARD_PORT || 4444);

const MIME = {
  '.html': 'text/html; charset=utf-8',
  '.css': 'text/css',
  '.js': 'application/javascript',
  '.json': 'application/json',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml',
  '.ico': 'image/x-icon',
  '.woff2': 'font/woff2',
  '.zip': 'application/zip',
  '.txt': 'text/plain; charset=utf-8',
};

// ---------------------------------------------------------------- run state
let child = null;
let runInfo = null; // { mode, startedAt, label }
let logBuffer = []; // last N lines so late SSE clients catch up
const sseClients = new Set();
const MAX_BUFFER = 500;

function broadcast(event, data) {
  const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
  for (const res of sseClients) res.write(payload);
}

function pushLog(line) {
  logBuffer.push(line);
  if (logBuffer.length > MAX_BUFFER) logBuffer = logBuffer.slice(-MAX_BUFFER);
  broadcast('log', line);
}

function startRun({ mode, tags = [], profile, env, browser, headless, screenshots }) {
  if (child) throw new Error('A run is already in progress');

  let args;
  let label;
  if (mode === 'excel') {
    args = [path.join(ROOT, 'src', 'runners', 'excelRunner.js')];
    label = 'Excel control sheet (Run = YES)';
  } else if (mode === 'profile') {
    args = [path.join(ROOT, 'scripts', 'run.js'), '--profile', profile];
    label = `Profile: ${profile}`;
  } else {
    if (!tags.length) throw new Error('No scenarios selected');
    const expr = tags.map((t) => (t.startsWith('@') ? t : `@${t}`)).join(' or ');
    args = [path.join(ROOT, 'scripts', 'run.js'), '--tags', expr];
    label = `Selected: ${tags.join(', ')}`;
  }

  const childEnv = { ...process.env };
  if (env) childEnv.ENV = env;
  if (browser) childEnv.BROWSER = browser;
  if (headless !== undefined) childEnv.HEADLESS = String(headless);
  if (screenshots) childEnv.STEP_SCREENSHOTS = screenshots;

  logBuffer = [];
  runInfo = { mode, label, startedAt: new Date().toISOString() };
  pushLog(`>>> ${label}  [ENV=${childEnv.ENV || 'qa'} BROWSER=${childEnv.BROWSER || 'chromium'} HEADLESS=${childEnv.HEADLESS || 'true'}]`);

  child = spawn(process.execPath, args, { cwd: ROOT, env: childEnv });
  child.stdout.on('data', (d) => d.toString().split(/\r?\n/).filter(Boolean).forEach(pushLog));
  child.stderr.on('data', (d) => d.toString().split(/\r?\n/).filter(Boolean).forEach(pushLog));
  child.on('close', (code) => {
    pushLog(`>>> Run finished with exit code ${code}`);
    broadcast('done', { code });
    child = null;
    runInfo = null;
  });
}

function stopRun() {
  if (!child) return false;
  pushLog('>>> Stop requested — killing run...');
  if (process.platform === 'win32') {
    try { execSync(`taskkill /pid ${child.pid} /T /F`); } catch { /* already gone */ }
  } else {
    child.kill('SIGTERM');
  }
  return true;
}

// ---------------------------------------------------------------- helpers
function json(res, code, body) {
  res.writeHead(code, { 'Content-Type': 'application/json' });
  res.end(JSON.stringify(body));
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let data = '';
    req.on('data', (c) => (data += c));
    req.on('end', () => {
      try { resolve(data ? JSON.parse(data) : {}); } catch (e) { reject(e); }
    });
  });
}

function serveStatic(res, baseDir, relPath) {
  const filePath = path.normalize(path.join(baseDir, relPath));
  if (!filePath.startsWith(baseDir)) return json(res, 403, { error: 'Forbidden' });
  if (!fs.existsSync(filePath) || !fs.statSync(filePath).isFile()) {
    return json(res, 404, { error: 'Not found' });
  }
  res.writeHead(200, { 'Content-Type': MIME[path.extname(filePath).toLowerCase()] || 'application/octet-stream' });
  fs.createReadStream(filePath).pipe(res);
}

// ---------------------------------------------------------------- server
const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);
  const route = `${req.method} ${url.pathname}`;

  try {
    if (route === 'GET /') return serveStatic(res, path.dirname(UI_FILE), 'index.html');

    if (route === 'GET /api/scenarios') {
      const rows = readSheet(CONTROL_XLSX, 'ExecutionControl');
      return json(res, 200, rows);
    }

    if (route === 'GET /api/history') {
      const file = path.join(REPORTS_DIR, 'run-history.json');
      const history = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : [];
      return json(res, 200, history.slice().reverse());
    }

    if (route === 'GET /api/status') {
      return json(res, 200, { running: !!child, ...(runInfo || {}) });
    }

    if (route === 'GET /api/logs') {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      });
      for (const line of logBuffer) res.write(`event: log\ndata: ${JSON.stringify(line)}\n\n`);
      sseClients.add(res);
      req.on('close', () => sseClients.delete(res));
      return;
    }

    if (route === 'POST /api/run') {
      if (child) return json(res, 409, { error: 'A run is already in progress' });
      const body = await readBody(req);
      startRun(body);
      return json(res, 200, { started: true });
    }

    if (route === 'POST /api/stop') {
      return json(res, 200, { stopped: stopRun() });
    }

    if (req.method === 'GET' && url.pathname.startsWith('/reports/')) {
      return serveStatic(res, REPORTS_DIR, decodeURIComponent(url.pathname.slice('/reports/'.length)));
    }

    json(res, 404, { error: 'Not found' });
  } catch (e) {
    json(res, 400, { error: e.message });
  }
});

server.listen(PORT, () => {
  console.log('='.repeat(60));
  console.log(`  Test Automation Dashboard  →  http://localhost:${PORT}`);
  console.log('='.repeat(60));
});
