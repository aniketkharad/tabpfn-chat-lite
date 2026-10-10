import type { ErrorCode, ErrorMessageMeta } from '../../types/contract';

export const ERROR_CATALOG: Record<ErrorCode, ErrorMessageMeta> = {
  validation: {
    code: 'validation',
    title: 'Invalid Request',
    message: 'The uploaded data or request parameters failed schema validation. Please check column limits, data types, and formatting.',
    action: 'Ensure your file is a valid CSV with at most 200 rows, 50 columns, and cell values under 64 characters.',
    retryable: false,
  },
  unsupported: {
    code: 'unsupported',
    title: 'Unsupported Capability',
    message: 'The requested analysis capability or split configuration is not supported by TabPFN-3.5 in this environment.',
    action: 'Select one of the supported capabilities: classification, regression, forecasting, anomaly detection, data generation, or interpretability.',
    retryable: false,
  },
  pii_detected: {
    code: 'pii_detected',
    title: 'Personal Data Detected',
    message: 'Our automated safety screener detected potential personal information (such as email addresses, phone numbers, or credit card numbers) in your table.',
    action: 'Please remove or mask columns containing private identifiers before uploading. No personal data was saved.',
    retryable: false,
  },
  rate_limited: {
    code: 'rate_limited',
    title: 'Too Many Requests',
    message: 'You have exceeded the allowed rate of 12 requests per minute.',
    action: 'Please wait a few moments before sending another message or starting a run.',
    retryable: true,
  },
  queue_full: {
    code: 'queue_full',
    title: 'Analysis Queue Is Full',
    message: 'All concurrent analysis slots are currently busy processing runs for other visitors.',
    action: 'Please wait a moment and try again, or switch to Demo Mode for instant local evaluation.',
    retryable: true,
  },
  quota_gemini: {
    code: 'quota_gemini',
    title: 'Gemini Quota Exhausted',
    message: 'The daily public Gemini planning quota (20 requests/day on free tier) has been reached for today.',
    action: 'The system will automatically switch to Demo Mode with pre-computed models, or reset at 00:00:00 UTC.',
    retryable: false,
  },
  quota_tabpfn: {
    code: 'quota_tabpfn',
    title: 'TabPFN Token Budget Exhausted',
    message: 'The daily TabPFN token budget (5,000,000 tokens) has been exhausted.',
    action: 'Analysis resets daily at 00:00:00 UTC. In the meantime, you can explore results in zero-quota Demo Mode.',
    retryable: false,
  },
  capacity_exhausted: {
    code: 'capacity_exhausted',
    title: 'Daily Service Capacity Reached',
    message: 'The maximum number of live runs allocated for the prototype today has been completed.',
    action: 'Explore sample workflows in instant Demo Mode, or check back after 00:00:00 UTC.',
    retryable: false,
  },
  kill_switch: {
    code: 'kill_switch',
    title: 'Service Temporarily Paused',
    message: 'Live analysis has been temporarily placed on hold by the administrator for scheduled maintenance.',
    action: 'Demo Mode remains fully functional with zero backend calls.',
    retryable: false,
  },
  turn_limit: {
    code: 'turn_limit',
    title: 'Session Turn Limit Reached',
    message: 'You have reached the maximum limit of 15 conversational turns for this session.',
    action: 'Please confirm your final plan to run the analysis, or start a fresh session with a new dataset.',
    retryable: false,
  },
  backend_waking: {
    code: 'backend_waking',
    title: 'Backend Service Waking Up',
    message: 'The free backend compute container was sleeping and is currently spinning up (cold start ~50s on Render).',
    action: 'Please hang tight! Your request will automatically complete once the container is ready.',
    retryable: true,
  },
  upstream_unavailable: {
    code: 'upstream_unavailable',
    title: 'Upstream Service Unavailable',
    message: 'A transient network error occurred while communicating with Google Gemini or the Prior Labs TabPFN API.',
    action: 'Please retry in a few seconds. If the problem persists, check upstream status.',
    retryable: true,
  },
  internal: {
    code: 'internal',
    title: 'Internal Server Error',
    message: 'An unexpected error occurred while processing your request. Our redacting logger has recorded a diagnostic trace.',
    action: 'Please refresh the page or start a new session. If the issue recurs, please report it.',
    retryable: true,
  },
};

export function getErrorMessage(code: ErrorCode): ErrorMessageMeta {
  return ERROR_CATALOG[code] ?? {
    code: 'internal',
    title: 'Unknown Error',
    message: 'An unexpected error occurred.',
    action: 'Please refresh or retry.',
    retryable: true,
  };
}
