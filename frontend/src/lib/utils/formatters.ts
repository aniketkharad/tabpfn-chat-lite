/**
 * Formatting utilities for tabular figures and metrics.
 */

export function formatNumber(val: number | string | null | undefined, digits = 3): string {
  if (val === null || val === undefined) return '—';
  if (typeof val === 'string') {
    const num = parseFloat(val);
    if (isNaN(num)) return val;
    return num.toLocaleString('en-US', { maximumFractionDigits: digits });
  }
  return val.toLocaleString('en-US', { maximumFractionDigits: digits });
}

export function formatDelta(delta: number | null | undefined, unit?: string): string {
  if (delta === null || delta === undefined) return '';
  const sign = delta > 0 ? '+' : '';
  const formatted = delta.toLocaleString('en-US', { maximumFractionDigits: 3 });
  return `${sign}${formatted}${unit ? ` ${unit}` : ''}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function formatPercent(val: number): string {
  return `${(val * 100).toFixed(1)}%`;
}
