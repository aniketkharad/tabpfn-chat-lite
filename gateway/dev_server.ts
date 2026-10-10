import { Miniflare } from 'miniflare';
import path from 'path';
import fs from 'fs';

// Build the bundle first with Bun
const buildResult = await Bun.build({
  entrypoints: [path.resolve(__dirname, 'src/index.ts')],
  outdir: path.resolve(__dirname, 'dist'),
  target: 'browser',
  external: ['cloudflare:workers'],
  minify: false,
});

if (!buildResult.success) {
  console.error('Build failed:', buildResult.logs);
  process.exit(1);
}

const frontendDist = path.resolve(__dirname, '../frontend/dist');

const MIME_TYPES: Record<string, string> = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8',
  '.json': 'application/json; charset=utf-8',
  '.svg': 'image/svg+xml',
  '.png': 'image/png',
  '.ico': 'image/x-icon',
  '.csv': 'text/csv; charset=utf-8',
};

const mf = new Miniflare({
  modules: true,
  scriptPath: path.resolve(__dirname, 'dist/index.js'),
  compatibilityDate: '2024-09-23',
  compatibilityFlags: ['nodejs_compat'],
  durableObjects: {
    ADMISSION_DO: { className: 'AdmissionDurableObject', useSQLite: true },
  },
  bindings: {
    BACKEND_URL: 'http://127.0.0.1:8000',
    DAILY_RUNS_PER_IP: '10',
    DAILY_RUNS_GLOBAL: '50',
    SESSION_TTL_SECONDS: '86400',
    TURNSTILE_SITE_KEY: '1x0000000000000000000000000000000AA',
    TURNSTILE_SECRET_KEY: '1x0000000000000000000000000000000AA',
    SESSION_SIGNING_SECRET: 'dev_session_secret_for_local_testing_only_32_chars',
    IP_SALT: 'dev_salt_1234567890_secret',
    GATEWAY_HMAC_SECRET_CURRENT: 'dev_gateway_hmac_secret_current_32_chars',
    GATEWAY_HMAC_SECRET_PREVIOUS: '',
    ADMIN_SECRET: 'dev_admin_secret_local',
  },
  serviceBindings: {
    ASSETS: async (request: Request) => {
      const url = new URL(request.url);
      let pathname = decodeURIComponent(url.pathname);
      if (pathname === '/') pathname = '/index.html';

      let filePath = path.join(frontendDist, pathname.replace(/^\/+/, ''));
      if (!fs.existsSync(filePath) || fs.statSync(filePath).isDirectory()) {
        // SPA fallback
        filePath = path.join(frontendDist, 'index.html');
      }

      if (!fs.existsSync(filePath)) {
        return new Response('Not found', { status: 404 });
      }

      const content = fs.readFileSync(filePath);
      const ext = path.extname(filePath).toLowerCase();
      const contentType = MIME_TYPES[ext] || 'application/octet-stream';

      return new Response(content, {
        headers: {
          'Content-Type': contentType,
        },
      });
    },
  },
  port: 8787,
  host: '127.0.0.1',
});

const url = await mf.ready;
console.log(`[gateway-dev] Gateway ready at http://127.0.0.1:8787`);

// Handle shutdown
process.on('SIGINT', async () => {
  await mf.dispose();
  process.exit(0);
});
process.on('SIGTERM', async () => {
  await mf.dispose();
  process.exit(0);
});
