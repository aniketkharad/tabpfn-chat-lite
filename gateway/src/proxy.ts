import { signGatewayRequest } from './crypto';
import type { Env, ErrorEnvelope } from './types';

const HOP_BY_HOP_HEADERS = new Set([
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-authorization',
  'te',
  'trailers',
  'transfer-encoding',
  'upgrade',
  'cookie', // Invariant: never forward browser cookies
  'host',
]);

const MAX_UPLOAD_BYTES = 10 * 1024 * 1024; // 10 MB for file upload
const MAX_JSON_BYTES = 512 * 1024;         // 512 KB for JSON payloads
const BACKEND_TIMEOUT_MS = 65000;          // 65 seconds to tolerate waking container

export function makeErrorResponse(
  code: ErrorEnvelope['error']['code'],
  message: string,
  requestId: string,
  statusCode = 400,
  retryAfterS?: number
): Response {
  const body: ErrorEnvelope = {
    error: {
      code,
      message,
      request_id: requestId,
      ...(retryAfterS !== undefined ? { retry_after_s: retryAfterS } : {}),
    },
  };
  const headers = new Headers({
    'Content-Type': 'application/json',
  });
  if (retryAfterS !== undefined) {
    headers.set('Retry-After', String(retryAfterS));
  }
  return new Response(JSON.stringify(body), {
    status: statusCode,
    headers,
  });
}

export async function proxyToBackend(
  request: Request,
  env: Env,
  sessionId?: string,
  requestIdOverride?: string
): Promise<Response> {
  const requestId = requestIdOverride || request.headers.get('X-Gateway-Request-ID') || `req_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;
  const url = new URL(request.url);
  const backendBase = env.BACKEND_URL.replace(/\/+$/, '');
  const targetUrl = new URL(url.pathname + url.search, backendBase);

  // 1. Enforce body-size caps before forwarding
  const isUpload = url.pathname.includes('/upload');
  const maxBytes = isUpload ? MAX_UPLOAD_BYTES : MAX_JSON_BYTES;

  const contentLengthStr = request.headers.get('content-length');
  if (contentLengthStr) {
    const contentLength = parseInt(contentLengthStr, 10);
    if (!isNaN(contentLength) && contentLength > maxBytes) {
      return makeErrorResponse(
        'validation',
        `Request body size ${contentLength} bytes exceeds limit of ${maxBytes} bytes.`,
        requestId,
        400
      );
    }
  }

  let bodyBytes = new Uint8Array(0);
  if (request.method !== 'GET' && request.method !== 'HEAD') {
    const rawBuffer = await request.arrayBuffer();
    if (rawBuffer.byteLength > maxBytes) {
      return makeErrorResponse(
        'validation',
        `Request payload of ${rawBuffer.byteLength} bytes exceeds allowable limit of ${maxBytes} bytes.`,
        requestId,
        400
      );
    }
    bodyBytes = new Uint8Array(rawBuffer);
  }

  // 2. Sign request per contract/auth.md
  const targetPath = url.pathname + url.search;
  const hmacHeaders = await signGatewayRequest(
    env.GATEWAY_HMAC_SECRET_CURRENT,
    request.method,
    targetPath,
    bodyBytes,
    requestId
  );

  // 3. Construct headers to forward (stripping hop-by-hop and browser cookies)
  const forwardHeaders = new Headers();
  for (const [key, val] of request.headers.entries()) {
    const lowerKey = key.toLowerCase();
    if (!HOP_BY_HOP_HEADERS.has(lowerKey)) {
      forwardHeaders.set(key, val);
    }
  }

  // Inject HMAC headers
  forwardHeaders.set('X-Gateway-Timestamp', hmacHeaders['X-Gateway-Timestamp']);
  forwardHeaders.set('X-Gateway-Request-ID', hmacHeaders['X-Gateway-Request-ID']);
  forwardHeaders.set('X-Gateway-Signature', hmacHeaders['X-Gateway-Signature']);

  // Forward session ID if available
  if (sessionId) {
    forwardHeaders.set('X-Session-ID', sessionId);
  }

  // 4. Dispatch with AbortController timeout to handle cold start
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), BACKEND_TIMEOUT_MS);

  try {
    const backendResponse = await fetch(targetUrl.toString(), {
      method: request.method,
      headers: forwardHeaders,
      body: bodyBytes.length > 0 ? bodyBytes : undefined,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    // Filter response headers
    const responseHeaders = new Headers();
    for (const [key, val] of backendResponse.headers.entries()) {
      const lower = key.toLowerCase();
      if (!HOP_BY_HOP_HEADERS.has(lower)) {
        responseHeaders.set(key, val);
      }
    }

    // Stream response body without buffering
    return new Response(backendResponse.body, {
      status: backendResponse.status,
      statusText: backendResponse.statusText,
      headers: responseHeaders,
    });
  } catch (err: any) {
    clearTimeout(timeoutId);

    // If aborted due to timeout or network connection failed (backend sleeping/waking)
    return makeErrorResponse(
      'backend_waking',
      'The free backend compute container was sleeping and is currently spinning up (cold start ~50s on Render).',
      requestId,
      503,
      15
    );
  }
}
