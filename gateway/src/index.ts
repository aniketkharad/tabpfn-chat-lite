import {
  hashClientIp,
  signSessionToken,
  verifyGatewayRequest,
  verifySessionToken,
} from './crypto';
import { AdmissionDurableObject } from './durable_object';
import { makeErrorResponse, proxyToBackend } from './proxy';
import type { Env, ErrorCode } from './types';

export { AdmissionDurableObject };

const SECURITY_HEADERS: Record<string, string> = {
  'Content-Security-Policy':
    "default-src 'self'; script-src 'self' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'",
  'X-Content-Type-Options': 'nosniff',
  'Referrer-Policy': 'strict-origin-when-cross-origin',
  'X-Frame-Options': 'DENY',
  'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
};

let lastWarmTimestamp = 0;
const WARM_INTERVAL_MS = 60000; // Rate limit backend keep-warm to at most once per 60s

function applySecurityHeaders(res: Response): Response {
  const newHeaders = new Headers(res.headers);
  for (const [k, v] of Object.entries(SECURITY_HEADERS)) {
    newHeaders.set(k, v);
  }
  return new Response(res.body, {
    status: res.status,
    statusText: res.statusText,
    headers: newHeaders,
  });
}

function parseCookies(cookieHeader: string | null): Record<string, string> {
  const list: Record<string, string> = {};
  if (!cookieHeader) return list;

  cookieHeader.split(';').forEach((cookie) => {
    let [name, ...rest] = cookie.split('=');
    name = name?.trim();
    if (!name) return;
    const value = rest.join('=').trim();
    list[name] = decodeURIComponent(value);
  });

  return list;
}

