import { describe, expect, it } from 'vitest';
import { makeErrorResponse, proxyToBackend } from '../src/proxy';
import type { Env } from '../src/types';

describe('Proxy Module Suite', () => {
  const dummyEnv: Env = {
    ADMISSION_DO: {} as any,
    BACKEND_URL: 'http://127.0.0.1:59999', // Non-existent port for timeout/waking simulation
    DAILY_RUNS_PER_IP: '10',
    DAILY_RUNS_GLOBAL: '50',
    SESSION_TTL_SECONDS: '86400',
    TURNSTILE_SITE_KEY: 'test_key',
    TURNSTILE_SECRET_KEY: 'test_secret',
    SESSION_SIGNING_SECRET: 'test_session_secret',
    IP_SALT: 'test_salt',
    GATEWAY_HMAC_SECRET_CURRENT: 'test_hmac_current',
    ADMIN_SECRET: 'admin_key',
  };

  it('makeErrorResponse creates conforming error envelope', async () => {
    const res = makeErrorResponse('backend_waking', 'Backend is starting', 'req_test', 503, 15);
    expect(res.status).toBe(503);
    expect(res.headers.get('Retry-After')).toBe('15');

    const json: any = await res.json();
    expect(json.error.code).toBe('backend_waking');
    expect(json.error.message).toBe('Backend is starting');
    expect(json.error.request_id).toBe('req_test');
    expect(json.error.retry_after_s).toBe(15);
  });

  it('rejects oversized payload before proxying', async () => {
    const largeBody = new Uint8Array(600 * 1024); // 600 KB exceeds 512 KB JSON cap
    const req = new Request('http://localhost/api/chat', {
      method: 'POST',
      body: largeBody,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    const res = await proxyToBackend(req, dummyEnv, 'session_1');
    expect(res.status).toBe(400);

    const json: any = await res.json();
    expect(json.error.code).toBe('validation');
    expect(json.error.message).toContain('exceeds');
  });

  it('returns backend_waking envelope when backend connection fails or times out', async () => {
    const req = new Request('http://localhost/api/status', {
      method: 'GET',
    });

    const res = await proxyToBackend(req, dummyEnv, 'session_1', 'req_waking_1');
    expect(res.status).toBe(503);
    expect(res.headers.get('Retry-After')).toBe('15');

    const json: any = await res.json();
    expect(json.error.code).toBe('backend_waking');
    expect(json.error.retry_after_s).toBe(15);
    expect(json.error.request_id).toBe('req_waking_1');
  });
});
