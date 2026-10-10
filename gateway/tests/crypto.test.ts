import { describe, expect, it } from 'vitest';
import {
  buildCanonicalString,
  computeHmacSha256,
  computeSha256,
  EMPTY_BODY_SHA256,
  hashClientIp,
  signGatewayRequest,
  signSessionToken,
  timingSafeEqual,
  verifyGatewayRequest,
  verifySessionToken,
} from '../src/crypto';

describe('Gateway Crypto & Authentication Suite', () => {
  const SECRET_CURRENT = 'current_secret_key_1234567890_test';
  const SECRET_PREVIOUS = 'previous_secret_key_0987654321_test';
  const SESSION_SECRET = 'session_secret_signing_key_32_bytes_len';

  describe('Canonical String & Body Digest', () => {
    it('computes empty body SHA-256 matching standard', async () => {
      const hash = await computeSha256(new Uint8Array(0));
      expect(hash).toBe(EMPTY_BODY_SHA256);
      expect(hash).toBe('e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855');
    });

    it('formats canonical string exactly per contract/auth.md', () => {
      const canonical = buildCanonicalString(
        1775779200,
        'POST',
        '/api/upload',
        EMPTY_BODY_SHA256,
        'req_test_123'
      );
      expect(canonical).toBe(
        `1775779200\nPOST\n/api/upload\n${EMPTY_BODY_SHA256}\nreq_test_123`
      );
    });

    it('timingSafeEqual detects equality and inequality correctly', () => {
      expect(timingSafeEqual('abcd', 'abcd')).toBe(true);
      expect(timingSafeEqual('abcd', 'abce')).toBe(false);
      expect(timingSafeEqual('abcd', 'abc')).toBe(false);
    });
  });

  describe('HMAC Signing and Verification with Dual Secret Rotation', () => {
    it('signs and verifies request with current secret within skew tolerance', async () => {
      const now = 1775779200;
      const body = new TextEncoder().encode('{"message":"hello"}');
      const headers = await signGatewayRequest(
        SECRET_CURRENT,
        'POST',
        '/api/chat',
        body,
        'req_001',
        now
      );

      expect(headers['X-Gateway-Timestamp']).toBe('1775779200');
      expect(headers['X-Gateway-Request-ID']).toBe('req_001');
      expect(headers['X-Gateway-Signature']).toHaveLength(64);

      const isValid = await verifyGatewayRequest(
        headers,
        'POST',
        '/api/chat',
        body,
        SECRET_CURRENT,
        SECRET_PREVIOUS,
        now
      );
      expect(isValid).toBe(true);
    });

    it('accepts signatures generated with previous secret (zero-downtime rotation)', async () => {
      const now = 1775779200;
      const body = new Uint8Array(0);
      const headers = await signGatewayRequest(
        SECRET_PREVIOUS,
        'GET',
        '/api/status',
        body,
        'req_002',
        now
      );

      const isValid = await verifyGatewayRequest(
        headers,
        'GET',
        '/api/status',
        body,
        SECRET_CURRENT,
        SECRET_PREVIOUS,
        now
      );
      expect(isValid).toBe(true);
    });

    it('rejects signatures if secret does not match current or previous', async () => {
      const now = 1775779200;
      const headers = await signGatewayRequest(
        'wrong_secret_key',
        'GET',
        '/api/status',
        new Uint8Array(0),
        'req_003',
        now
      );

      const isValid = await verifyGatewayRequest(
        headers,
        'GET',
        '/api/status',
        new Uint8Array(0),
        SECRET_CURRENT,
        SECRET_PREVIOUS,
        now
      );
      expect(isValid).toBe(false);
    });

    it('rejects tampered request body', async () => {
      const now = 1775779200;
      const originalBody = new TextEncoder().encode('{"plan_id":"plan_1"}');
      const headers = await signGatewayRequest(
        SECRET_CURRENT,
        'POST',
        '/api/run',
        originalBody,
        'req_004',
        now
      );

      const tamperedBody = new TextEncoder().encode('{"plan_id":"plan_2"}');
      const isValid = await verifyGatewayRequest(
        headers,
        'POST',
        '/api/run',
        tamperedBody,
        SECRET_CURRENT,
        SECRET_PREVIOUS,
        now
      );
      expect(isValid).toBe(false);
    });

    it('rejects replay outside 30-second skew tolerance', async () => {
      const oldTime = 1775779200;
      const headers = await signGatewayRequest(
        SECRET_CURRENT,
        'GET',
        '/api/status',
        new Uint8Array(0),
        'req_005',
        oldTime
      );

      // 31 seconds later (exceeds skew tolerance)
      const nowExpired = oldTime + 31;
      const isExpired = await verifyGatewayRequest(
        headers,
        'GET',
        '/api/status',
        new Uint8Array(0),
        SECRET_CURRENT,
        SECRET_PREVIOUS,
        nowExpired
      );
      expect(isExpired).toBe(false);

      // Exactly 30 seconds (at boundary, passes)
      const nowBoundary = oldTime + 30;
      const isBoundary = await verifyGatewayRequest(
        headers,
        'GET',
        '/api/status',
        new Uint8Array(0),
        SECRET_CURRENT,
        SECRET_PREVIOUS,
        nowBoundary
      );
      expect(isBoundary).toBe(true);
    });
  });

  describe('Session Token Lifecycle', () => {
    it('signs and verifies session token correctly', async () => {
      const sessionId = 'session_test_abc_123';
      const expiresAt = Date.now() + 3600 * 1000;

      const token = await signSessionToken(sessionId, expiresAt, SESSION_SECRET);
      expect(token).toContain(sessionId);

      const verified = await verifySessionToken(token, SESSION_SECRET);
      expect(verified).toBe(sessionId);
    });

    it('rejects expired session token', async () => {
      const sessionId = 'session_test_expired';
      const expiresAt = 1000; // In the past

      const token = await signSessionToken(sessionId, expiresAt, SESSION_SECRET);
      const verified = await verifySessionToken(token, SESSION_SECRET, 2000);
      expect(verified).toBeNull();
    });

    it('rejects tampered session token', async () => {
      const sessionId = 'session_test_tampered';
      const expiresAt = Date.now() + 3600 * 1000;

      const token = await signSessionToken(sessionId, expiresAt, SESSION_SECRET);
      const tampered = token.replace(sessionId, 'session_malicious');

      const verified = await verifySessionToken(tampered, SESSION_SECRET);
      expect(verified).toBeNull();
    });
  });

  describe('Salted Client IP Hashing', () => {
    it('hashes IP deterministically with salt', async () => {
      const salt = 'salt_abc_123';
      const h1 = await hashClientIp('192.168.1.1', salt);
      const h2 = await hashClientIp('192.168.1.1', salt);
      const h3 = await hashClientIp('192.168.1.2', salt);

      expect(h1).toHaveLength(64);
      expect(h1).toBe(h2);
      expect(h1).not.toBe(h3);
    });
  });
});
