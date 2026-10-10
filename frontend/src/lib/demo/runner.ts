import type {
  Capability,
  Plan,
  RunDetails,
  SSEEvent,
  TableData,
} from '../../types/contract';
import {
  AIR_PLAN,
  CAPABILITY_RESULTS,
  CHURN_PLAN,
  HOUSING_PLAN,
  SAMPLE_AIR_CSV,
  SAMPLE_CHURN_CSV,
  SAMPLE_HOUSING_CSV,
} from '../api/fixtures';
import { parseCSV } from '../csv/parser';

export interface DemoDatasetInfo {
  id: string;
  name: string;
  capability: Capability;
  badge: string;
  description: string;
  csv: string;
  plan: Plan;
}

export const DEMO_DATASETS: DemoDatasetInfo[] = [
  {
    id: 'churn',
    name: 'Customer Churn',
    capability: 'classification',
    badge: 'Classification',
    description: '140 accounts predicting churn based on monthly charges and tenure.',
    csv: SAMPLE_CHURN_CSV,
    plan: CHURN_PLAN,
  },
  {
    id: 'housing',
    name: 'California Housing',
    capability: 'regression',
    badge: 'Regression',
    description: '100 residential districts predicting median value with credible intervals.',
    csv: SAMPLE_HOUSING_CSV,
    plan: HOUSING_PLAN,
  },
  {
    id: 'air',
    name: 'Airline Passengers',
    capability: 'forecasting',
    badge: 'Forecasting',
    description: '144 monthly passenger observations with 12-month forward horizon forecast.',
    csv: SAMPLE_AIR_CSV,
    plan: AIR_PLAN,
  },
];

export class DemoRunner {
  /**
   * Fast compressed replay of capability results to meet <= 2.0s demo latency budget.
   */
  public async *runDemo(
    capability: Capability,
    onProgress?: (stage: string) => void
  ): AsyncGenerator<SSEEvent, void, unknown> {
    const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
    const details: RunDetails = CAPABILITY_RESULTS[capability] ?? CAPABILITY_RESULTS.classification;

    // 1. Queued (immediate)
    yield {
      id: '1',
      event: 'queued',
      data: { position: 1, eta_s: 0.5 },
    };
    await delay(120);

    // 2. Planning
    if (onProgress) onProgress('planning');
    yield {
      id: '2',
      event: 'status',
      data: { stage: 'planning', message: 'Compiling validated JobSpec' },
    };
    await delay(120);

    // 3. Estimating
    if (onProgress) onProgress('estimating');
    yield {
      id: '3',
      event: 'status',
      data: { stage: 'estimating', message: 'Estimating TabPFN token cost' },
    };
    await delay(120);

    // 4. Fitting
    if (onProgress) onProgress('fitting');
    yield {
      id: '4',
      event: 'status',
      data: { stage: 'fitting', message: 'Executing deterministic TabPFN REST prediction' },
    };
    await delay(220);

    // 5. Narrating
    if (onProgress) onProgress('narrating');
    yield {
      id: '5',
      event: 'status',
      data: { stage: 'narrating', message: 'Synthesizing grounded performance narration' },
    };
    await delay(120);

    // 6. Blocks
    let eventId = 6;
    for (const block of details.blocks) {
      yield {
        id: String(eventId++),
        event: 'block',
        data: { block },
      };
      await delay(80);
    }

    // 7. Done
    yield {
      id: String(eventId),
      event: 'done',
      data: {
        summary: details.summary ?? 'Demo analysis completed.',
        run_id: details.run_id,
        completed_at: new Date().toISOString(),
      },
    };
  }

  public getParsedDemoTable(datasetId: string): TableData {
    const ds = DEMO_DATASETS.find((d) => d.id === datasetId) ?? DEMO_DATASETS[0]!;
    const res = parseCSV(ds.csv);
    return res.table;
  }
}

export const demoRunner = new DemoRunner();
