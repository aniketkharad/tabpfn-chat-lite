/**
 * Core contract types matching contract/schemas/ and openapi.yaml
 */

export type ColumnType = 'string' | 'int' | 'float' | 'boolean' | 'datetime';

export type CellValue = string | number | boolean | null;

export interface TableData {
  cols: string[];
  types: ColumnType[];
  rows: CellValue[][];
}

export interface ColumnCard {
  name: string;
  type: string;
  null_count: number;
  sample_values: CellValue[];
}

export interface DatasetCard {
  row_count: number;
  col_count: number;
  columns: ColumnCard[];
  preview_rows: CellValue[][];
}

export type Capability =
  | 'classification'
  | 'regression'
  | 'forecasting'
  | 'anomaly_detection'
  | 'data_generation'
  | 'interpretability';

export interface PlanEstimate {
  gemini_calls: number;
  tabpfn_tokens: number;
  pct_of_daily_budget: number;
}

export interface Plan {
  plan_id: string;
  capability: Capability;
  target: string | null;
  features: string[];
  params: Record<string, unknown>;
  estimate: PlanEstimate;
}

export interface MetricUncertainty {
  lower: number;
  upper: number;
  confidence_level: number;
}

export interface MetricBlock {
  type: 'metric';
  name: string;
  value: number | string;
  baseline_value?: number | null;
  delta?: number | null;
  unit?: string;
  description?: string;
  uncertainty?: MetricUncertainty;
}

export interface TableBlock {
  type: 'table';
  title: string;
  description?: string;
  table: TableData;
}

export type ChartKind = 'bar' | 'line' | 'scatter' | 'reliability' | 'interval' | 'importance';

export interface ChartBlock {
  type: 'chart';
  kind: ChartKind;
  title: string;
  description?: string;
  data: Record<string, any>;
}

export interface TextBlock {
  type: 'text';
  title?: string;
  content: string;
}

export interface DownloadBlock {
  type: 'download';
  filename: string;
  format: 'csv' | 'json';
  content: string;
  description?: string;
  size_bytes?: number;
}

export type ResultBlock = MetricBlock | TableBlock | ChartBlock | TextBlock | DownloadBlock;

export type RunStatus = 'queued' | 'running' | 'completed' | 'failed';

export interface RunDetails {
  run_id: string;
  plan_id: string;
  status: RunStatus;
  blocks: ResultBlock[];
  summary?: string;
  error?: {
    code: ErrorCode;
    message: string;
    request_id?: string;
    retry_after_s?: number;
  };
}

export type PipelineStage = 'planning' | 'estimating' | 'fitting' | 'narrating';

export type SSEEvent =
  | {
      id: string;
      event: 'queued';
      data: {
        position: number;
        eta_s: number;
      };
    }
  | {
      id: string;
      event: 'status';
      data: {
        stage: PipelineStage;
        message?: string;
      };
    }
  | {
      id: string;
      event: 'block';
      data: {
        block: ResultBlock;
      };
    }
  | {
      id: string;
      event: 'done';
      data: {
        summary: string;
        run_id?: string;
        completed_at?: string;
      };
    }
  | {
      id: string;
      event: 'error';
      data: {
        error: {
          code: ErrorCode;
          message: string;
          retry_after_s?: number;
          request_id: string;
        };
      };
    };

export type ErrorCode =
  | 'validation'
  | 'unsupported'
  | 'pii_detected'
  | 'rate_limited'
  | 'queue_full'
  | 'quota_gemini'
  | 'quota_tabpfn'
  | 'capacity_exhausted'
  | 'kill_switch'
  | 'turn_limit'
  | 'backend_waking'
  | 'upstream_unavailable'
  | 'internal';

export interface ErrorDetails {
  code: ErrorCode;
  message: string;
  retry_after_s?: number;
  request_id: string;
}

export interface ErrorEnvelope {
  error: ErrorDetails;
}

export interface ErrorMessageMeta {
  code: ErrorCode;
  title: string;
  message: string;
  action: string;
  retryable: boolean;
}

export interface ServiceStatus {
  state: 'ok' | 'busy' | 'exhausted' | 'killed';
  resets_at: string;
  limits: {
    max_rows: number;
    max_cols: number;
    max_cells: number;
    max_file_size_bytes: number;
    max_turns: number;
  };
  capacity?: {
    active_runs?: number;
    daily_runs_remaining?: number;
  };
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  plan?: Plan | null;
  timestamp: number;
}
