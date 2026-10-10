import type {
  Capability,
  DatasetCard,
  ErrorCode,
  ErrorEnvelope,
  Plan,
  ServiceStatus,
  SSEEvent,
  TableData,
} from '../../types/contract';
import { getErrorMessage } from './messages';
import { mockApi } from './mock';

export class ApiError extends Error {
  public code: ErrorCode;
  public action: string;
  public retryable: boolean;
  public retry_after_s?: number;
  public request_id?: string;

  constructor(code: ErrorCode, message: string, action: string, retryable: boolean, retry_after_s?: number, request_id?: string) {
    super(message);
    this.name = 'ApiError';
    this.code = code;
    this.action = action;
    this.retryable = retryable;
    this.retry_after_s = retry_after_s;
    this.request_id = request_id;
  }
}

export class ApiClient {
  private isWakingUp = false;
  private onWakingStateChange?: (waking: boolean) => void;

  public setWakingCallback(cb: (waking: boolean) => void): void {
    this.onWakingStateChange = cb;
  }

  /**
   * Fire-and-forget warm-up probe ping on app launch.
   * Wakes free backend containers (e.g. Render cold start ~50s) while user inspects files.
   */
  public async warmUpBackend(): Promise<void> {
    if (mockApi.isMockActive) return;

    try {
      const res = await fetch('/health', { method: 'GET', cache: 'no-cache' });
      if (!res.ok) {
        this.setWaking(true);
      } else {
        this.setWaking(false);
      }
    } catch {
      // Quietly register waking state on network failure
      this.setWaking(true);
    }
  }

  private setWaking(waking: boolean): void {
    this.isWakingUp = waking;
    if (this.onWakingStateChange) {
      this.onWakingStateChange(waking);
    }
  }

  public get waking(): boolean {
    return this.isWakingUp;
  }

  public async getStatus(): Promise<ServiceStatus> {
    if (mockApi.isMockActive) {
      return mockApi.getStatus();
    }

    try {
      const res = await fetch('/api/status', { method: 'GET', cache: 'no-cache' });
      if (!res.ok) {
        throw await this.handleErrorResponse(res);
      }
      return await res.json();
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw this.wrapUnknownError(err);
    }
  }

