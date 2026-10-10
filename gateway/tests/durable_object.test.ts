import { describe, expect, it, beforeEach } from 'vitest';
// @ts-ignore
import { Database } from 'bun:sqlite';
import { AdmissionDurableObject } from '../src/durable_object';
import type { Env } from '../src/types';

// Mock Cloudflare SqlStorage backed by real in-memory SQLite database
class MockSqlStorage {
  private db: Database;

  constructor() {
    this.db = new Database(':memory:');
  }

  exec(query: string, ...params: any[]): Iterable<any> {
    const trimmed = query.trim();
    // Support multiple statements in schema init
    if (trimmed.includes(';')) {
      const statements = trimmed
        .split(';')
        .map((s) => s.trim())
        .filter(Boolean);
      for (const stmt of statements) {
        if (stmt.toLowerCase().startsWith('select')) {
          return this.db.query(stmt).all(...params) as any[];
        } else {
          this.db.query(stmt).run(...params);
        }
      }
      return [];
    }

    if (trimmed.toLowerCase().startsWith('select')) {
      return this.db.query(query).all(...params) as any[];
    } else {
      this.db.query(query).run(...params);
      return [];
    }
  }
}

describe('Admission & Sinks Durable Object Suite', () => {
  let mockSql: MockSqlStorage;
  let mockState: any;
  let mockEnv: Env;
  let durableObject: AdmissionDurableObject;

  beforeEach(() => {
    mockSql = new MockSqlStorage();
    mockState = {
      storage: {
        sql: mockSql,
      },
      blockConcurrencyWhile: async (fn: any) => await fn(),
    };
    mockEnv = {
      ADMISSION_DO: {} as any,
      BACKEND_URL: 'http://127.0.0.1:8000',
      DAILY_RUNS_PER_IP: '3',
      DAILY_RUNS_GLOBAL: '5',
      SESSION_TTL_SECONDS: '86400',
      TURNSTILE_SITE_KEY: 'test_site_key',
      TURNSTILE_SECRET_KEY: 'test_secret_key',
      SESSION_SIGNING_SECRET: 'test_session_secret',
      IP_SALT: 'test_salt',
      GATEWAY_HMAC_SECRET_CURRENT: 'test_current',
      ADMIN_SECRET: 'test_admin_key',
    };
    durableObject = new AdmissionDurableObject(mockState, mockEnv);
  });

  describe('Admission Checks & Rate Limits', () => {
    it('allows initial run when limits not exceeded', () => {
      const res = durableObject.checkAdmission('ip_hash_1', 3, 5);
      expect(res.allowed).toBe(true);
    });

    it('enforces per-IP daily limit', () => {
      const ip = 'ip_hash_victim';
      durableObject.recordRun(ip);
      durableObject.recordRun(ip);
      expect(durableObject.checkAdmission(ip, 2, 10).allowed).toBe(false);
      const res = durableObject.checkAdmission(ip, 2, 10);
      expect(res.code).toBe('rate_limited');

      // Different IP is still allowed
      expect(durableObject.checkAdmission('ip_hash_other', 2, 10).allowed).toBe(true);
    });

    it('enforces global daily limit', () => {
      durableObject.recordRun('ip_1');
      durableObject.recordRun('ip_2');
      durableObject.recordRun('ip_3');

      const res = durableObject.checkAdmission('ip_4', 10, 3);
      expect(res.allowed).toBe(false);
      expect(res.code).toBe('capacity_exhausted');
    });
  });

  describe('Kill Switch Trip and Clear', () => {
    it('blocks all admission when kill switch is tripped', () => {
      expect(durableObject.isKillSwitched().tripped).toBe(false);

      durableObject.tripKillSwitch('Emergency security audit');
      expect(durableObject.isKillSwitched().tripped).toBe(true);

      const admission = durableObject.checkAdmission('any_ip', 10, 50);
      expect(admission.allowed).toBe(false);
      expect(admission.code).toBe('kill_switch');
      expect(admission.reason).toContain('Emergency security audit');

      const capacity = durableObject.getCapacity(50);
      expect(capacity.state).toBe('killed');

      // Clear kill switch
      durableObject.clearKillSwitch();
      expect(durableObject.isKillSwitched().tripped).toBe(false);
      expect(durableObject.checkAdmission('any_ip', 10, 50).allowed).toBe(true);
      expect(durableObject.getCapacity(50).state).toBe('ok');
    });
  });

  describe('Session Event Logs & Hash Chain Sink', () => {
    it('appends and retrieves ordered session events', () => {
      const sessionId = 'session_log_test_1';
      const events = [
        { seq: 0, prev_hash: '00000000', hash: 'hash_0', event_type: 'init', data: { a: 1 } },
        { seq: 1, prev_hash: 'hash_0', hash: 'hash_1', event_type: 'run', data: { b: 2 } },
      ];

      const count = durableObject.appendLogs(sessionId, events);
      expect(count).toBe(2);

      const retrieved = durableObject.getLogs(sessionId);
      expect(retrieved).toHaveLength(2);
      expect(retrieved[0].seq).toBe(0);
      expect(retrieved[0].data).toEqual({ a: 1 });
      expect(retrieved[1].seq).toBe(1);
      expect(retrieved[1].data).toEqual({ b: 2 });
    });

    it('wipes session logs on delete request', () => {
      const sessionId = 'session_to_wipe';
      durableObject.appendLogs(sessionId, [{ seq: 0, prev_hash: '0', hash: 'h0', event_type: 'init', data: {} }]);
      expect(durableObject.getLogs(sessionId)).toHaveLength(1);

      durableObject.wipeSession(sessionId);
      expect(durableObject.getLogs(sessionId)).toHaveLength(0);
    });
  });

  describe('Counter Sinks', () => {
    it('aggregates daily token and call counters', () => {
      const u1 = durableObject.updateCounters(10000, 2);
      expect(u1.tabpfn_tokens_today).toBe(10000);
      expect(u1.gemini_calls_today).toBe(2);

      const u2 = durableObject.updateCounters(25000, 3);
      expect(u2.tabpfn_tokens_today).toBe(35000);
      expect(u2.gemini_calls_today).toBe(5);
    });
  });
});
