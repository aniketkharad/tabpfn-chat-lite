import type {
  Capability,
  DatasetCard,
  ErrorCode,
  Plan,
  RunDetails,
  ServiceStatus,
  SSEEvent,
  TableData,
} from '../../types/contract';
import {
  AIR_PLAN,
  CAPABILITY_RESULTS,
  CHURN_PLAN,
  ERROR_FIXTURES,
  HEALTH_FIXTURE,
  HOUSING_PLAN,
  SESSION_CREATE_FIXTURE,
  SESSION_DELETE_FIXTURE,
  STATUS_FIXTURE,
} from './fixtures';

export class MockApiEngine {
  private injectedError: ErrorCode | null = null;
  public isMockActive: boolean = false;

  constructor() {
    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      this.isMockActive = params.get('mock') === '1' || params.get('mock') === 'true';
      const errParam = params.get('error') as ErrorCode | null;
      if (errParam && ERROR_FIXTURES[errParam]) {
        this.injectedError = errParam;
      }
    }
  }

  public setInjectedError(error: ErrorCode | null): void {
    this.injectedError = error;
  }

  public getInjectedError(): ErrorCode | null {
    return this.injectedError;
  }

  public setMockActive(active: boolean): void {
    this.isMockActive = active;
  }

  private checkInjectedError(): void {
    if (this.injectedError && ERROR_FIXTURES[this.injectedError]) {
      const errEnvelope = ERROR_FIXTURES[this.injectedError];
      throw errEnvelope;
    }
  }

  public async getStatus(): Promise<ServiceStatus> {
    this.checkInjectedError();
    await this.delay(100);
    return STATUS_FIXTURE;
  }

  public async getHealth(): Promise<{ status: string; version: string; timestamp: string }> {
    this.checkInjectedError();
    await this.delay(50);
    return HEALTH_FIXTURE;
  }

  public async createSession(_turnstileToken = 'mock_token'): Promise<{ session_id: string; expires_at: string }> {
    this.checkInjectedError();
    await this.delay(150);
    return SESSION_CREATE_FIXTURE;
  }

  public async deleteSession(): Promise<{ status: string; message: string }> {
    this.checkInjectedError();
    await this.delay(100);
    return SESSION_DELETE_FIXTURE;
  }

  public async upload(table: TableData): Promise<{
    dataset_id: string;
    dataset_card: DatasetCard;
    table: TableData;
  }> {
    this.checkInjectedError();
    await this.delay(200);

    const columns = table.cols.map((col, idx) => ({
      name: col,
      type: table.types[idx] ?? 'string',
      null_count: table.rows.filter((r) => r[idx] === null).length,
      sample_values: table.rows.slice(0, 5).map((r) => r[idx] ?? null),
    }));

    return {
      dataset_id: `ds_mock_${Date.now()}`,
      dataset_card: {
        row_count: table.rows.length,
        col_count: table.cols.length,
        columns,
        preview_rows: table.rows.slice(0, 5),
      },
      table,
    };
  }

  public async chatTurn(
    message: string,
    _history: { role: 'user' | 'assistant'; content: string }[],
    currentTable?: TableData
  ): Promise<{ type: 'clarification' | 'plan'; message: string; plan: Plan | null }> {
    this.checkInjectedError();
    await this.delay(250);

    const lower = message.toLowerCase();

    // Check if prompt matches air/forecasting, housing/regression, or churn/classification
    if (lower.includes('forecast') || lower.includes('passenger') || lower.includes('time series')) {
      return {
        type: 'plan',
        message:
          "I've analyzed the passenger volume timeline and structured a 12-month forward time-series forecast using TabPFN.",
        plan: AIR_PLAN,
      };
    }

    if (lower.includes('house') || lower.includes('price') || lower.includes('regress')) {
      return {
        type: 'plan',
        message:
          "I've structured a regression plan to predict median house value from income, age, and room metrics.",
        plan: HOUSING_PLAN,
      };
    }

    if (lower.includes('anomaly') || lower.includes('outlier')) {
      return {
        type: 'plan',
        message: "I've structured an unsupervised TabPFN density plan to detect anomalous telemetry instances.",
        plan: {
          plan_id: 'plan_equipment_anomalies_v1',
          capability: 'anomaly_detection',
          target: null,
          features: currentTable?.cols.slice(0, 4) ?? ['vibration', 'temperature'],
          params: { contamination: 0.05 },
          estimate: { gemini_calls: 1, tabpfn_tokens: 10000, pct_of_daily_budget: 0.2 },
        },
      };
    }

    if (lower.includes('synthetic') || lower.includes('generate')) {
      return {
        type: 'plan',
        message: "I've structured a TabPFN synthetic tabular generation plan preserving marginals and correlations.",
        plan: {
          plan_id: 'plan_synthetic_patients_v1',
          capability: 'data_generation',
          target: null,
          features: currentTable?.cols ?? ['age', 'bmi', 'blood_pressure'],
          params: { n_samples: 100 },
          estimate: { gemini_calls: 1, tabpfn_tokens: 10000, pct_of_daily_budget: 0.2 },
        },
      };
    }

    if (lower.includes('interpret') || lower.includes('importance') || lower.includes('explain')) {
      return {
        type: 'plan',
        message: "I've structured a permutation feature importance and partial dependence interpretability plan.",
        plan: {
          plan_id: 'plan_medical_diagnostics_v1',
          capability: 'interpretability',
          target: currentTable?.cols[currentTable.cols.length - 1] ?? 'outcome',
          features: currentTable?.cols.slice(0, -1) ?? ['glucose', 'insulin', 'bmi'],
          params: { n_permutations: 50 },
          estimate: { gemini_calls: 2, tabpfn_tokens: 10000, pct_of_daily_budget: 0.2 },
        },
      };
    }

    // Default to churn classification plan
    return {
      type: 'plan',
      message:
        "I've analyzed your table and structured a plan to predict target outcomes using TabPFN prior-fitted inference.",
      plan: CHURN_PLAN,
    };
  }

  public async executeRun(planId: string): Promise<{
    run_id: string;
    status: string;
    estimate: { gemini_calls: number; tabpfn_tokens: number; pct_of_daily_budget: number };
  }> {
    this.checkInjectedError();
    await this.delay(150);
    return {
      run_id: `run_mock_${planId}`,
      status: 'queued',
      estimate: { gemini_calls: 2, tabpfn_tokens: 10000, pct_of_daily_budget: 0.2 },
    };
  }

  /**
   * Replays Server-Sent Events stream with simulated compressed timing.
   */
  public async *streamEvents(
    capability: Capability = 'classification',
    speedMultiplier = 1
  ): AsyncGenerator<SSEEvent, void, unknown> {
    const stepDelay = Math.max(80, 250 / speedMultiplier);

    // 1. Queued
    yield {
      id: '1',
      event: 'queued',
      data: { position: 1, eta_s: 1.0 },
    };
    await this.delay(stepDelay);

    // Check if error simulation requested for stream
    if (this.injectedError && ERROR_FIXTURES[this.injectedError]) {
      yield {
        id: '2',
        event: 'status',
        data: { stage: 'planning', message: 'Compiling validated JobSpec' },
      };
      await this.delay(stepDelay);

      const err = ERROR_FIXTURES[this.injectedError].error;
      yield {
        id: '3',
        event: 'error',
        data: { error: err },
      };
      return;
    }

    // 2. Planning
    yield {
      id: '2',
      event: 'status',
      data: { stage: 'planning', message: 'Compiling validated JobSpec' },
    };
    await this.delay(stepDelay);

    // 3. Estimating
    yield {
      id: '3',
      event: 'status',
      data: { stage: 'estimating', message: 'Estimating TabPFN token cost' },
    };
    await this.delay(stepDelay);

    // 4. Fitting
    yield {
      id: '4',
      event: 'status',
      data: { stage: 'fitting', message: 'Executing deterministic TabPFN REST prediction' },
    };
    await this.delay(stepDelay);

    // 5. Narrating
    yield {
      id: '5',
      event: 'status',
      data: { stage: 'narrating', message: 'Synthesizing grounded performance narration' },
    };
    await this.delay(stepDelay);

    // 6. Yield result blocks from capability fixture
    const details = CAPABILITY_RESULTS[capability] ?? CAPABILITY_RESULTS.classification;
    let eventId = 6;
    for (const block of details.blocks) {
      yield {
        id: String(eventId++),
        event: 'block',
        data: { block },
      };
      await this.delay(stepDelay * 0.6);
    }

    // 7. Done
    yield {
      id: String(eventId),
      event: 'done',
      data: {
        summary: details.summary ?? 'TabPFN analysis completed successfully.',
        run_id: details.run_id,
        completed_at: new Date().toISOString(),
      },
    };
  }

  public async getRun(capability: Capability = 'classification'): Promise<RunDetails> {
    this.checkInjectedError();
    await this.delay(100);
    return CAPABILITY_RESULTS[capability] ?? CAPABILITY_RESULTS.classification;
  }

  private delay(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }
}

export const mockApi = new MockApiEngine();
