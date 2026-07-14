/**
 * Winston logger — console + rolling file output.
 * Each run writes to logs/execution-<date>.log; scenario names are injected
 * via child loggers (see hooks.js) so every line is traceable to a scenario.
 */
const path = require('path');
const fs = require('fs');
const winston = require('winston');

const logDir = path.resolve(__dirname, '..', '..', 'logs');
if (!fs.existsSync(logDir)) fs.mkdirSync(logDir, { recursive: true });

const timestamp = new Date().toISOString().slice(0, 10);

const logFormat = winston.format.printf(({ level, message, label, timestamp }) => {
  return `${timestamp} [${level.toUpperCase()}]${label ? ` [${label}]` : ''} ${message}`;
});

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss.SSS' }),
    logFormat
  ),
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize({ level: false }),
        winston.format.timestamp({ format: 'HH:mm:ss' }),
        logFormat
      ),
    }),
    new winston.transports.File({
      filename: path.join(logDir, `execution-${timestamp}.log`),
      maxsize: 10 * 1024 * 1024,
      maxFiles: 5,
      tailable: true,
    }),
  ],
});

/** Create a scenario-scoped logger: logger lines get a [Scenario Name] label. */
function scenarioLogger(label) {
  return logger.child({ label });
}

module.exports = { logger, scenarioLogger };
