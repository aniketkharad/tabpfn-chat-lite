export const SKEW_TOLERANCE_SECONDS = 30;
export const EMPTY_BODY_SHA256 = 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';

function bufferToHex(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let hex = '';
  for (let i = 0; i < bytes.length; i++) {
    hex += bytes[i].toString(16).padStart(2, '0');
  }
  return hex;
}

function hexToBytes(hex: string): Uint8Array {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < bytes.length; i++) {
    bytes[i] = parseInt(hex.substring(i * 2, i * 2 + 2), 16);
  }
  return bytes;
}

/**
 * Constant-time byte comparison to prevent timing attacks.
 */
export function timingSafeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) {
    return false;
  }
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return result === 0;
}

/**
 * Compute SHA-256 hex digest of given bytes or string.
 */
export async function computeSha256(data: Uint8Array | string): Promise<string> {
  const bytes = typeof data === 'string' ? new TextEncoder().encode(data) : data;
  if (bytes.length === 0) {
    return EMPTY_BODY_SHA256;
  }
  const hashBuffer = await crypto.subtle.digest('SHA-256', bytes);
  return bufferToHex(hashBuffer);
}

/**
 * Construct canonical payload string per contract/auth.md Section 3.
 */
export function buildCanonicalString(
  timestamp: number,
  method: string,
  path: string,
  bodySha256: string,
  requestId: string
): string {
  return `${timestamp}\n${method.toUpperCase()}\n${path}\n${bodySha256}\n${requestId}`;
}

/**
 * Compute HMAC-SHA256 signature over string data using Web Crypto API.
 */
export async function computeHmacSha256(secret: string, data: string): Promise<string> {
  const enc = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    enc.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  const signatureBuffer = await crypto.subtle.sign('HMAC', key, enc.encode(data));
  return bufferToHex(signatureBuffer);
}

/**
 * Helper to generate required gateway headers for a proxied request.
 */
export async function signGatewayRequest(
  secret: string,
  method: string,
  path: string,
  bodyBytes: Uint8Array = new Uint8Array(0),
  requestId?: string,
  timestamp?: number
): Promise<{
  'X-Gateway-Timestamp': string;
  'X-Gateway-Request-ID': string;
  'X-Gateway-Signature': string;
}> {
  const ts = timestamp !== undefined ? timestamp : Math.floor(Date.now() / 1000);
  const reqId = requestId || `req_${crypto.randomUUID().replace(/-/g, '').slice(0, 12)}`;
  const bodyHash = await computeSha256(bodyBytes);
  const canonical = buildCanonicalString(ts, method, path, bodyHash, reqId);
  const sig = await computeHmacSha256(secret, canonical);

  return {
    'X-Gateway-Timestamp': String(ts),
    'X-Gateway-Request-ID': reqId,
    'X-Gateway-Signature': sig,
  };
}

/**
 * Verify incoming HMAC gateway request per contract/auth.md.
 */
export async function verifyGatewayRequest(
  headers: Headers | Record<string, string>,
  method: string,
  path: string,
  bodyBytes: Uint8Array,
  currentSecret: string,
  previousSecret?: string,
  nowOverride?: number
): Promise<boolean> {
  const getHeader = (name: string): string | null => {
    if (headers instanceof Headers) {
      return headers.get(name);
    }
    return headers[name] || headers[name.toLowerCase()] || null;
  };

  const tsStr = getHeader('X-Gateway-Timestamp');
  const reqId = getHeader('X-Gateway-Request-ID');
  const sig = getHeader('X-Gateway-Signature');

  if (!tsStr || !reqId || !sig) {
    return false;
  }

  const ts = parseInt(tsStr, 10);
  if (isNaN(ts)) {
    return false;
  }

  // 1. Skew tolerance check (30 seconds)
  const now = nowOverride !== undefined ? nowOverride : Math.floor(Date.now() / 1000);
  if (Math.abs(now - ts) > SKEW_TOLERANCE_SECONDS) {
    return false;
  }

  // 2. Body SHA-256
  const bodyHash = await computeSha256(bodyBytes);

  // 3. Canonical string
  const canonical = buildCanonicalString(ts, method, path, bodyHash, reqId);

  // 4. Constant-time comparison with current secret
  const expectedCurrent = await computeHmacSha256(currentSecret, canonical);
  if (timingSafeEqual(sig, expectedCurrent)) {
    return true;
  }

  // 5. Dual-secret evaluation with previous secret
  if (previousSecret) {
    const expectedPrev = await computeHmacSha256(previousSecret, canonical);
    if (timingSafeEqual(sig, expectedPrev)) {
      return true;
    }
  }

  return false;
}

/**
 * Sign session ID and expiration timestamp for HttpOnly cookie.
 */
export async function signSessionToken(
  sessionId: string,
  expiresAt: number,
  signingSecret: string
): Promise<string> {
  const data = `${sessionId}.${expiresAt}`;
  const sig = await computeHmacSha256(signingSecret, data);
  return `${sessionId}.${expiresAt}.${sig}`;
}

/**
 * Verify session cookie token, returning sessionId or null if invalid/expired.
 */
export async function verifySessionToken(
  token: string,
  signingSecret: string,
  nowMs?: number
): Promise<string | null> {
  const parts = token.split('.');
  if (parts.length !== 3) {
    return null;
  }
  const [sessionId, expiresAtStr, sig] = parts;
  const expiresAt = parseInt(expiresAtStr, 10);
  if (isNaN(expiresAt)) {
    return null;
  }

  const now = nowMs !== undefined ? nowMs : Date.now();
  if (now > expiresAt) {
    return null; // Expired
  }

  const expectedSig = await computeHmacSha256(signingSecret, `${sessionId}.${expiresAt}`);
  if (!timingSafeEqual(sig, expectedSig)) {
    return null; // Tampered
  }

  return sessionId;
}

/**
 * Compute salted SHA-256 hash of client IP.
 */
export async function hashClientIp(clientIp: string, salt: string): Promise<string> {
  return computeSha256(`${clientIp}:${salt}`);
}