  public async getSession(): Promise<{
    session_id: string;
    dataset_card: DatasetCard | null;
    history: { role: 'user' | 'assistant'; content: string; timestamp?: string }[];
    job_spec: any | null;
    results: any | null;
  } | null> {
    if (mockApi.isMockActive) return null;
    try {
      const res = await fetch('/api/session', { method: 'GET' });
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }

  public async createSession(turnstileToken: string): Promise<{ session_id: string; expires_at: string }> {
    if (mockApi.isMockActive) {
      return mockApi.createSession(turnstileToken);
    }

    try {
      const res = await fetch('/api/session', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ turnstile_token: turnstileToken }),
      });
      if (!res.ok) throw await this.handleErrorResponse(res);
      return await res.json();
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw this.wrapUnknownError(err);
    }
  }

  public async deleteSession(): Promise<{ status: string; message: string }> {
    if (mockApi.isMockActive) {
      return mockApi.deleteSession();
    }

    try {
      const res = await fetch('/api/session', { method: 'DELETE' });
      if (!res.ok) throw await this.handleErrorResponse(res);
      return await res.json();
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw this.wrapUnknownError(err);
    }
  }

  public async upload(data: TableData | File | string, filename = 'dataset.csv'): Promise<{
    dataset_id: string;
    dataset_card: DatasetCard;
    table: TableData;
  }> {
    if (mockApi.isMockActive && typeof data === 'object' && 'cols' in data) {
      return mockApi.upload(data as TableData);
    }

    try {
      const formData = new FormData();
      if (data instanceof File) {
        formData.append('file', data, data.name);
      } else if (typeof data === 'string') {
        const blob = new Blob([data], { type: 'text/csv' });
        formData.append('file', blob, filename);
      } else {
        // Convert TableData to CSV string
        const table = data as TableData;
        const header = table.cols.join(',');
        const rows = table.rows.map((row) =>
          row
            .map((val) =>
              val === null || val === undefined
                ? ''
                : String(val).includes(',')
                  ? `"${String(val).replace(/"/g, '""')}"`
                  : String(val)
            )
            .join(',')
        );
        const csvContent = [header, ...rows].join('\n');
        const blob = new Blob([csvContent], { type: 'text/csv' });
        formData.append('file', blob, filename);
      }

      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      if (!res.ok) throw await this.handleErrorResponse(res);
      return await res.json();
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw this.wrapUnknownError(err);
    }
  }

  public async downloadSessionLog(sessionId?: string): Promise<void> {
    if (mockApi.isMockActive) {
      const blob = new Blob([JSON.stringify({ session_id: 'mock_session', events: [] }, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tabpfn_session_log_${sessionId || 'mock'}.json`;
      a.click();
      URL.revokeObjectURL(url);
      return;
    }

    try {
      const res = await fetch('/api/log?format=json');
      if (!res.ok) throw await this.handleErrorResponse(res);
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tabpfn_session_log_${data.session_id || sessionId || 'session'}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw this.wrapUnknownError(err);
    }
  }

  public async chatTurn(
    message: string,
    history: { role: 'user' | 'assistant'; content: string }[],
    currentTable?: TableData
  ): Promise<{ type: 'clarification' | 'plan'; message: string; plan: Plan | null }> {
    if (mockApi.isMockActive) {
      return mockApi.chatTurn(message, history, currentTable);
    }

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message, history }),
      });
      if (!res.ok) throw await this.handleErrorResponse(res);
      return await res.json();
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw this.wrapUnknownError(err);
    }
  }

  public async executeRun(planId: string): Promise<{
    run_id: string;
    status: string;
    estimate: { gemini_calls: number; tabpfn_tokens: number; pct_of_daily_budget: number };
  }> {
    if (mockApi.isMockActive) {
      return mockApi.executeRun(planId);
    }

    try {
      const res = await fetch('/api/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plan_id: planId }),
      });
      if (!res.ok) throw await this.handleErrorResponse(res);
      return await res.json();
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw this.wrapUnknownError(err);
    }
  }

  public async *streamEvents(
    runId: string,
    capability: Capability = 'classification',
    lastEventId?: string
  ): AsyncGenerator<SSEEvent, void, unknown> {
    if (mockApi.isMockActive) {
      yield* mockApi.streamEvents(capability);
      return;
    }

    const headers: Record<string, string> = { Accept: 'text/event-stream' };
    if (lastEventId) {
      headers['Last-Event-ID'] = lastEventId;
    }

    const response = await fetch(`/api/runs/${runId}/events`, {
      headers,
    });

    if (!response.ok) {
      throw await this.handleErrorResponse(response);
    }

    if (!response.body) {
      throw new ApiError('internal', 'No response stream available', 'Retry analysis', true);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n\n');
      buffer = lines.pop() ?? '';

      for (const block of lines) {
        if (!block.trim()) continue;
        const eventLines = block.split('\n');
        let eventId = '';
        let eventType = '';
        let eventDataRaw = '';

        for (const line of eventLines) {
          if (line.startsWith('id:')) eventId = line.slice(3).trim();
          else if (line.startsWith('event:')) eventType = line.slice(6).trim();
          else if (line.startsWith('data:')) eventDataRaw = line.slice(5).trim();
        }

        if (eventDataRaw) {
          try {
            const data = JSON.parse(eventDataRaw);
            yield { id: eventId, event: eventType as any, data };
          } catch {
            // Ignore malformed event frame
          }
        }
      }
    }
  }

  private async handleErrorResponse(res: Response): Promise<ApiError> {
    try {
      const data: ErrorEnvelope = await res.json();
      if (data?.error?.code) {
        const meta = getErrorMessage(data.error.code);
        return new ApiError(
          data.error.code,
          data.error.message || meta.message,
          meta.action,
          meta.retryable,
          data.error.retry_after_s,
          data.error.request_id
        );
      }
    } catch {
      // Non-JSON error
    }

    if (res.status === 503) {
      const meta = getErrorMessage('backend_waking');
      return new ApiError('backend_waking', meta.message, meta.action, true);
    }

    const meta = getErrorMessage('internal');
    return new ApiError('internal', `HTTP ${res.status}: ${res.statusText}`, meta.action, true);
  }

  private wrapUnknownError(err: unknown): ApiError {
    const meta = getErrorMessage('internal');
    const msg = err instanceof Error ? err.message : 'Unknown communication error';
    return new ApiError('internal', msg, meta.action, true);
  }
}

export const api = new ApiClient();
