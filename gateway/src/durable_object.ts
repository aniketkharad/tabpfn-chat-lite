import { DurableObject } from 'cloudflare:workers';
import type { Env, ErrorCode } from './types';

export class AdmissionDurableObject extends DurableObject {
  private sql: SqlStorage;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.sql = ctx.storage.sql;
    this.initSchema();
  }

  private initSchema(): void {
    const runInit = () => {
      this.sql.exec(`
        CREATE TABLE IF NOT EXISTS daily_runs (
          day TEXT NOT NULL,
          ip_hash TEXT NOT NULL,
          count INTEGER NOT NULL,
          PRIMARY KEY(day, ip_hash)
        )
      `);

      this.sql.exec(`
        CREATE TABLE IF NOT EXISTS global_runs (
          day TEXT PRIMARY KEY,
          count INTEGER NOT NULL
        )
      `);

      this.sql.exec(`
        CREATE TABLE IF NOT EXISTS kill_switch (
          id INTEGER PRIMARY KEY,
          tripped INTEGER NOT NULL,
          reason TEXT,
          updated_at TEXT NOT NULL
        )
      `);

      this.sql.exec(`
        CREATE TABLE IF NOT EXISTS session_logs (
          session_id TEXT NOT NULL,
          seq INTEGER NOT NULL,
          prev_hash TEXT NOT NULL,
          hash TEXT NOT NULL,
          event_type TEXT NOT NULL,
          timestamp TEXT NOT NULL,
          data TEXT NOT NULL,
          PRIMARY KEY(session_id, seq)
        )
      `);

      this.sql.exec(`
        CREATE TABLE IF NOT EXISTS usage_counters (
          day TEXT PRIMARY KEY,
          tabpfn_tokens INTEGER NOT NULL,
          gemini_calls INTEGER NOT NULL
        )
      `);
    };

    if (this.ctx && typeof this.ctx.blockConcurrencyWhile === 'function') {
      this.ctx.blockConcurrencyWhile(async () => {
        runInit();
      });
    } else {
      runInit();
    }
  }

  private getTodayUtc(): string {
    return new Date().toISOString().slice(0, 10);
  }

  private getResetsAtUtc(): string {
    const now = new Date();
    const nextMidnight = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1));
    return nextMidnight.toISOString();
  }

  public isKillSwitched(): { tripped: boolean; reason: string } {
    const cursor = this.sql.exec('SELECT tripped, reason FROM kill_switch WHERE id = 1');
    const rows = [...cursor];
    if (rows.length > 0 && Number(rows[0].tripped) === 1) {
      return { tripped: true, reason: String(rows[0].reason || 'Emergency maintenance activated.') };
    }
    return { tripped: false, reason: '' };
  }

  public tripKillSwitch(reason: string = 'Administrative pause'): void {
    const now = new Date().toISOString();
    this.sql.exec(
      'INSERT OR REPLACE INTO kill_switch (id, tripped, reason, updated_at) VALUES (1, 1, ?, ?)',
      reason,
      now
    );
  }

  public clearKillSwitch(): void {
    const now = new Date().toISOString();
    this.sql.exec(
      'INSERT OR REPLACE INTO kill_switch (id, tripped, reason, updated_at) VALUES (1, 0, "", ?)',
      now
    );
  }

  public checkAdmission(
    ipHash: string,
    perIpLimit: number,
    globalLimit: number
  ): { allowed: boolean; code?: ErrorCode; reason?: string } {
    // 1. Check Kill Switch
    const ks = this.isKillSwitched();
    if (ks.tripped) {
      return { allowed: false, code: 'kill_switch', reason: ks.reason };
    }

    const today = this.getTodayUtc();

    // 2. Check Global Limit
    const globalCursor = this.sql.exec('SELECT count FROM global_runs WHERE day = ?', today);
    const globalRows = [...globalCursor];
    const globalCount = globalRows.length > 0 ? Number(globalRows[0].count) : 0;
    if (globalCount >= globalLimit) {
      return {
        allowed: false,
        code: 'capacity_exhausted',
        reason: `Global daily run capacity (${globalLimit}) reached for today.`,
      };
    }

    // 3. Check Per-IP Limit
    const ipCursor = this.sql.exec(
      'SELECT count FROM daily_runs WHERE day = ? AND ip_hash = ?',
      today,
      ipHash
    );
    const ipRows = [...ipCursor];
    const ipCount = ipRows.length > 0 ? Number(ipRows[0].count) : 0;
    if (ipCount >= perIpLimit) {
      return {
        allowed: false,
        code: 'rate_limited',
        reason: `Daily per-visitor run limit (${perIpLimit}) reached for today.`,
      };
    }

    return { allowed: true };
  }

  public recordRun(ipHash: string): void {
    const today = this.getTodayUtc();

    this.sql.exec(
      `INSERT INTO global_runs (day, count) VALUES (?, 1)
       ON CONFLICT(day) DO UPDATE SET count = count + 1`,
      today
    );

    this.sql.exec(
      `INSERT INTO daily_runs (day, ip_hash, count) VALUES (?, ?, 1)
       ON CONFLICT(day, ip_hash) DO UPDATE SET count = count + 1`,
      today,
      ipHash
    );
  }

  public getCapacity(globalLimit: number): {
    state: 'ok' | 'busy' | 'exhausted' | 'killed';
    resets_at: string;
    daily_runs_remaining: number;
  } {
    const ks = this.isKillSwitched();
    const today = this.getTodayUtc();
    const resetsAt = this.getResetsAtUtc();

    const globalCursor = this.sql.exec('SELECT count FROM global_runs WHERE day = ?', today);
    const globalRows = [...globalCursor];
    const globalCount = globalRows.length > 0 ? Number(globalRows[0].count) : 0;
    const remaining = Math.max(0, globalLimit - globalCount);

    let state: 'ok' | 'busy' | 'exhausted' | 'killed' = 'ok';
    if (ks.tripped) {
      state = 'killed';
    } else if (remaining <= 0) {
      state = 'exhausted';
    }

    return {
      state,
      resets_at: resetsAt,
      daily_runs_remaining: remaining,
    };
  }

  public appendLogs(sessionId: string, events: any[]): number {
    let count = 0;
    for (const ev of events) {
      const seq = Number(ev.seq);
      const prevHash = String(ev.prev_hash || '');
      const hash = String(ev.hash || '');
      const eventType = String(ev.event_type || 'unknown');
      const timestamp = String(ev.timestamp || new Date().toISOString());
      const dataStr = typeof ev.data === 'string' ? ev.data : JSON.stringify(ev.data || {});

      this.sql.exec(
        `INSERT OR REPLACE INTO session_logs
         (session_id, seq, prev_hash, hash, event_type, timestamp, data)
         VALUES (?, ?, ?, ?, ?, ?, ?)`,
        sessionId,
        seq,
        prevHash,
        hash,
        eventType,
        timestamp,
        dataStr
      );
      count++;
    }
    return count;
  }

  public getLogs(sessionId: string): any[] {
    const cursor = this.sql.exec(
      `SELECT seq, prev_hash, hash, event_type, timestamp, data
       FROM session_logs
       WHERE session_id = ?
       ORDER BY seq ASC`,
      sessionId
    );
    const rows = [...cursor];
    return rows.map((r) => {
      let parsedData: any = {};
      try {
        parsedData = JSON.parse(String(r.data));
      } catch {
        parsedData = { raw: r.data };
      }
      return {
        seq: Number(r.seq),
        prev_hash: String(r.prev_hash),
        hash: String(r.hash),
        event_type: String(r.event_type),
        timestamp: String(r.timestamp),
        data: parsedData,
      };
    });
  }

  public wipeSession(sessionId: string): void {
    this.sql.exec('DELETE FROM session_logs WHERE session_id = ?', sessionId);
  }

  public updateCounters(
    tokens: number,
    calls: number
  ): { tabpfn_tokens_today: number; gemini_calls_today: number } {
    const today = this.getTodayUtc();
    this.sql.exec(
      `INSERT INTO usage_counters (day, tabpfn_tokens, gemini_calls)
       VALUES (?, ?, ?)
       ON CONFLICT(day) DO UPDATE SET
         tabpfn_tokens = tabpfn_tokens + ?,
         gemini_calls = gemini_calls + ?`,
      today,
      tokens,
      calls,
      tokens,
      calls
    );

    const cursor = this.sql.exec(
      'SELECT tabpfn_tokens, gemini_calls FROM usage_counters WHERE day = ?',
      today
    );
    const rows = [...cursor];
    return {
      tabpfn_tokens_today: rows.length > 0 ? Number(rows[0].tabpfn_tokens) : tokens,
      gemini_calls_today: rows.length > 0 ? Number(rows[0].gemini_calls) : calls,
    };
  }

  /**
   * HTTP fetch handler for requests dispatched to this Durable Object.
   */
  async fetch(request: Request): Promise<Response> {
    const url = new URL(request.url);
    const action = url.pathname.replace(/^\/+/, '');

    try {
      if (request.method === 'POST') {
        const body: any = await request.json().catch(() => ({}));

        if (action === 'check_admission') {
          const res = this.checkAdmission(
            body.ip_hash,
            Number(body.per_ip_limit || 10),
            Number(body.global_limit || 50)
          );
          return Response.json(res);
        }

        if (action === 'record_run') {
          this.recordRun(body.ip_hash);
          return Response.json({ recorded: true });
        }

        if (action === 'trip_kill_switch') {
          this.tripKillSwitch(body.reason || 'Admin pause');
          return Response.json({ status: 'tripped', reason: body.reason });
        }

        if (action === 'clear_kill_switch') {
          this.clearKillSwitch();
          return Response.json({ status: 'cleared' });
        }

        if (action === 'append_logs') {
          const count = this.appendLogs(body.session_id, body.events || []);
          return Response.json({ accepted: true, count });
        }

        if (action === 'wipe_session') {
          this.wipeSession(body.session_id);
          return Response.json({ wiped: true });
        }

        if (action === 'update_counters') {
          const usage = this.updateCounters(Number(body.tabpfn_tokens || 0), Number(body.gemini_calls || 0));
          return Response.json({ accepted: true, current_usage: usage });
        }
      }

      if (request.method === 'GET') {
        if (action === 'capacity') {
          const globalLimit = Number(url.searchParams.get('global_limit') || 50);
          const capacity = this.getCapacity(globalLimit);
          return Response.json(capacity);
        }

        if (action === 'logs') {
          const sessionId = url.searchParams.get('session_id') || '';
          const logs = this.getLogs(sessionId);
          return Response.json({ session_id: sessionId, events: logs });
        }

        if (action === 'kill_switch') {
          return Response.json(this.isKillSwitched());
        }
      }

      return new Response('Not found in Durable Object', { status: 404 });
    } catch (err: any) {
      return Response.json({ error: String(err?.message || err) }, { status: 500 });
    }
  }
}