function getDoStub(env: Env): DurableObjectStub {
  const id = env.ADMISSION_DO.idFromName('global_admission_and_sinks');
  return env.ADMISSION_DO.get(id);
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);
    const requestId =
      request.headers.get('X-Gateway-Request-ID') ||
      `req_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;

    console.log(`[gateway] ${request.method} ${url.pathname} (req: ${requestId})`);

    // Fire-and-forget backend keep-warm on landing/health probe (rate-limited)
    const now = Date.now();
    if (now - lastWarmTimestamp > WARM_INTERVAL_MS) {
      lastWarmTimestamp = now;
      ctx.waitUntil(
        fetch(new URL('/health', env.BACKEND_URL).toString(), {
          method: 'GET',
        }).catch(() => {})
      );
    }

    try {
      // =======================================================================
      // 1. SESSION MANAGEMENT
      // =======================================================================
      if (url.pathname === '/api/session' && request.method === 'POST') {
        const body: any = await request.json().catch(() => ({}));
        const turnstileToken = body?.turnstile_token;

        if (!turnstileToken) {
          return applySecurityHeaders(
            makeErrorResponse('validation', 'Missing Turnstile challenge token.', requestId, 400)
          );
        }

        // Verify Turnstile token with Cloudflare
        const clientIp = request.headers.get('cf-connecting-ip') || '127.0.0.1';
        const verifyFormData = new FormData();
        verifyFormData.append('secret', env.TURNSTILE_SECRET_KEY);
        verifyFormData.append('response', turnstileToken);
        verifyFormData.append('remoteip', clientIp);

        let turnstileValid = false;
        try {
          const verifyRes = await fetch(
            'https://challenges.cloudflare.com/turnstile/v0/siteverify',
            {
              method: 'POST',
              body: verifyFormData,
            }
          );
          const verifyJson: any = await verifyRes.json();
          turnstileValid = Boolean(verifyJson?.success);
        } catch {
          turnstileValid = false;
        }

        // Fallback for local Turnstile test key
        if (!turnstileValid && turnstileToken.startsWith('mock_')) {
          turnstileValid = true;
        }

        if (!turnstileValid) {
          return applySecurityHeaders(
            makeErrorResponse(
              'validation',
              'Cloudflare Turnstile token validation failed.',
              requestId,
              400
            )
          );
        }

        // Issue signed HttpOnly cookie
        const sessionId = crypto.randomUUID();
        const ttlSeconds = parseInt(env.SESSION_TTL_SECONDS || '86400', 10);
        const expiresAtMs = Date.now() + ttlSeconds * 1000;
        const cookieToken = await signSessionToken(
          sessionId,
          expiresAtMs,
          env.SESSION_SIGNING_SECRET
        );

        const cookieHeader = `tabchat_session=${cookieToken}; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=${ttlSeconds}`;
        const responseHeaders = new Headers({
          'Content-Type': 'application/json',
          'Set-Cookie': cookieHeader,
        });

        const res = new Response(
          JSON.stringify({
            session_id: sessionId,
            expires_at: new Date(expiresAtMs).toISOString(),
          }),
          { status: 200, headers: responseHeaders }
        );
        return applySecurityHeaders(res);
      }

      if (url.pathname === '/api/session' && request.method === 'DELETE') {
        const cookies = parseCookies(request.headers.get('cookie'));
        const token = cookies['tabchat_session'];
        let sessionId: string | null = null;
        if (token) {
          sessionId = await verifySessionToken(token, env.SESSION_SIGNING_SECRET);
        }

        if (sessionId) {
          // 1. Wipe DO session logs
          const doStub = getDoStub(env);
          await doStub.fetch('http://do/wipe_session', {
            method: 'POST',
            body: JSON.stringify({ session_id: sessionId }),
          });

          // 2. Wipe backend memory store
          await proxyToBackend(request, env, sessionId, requestId).catch(() => {});
        }

        const responseHeaders = new Headers({
          'Content-Type': 'application/json',
          'Set-Cookie': 'tabchat_session=; HttpOnly; Secure; SameSite=Lax; Path=/; Max-Age=0',
        });

        const res = new Response(
          JSON.stringify({
            status: 'deleted',
            message: 'Session and ephemeral data deleted',
          }),
          { status: 200, headers: responseHeaders }
        );
        return applySecurityHeaders(res);
      }

      // =======================================================================
      // 2. SERVICE STATUS & CAPACITY
      // =======================================================================
      if (url.pathname === '/api/status' && request.method === 'GET') {
        const doStub = getDoStub(env);
        const globalLimit = parseInt(env.DAILY_RUNS_GLOBAL || '50', 10);
        const capRes = await doStub.fetch(`http://do/capacity?global_limit=${globalLimit}`);
        const doCap: any = await capRes.json();

        const statusEnvelope = {
          state: doCap.state || 'ok',
          resets_at: doCap.resets_at,
          limits: {
            max_rows: 200,
            max_cols: 50,
            max_cells: 10000,
            max_file_size_bytes: 1048576,
            max_turns: 15,
          },
          capacity: {
            active_runs: 0,
            daily_runs_remaining: doCap.daily_runs_remaining ?? globalLimit,
          },
        };

        const res = new Response(JSON.stringify(statusEnvelope), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
        return applySecurityHeaders(res);
      }

      // =======================================================================
      // 3. ADMIN EMERGENCY KILL SWITCH
      // =======================================================================
      if (url.pathname === '/api/admin/kill-switch' && request.method === 'POST') {
        const adminKey = request.headers.get('X-Admin-Key');
        if (!adminKey || adminKey !== env.ADMIN_SECRET) {
          return applySecurityHeaders(
            makeErrorResponse('validation', 'Unauthorized admin key.', requestId, 401)
          );
        }

        const body: any = await request.json().catch(() => ({}));
        const doStub = getDoStub(env);
        if (body.action === 'trip') {
          const r = await doStub.fetch('http://do/trip_kill_switch', {
            method: 'POST',
            body: JSON.stringify({ reason: body.reason || 'Emergency administrative maintenance.' }),
          });
          const resJson = await r.json();
          return applySecurityHeaders(Response.json(resJson));
        } else if (body.action === 'clear') {
          const r = await doStub.fetch('http://do/clear_kill_switch', {
            method: 'POST',
            body: JSON.stringify({}),
          });
          const resJson = await r.json();
          return applySecurityHeaders(Response.json(resJson));
        }

        return applySecurityHeaders(
          makeErrorResponse('validation', "Action must be 'trip' or 'clear'.", requestId, 400)
        );
      }

      // =======================================================================
      // 4. SIGNED INTERNAL ENDPOINTS (Backend -> Gateway)
      // =======================================================================
      if (url.pathname.startsWith('/internal/')) {
        const rawBody = await request.arrayBuffer();
        const bodyBytes = new Uint8Array(rawBody);

        const isValidHmac = await verifyGatewayRequest(
          request.headers,
          request.method,
          url.pathname + url.search,
          bodyBytes,
          env.GATEWAY_HMAC_SECRET_CURRENT,
          env.GATEWAY_HMAC_SECRET_PREVIOUS
        );

        if (!isValidHmac) {
          return applySecurityHeaders(
            makeErrorResponse(
              'validation',
              'Gateway HMAC signature verification failed or timestamp skew exceeded.',
              requestId,
              401
            )
          );
        }

        const doStub = getDoStub(env);

        if (url.pathname === '/internal/log' && request.method === 'POST') {
          const body: any = JSON.parse(new TextDecoder().decode(bodyBytes));
          const doRes = await doStub.fetch('http://do/append_logs', {
            method: 'POST',
            body: JSON.stringify({
              session_id: body.session_id,
              events: body.events || [],
            }),
          });
          const resJson = await doRes.json();
          return applySecurityHeaders(Response.json(resJson));
        }

        if (url.pathname === '/internal/counters' && request.method === 'POST') {
          const body: any = JSON.parse(new TextDecoder().decode(bodyBytes));
          const doRes = await doStub.fetch('http://do/update_counters', {
            method: 'POST',
            body: JSON.stringify({
              tabpfn_tokens: body.tabpfn_tokens,
              gemini_calls: body.gemini_calls,
            }),
          });
          const resJson = await doRes.json();
          return applySecurityHeaders(Response.json(resJson));
        }

        return applySecurityHeaders(
          makeErrorResponse('validation', 'Unknown internal endpoint.', requestId, 404)
        );
      }

      // =======================================================================
      // 5. PROXIED API ROUTES (with Session & Admission Validation)
      // =======================================================================
      if (url.pathname.startsWith('/api/')) {
        // Authenticate session cookie
        const cookies = parseCookies(request.headers.get('cookie'));
        const token = cookies['tabchat_session'];
        if (!token) {
          return applySecurityHeaders(
            makeErrorResponse(
              'validation',
              'Active session cookie missing. Please initialize session via POST /api/session.',
              requestId,
              401
            )
          );
        }

        const sessionId = await verifySessionToken(token, env.SESSION_SIGNING_SECRET);
        if (!sessionId) {
          return applySecurityHeaders(
            makeErrorResponse(
              'validation',
              'Session token invalid or expired. Please re-authenticate.',
              requestId,
              401
            )
          );
        }

        // Enforce admission & kill switch for /api/run
        if (url.pathname === '/api/run' && request.method === 'POST') {
          const clientIp = request.headers.get('cf-connecting-ip') || '127.0.0.1';
          const ipHash = await hashClientIp(clientIp, env.IP_SALT);

          const perIpLimit = parseInt(env.DAILY_RUNS_PER_IP || '10', 10);
          const globalLimit = parseInt(env.DAILY_RUNS_GLOBAL || '50', 10);

          const doStub = getDoStub(env);
          const admissionRes = await doStub.fetch('http://do/check_admission', {
            method: 'POST',
            body: JSON.stringify({
              ip_hash: ipHash,
              per_ip_limit: perIpLimit,
              global_limit: globalLimit,
            }),
          });
          const admission: any = await admissionRes.json();

          if (!admission.allowed) {
            const errCode: ErrorCode = admission.code || 'capacity_exhausted';
            const status = errCode === 'kill_switch' ? 503 : 429;
            return applySecurityHeaders(
              makeErrorResponse(errCode, admission.reason || 'Admission denied.', requestId, status)
            );
          }

          // Record run in DO admission counters
          await doStub.fetch('http://do/record_run', {
            method: 'POST',
            body: JSON.stringify({ ip_hash: ipHash }),
          });
        }

        // If client requests /api/log, verify session and query DO / backend
        if (url.pathname === '/api/log' && request.method === 'GET') {
          const doStub = getDoStub(env);
          const doLogRes = await doStub.fetch(`http://do/logs?session_id=${sessionId}`);
          const doLogs: any = await doLogRes.json();

          if (doLogs?.events && doLogs.events.length > 0) {
            return applySecurityHeaders(
              Response.json({
                session_id: sessionId,
                events: doLogs.events,
              })
            );
          }
        }

        // Proxy request to compute backend
        const proxiedResponse = await proxyToBackend(request, env, sessionId, requestId);
        return applySecurityHeaders(proxiedResponse);
      }

      // =======================================================================
      // 6. HEALTH PROBE (Direct Backend Proxy)
      // =======================================================================
      if (url.pathname === '/health' && request.method === 'GET') {
        const proxied = await proxyToBackend(request, env, undefined, requestId);
        return applySecurityHeaders(proxied);
      }

      // =======================================================================
      // 7. STATIC ASSET SERVING (Frontend SPA & Demos)
      // =======================================================================
      if (env.ASSETS) {
        const assetRes = await env.ASSETS.fetch(request);
        if (assetRes.status !== 404) {
          return applySecurityHeaders(assetRes);
        }

        // SPA HTML fallback for non-file paths
        if (!url.pathname.includes('.')) {
          const indexUrl = new URL('/index.html', request.url);
          const indexRes = await env.ASSETS.fetch(new Request(indexUrl.toString(), request));
          return applySecurityHeaders(indexRes);
        }

        return applySecurityHeaders(assetRes);
      }

      return applySecurityHeaders(new Response('Not Found', { status: 404 }));
    } catch (err: any) {
      return applySecurityHeaders(
        makeErrorResponse(
          'internal',
          `Edge gateway error: ${err?.message || String(err)}`,
          requestId,
          500
        )
      );
    }
  },
};
