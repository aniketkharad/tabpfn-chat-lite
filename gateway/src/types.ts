export interface Env {
  // Bindings
  ASSETS?: Fetcher;
  ADMISSION_DO: DurableObjectNamespace;

  // Environment variables / secrets
  BACKEND_URL: string;
  DAILY_RUNS_PER_IP: string;
  DAILY_RUNS_GLOBAL: string;
  SESSION_TTL_SECONDS: string;
  TURNSTILE_SITE_KEY: string;
  TURNSTILE_SECRET_KEY: string;
  SESSION_SIGNING_SECRET: string;
  IP_SALT: string;
  GATEWAY_HMAC_SECRET_CURRENT: string;
  GATEWAY_HMAC_SECRET_PREVIOUS?: string;
  ADMIN_SECRET: string;
}

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

export interface ErrorEnvelope {
  error: {
    code: ErrorCode;
    message: string;
    request_id: string;
    retry_after_s?: number;
  };
}
