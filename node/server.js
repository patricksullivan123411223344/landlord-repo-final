const fs = require('fs');
const http = require('http');
const https = require('https');
const path = require('path');
const express = require('express');
const { createProxyMiddleware } = require('http-proxy-middleware');
const dotenv = require('dotenv');

dotenv.config({ path: path.join(__dirname, '..', '.env') });

const app = express();
const ROOT = path.join(__dirname, '..');
const PYTHON_TARGET = process.env.PYTHON_BACKEND_URL || 'http://127.0.0.1:8000';
const NODE_PORT = Number(process.env.NODE_PORT || 3000);
const USE_HTTPS = String(process.env.NODE_USE_HTTPS || 'false').toLowerCase() === 'true';
const SSL_KEY_PATH = process.env.NODE_SSL_KEY_PATH || '';
const SSL_CERT_PATH = process.env.NODE_SSL_CERT_PATH || '';

const apiProxy = createProxyMiddleware({
  pathFilter: ['/api', '/analyze', '/zips', '/health', '/robots.txt'],
  target: PYTHON_TARGET,
  changeOrigin: true,
  ws: false,
  timeout: 45000,
  proxyTimeout: 45000,
  onError: (_err, req, res) => {
    if (!res.headersSent) {
      res.status(502).json({
        error: 'python_backend_unreachable',
        message: `Could not reach Python backend at ${PYTHON_TARGET}`,
        path: req.originalUrl,
      });
    }
  },
});

app.use(apiProxy);

app.use('/css', express.static(path.join(ROOT, 'css')));
app.use('/js', express.static(path.join(ROOT, 'js')));

app.get('/', (_req, res) => {
  res.sendFile(path.join(ROOT, 'index.html'));
});

app.get('/rating', (_req, res) => {
  res.sendFile(path.join(ROOT, 'html', 'ratingPage.html'));
});

app.get('/fair-rent', (_req, res) => {
  res.sendFile(path.join(ROOT, 'html', 'ri-fair-rent.html'));
});

app.get('/fair-rent/manage', (_req, res) => {
  res.setHeader('X-Robots-Tag', 'noindex, nofollow');
  res.sendFile(path.join(ROOT, 'html', 'admin.html'));
});

app.use((_req, res) => {
  res.status(404).send('Not found');
});

function startHttpServer() {
  const server = http.createServer(app);
  server.listen(NODE_PORT, () => {
    console.log(`[tenant-shield-node] HTTP gateway listening on http://127.0.0.1:${NODE_PORT}`);
    console.log(`[tenant-shield-node] Proxying API requests to ${PYTHON_TARGET}`);
  });
}

function startHttpsServer() {
  if (!SSL_KEY_PATH || !SSL_CERT_PATH) {
    throw new Error('NODE_USE_HTTPS=true but NODE_SSL_KEY_PATH/NODE_SSL_CERT_PATH are not set');
  }

  const keyPath = path.isAbsolute(SSL_KEY_PATH) ? SSL_KEY_PATH : path.join(ROOT, SSL_KEY_PATH);
  const certPath = path.isAbsolute(SSL_CERT_PATH) ? SSL_CERT_PATH : path.join(ROOT, SSL_CERT_PATH);

  const key = fs.readFileSync(keyPath);
  const cert = fs.readFileSync(certPath);

  const server = https.createServer({ key, cert }, app);
  server.listen(NODE_PORT, () => {
    console.log(`[tenant-shield-node] HTTPS gateway listening on https://127.0.0.1:${NODE_PORT}`);
    console.log(`[tenant-shield-node] Proxying API requests to ${PYTHON_TARGET}`);
  });
}

try {
  if (USE_HTTPS) startHttpsServer();
  else startHttpServer();
} catch (err) {
  console.error('[tenant-shield-node] Failed to start gateway:', err.message);
  process.exit(1);
}
