<script lang="ts">
  import type { ErrorCode, ServiceStatus } from '../types/contract';
  import { mockApi } from '../lib/api/mock';

  let {
    mode = 'demo',
    status = null,
    isWaking = false,
    onReset,
    onTriggerMockError,
  }: {
    mode: 'demo' | 'mock' | 'live';
    status: ServiceStatus | null;
    isWaking: boolean;
    onReset: () => void;
    onTriggerMockError?: (code: ErrorCode | null) => void;
  } = $props();

  const allErrors: ErrorCode[] = [
    'validation',
    'unsupported',
    'pii_detected',
    'rate_limited',
    'queue_full',
    'quota_gemini',
    'quota_tabpfn',
    'capacity_exhausted',
    'kill_switch',
    'turn_limit',
    'backend_waking',
    'upstream_unavailable',
    'internal',
  ];

  let selectedMockError: string = $state('');

  function handleMockErrorChange(e: Event): void {
    const target = e.target as HTMLSelectElement;
    const val = target.value as ErrorCode | '';
    if (onTriggerMockError) {
      onTriggerMockError(val || null);
    }
  }
</script>

<header class="app-header">
  <div class="header-inner container">
    <div class="brand">
      <button type="button" class="brand-btn" onclick={onReset} aria-label="Reset to home">
        <svg class="brand-icon" width="24" height="24" viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <rect width="32" height="32" rx="8" fill="var(--accent)"/>
          <path d="M8 10h16M8 16h16M8 22h10" stroke="#ffffff" stroke-width="2.5" stroke-linecap="round"/>
        </svg>
        <span class="brand-text">tabpfn-chat-lite</span>
      </button>

      <span
        class="badge"
        class:badge-accent={mode === 'mock'}
        class:badge-success={mode === 'live'}
        class:badge-warning={mode === 'demo'}
      >
        {mode === 'mock' ? 'MOCK MODE' : mode === 'live' ? 'LIVE' : 'DEMO'}
      </span>

      {#if isWaking}
        <span class="waking-pill" title="Free backend instance is cold starting">
          <span class="pulse-amber"></span> Backend waking up...
        </span>
      {/if}
    </div>

    <div class="header-controls">
      {#if status?.capacity?.daily_runs_remaining !== undefined}
        <div class="capacity-pill tabular-nums" title="Remaining analysis capacity today">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"></path>
          </svg>
          <span>{status.capacity.daily_runs_remaining} runs left</span>
        </div>
      {/if}

      {#if mode === 'mock'}
        <div class="mock-selector">
          <label for="mock-error-select" class="sr-only">Simulate Error:</label>
          <select
            id="mock-error-select"
            bind:value={selectedMockError}
            onchange={handleMockErrorChange}
            class="mock-select"
            aria-label="Simulate error code"
          >
            <option value="">Error Simulation: None</option>
            {#each allErrors as code}
              <option value={code}>Test: {code}</option>
            {/each}
          </select>
        </div>
      {/if}

      <button type="button" class="btn btn-ghost btn-sm" onclick={onReset} title="Start clean session">
        New Session
      </button>
    </div>
  </div>
</header>

<style>
  .app-header {
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-subtle);
    position: sticky;
    top: 0;
    z-index: 50;
    backdrop-filter: blur(8px);
  }
  .header-inner {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding-top: var(--space-3);
    padding-bottom: var(--space-3);
  }
  .brand {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  .brand-btn {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0;
  }
  .brand-text {
    font-size: var(--font-base);
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
  }
  @media (max-width: 480px) {
    .header-inner {
      padding-top: var(--space-2);
      padding-bottom: var(--space-2);
      gap: var(--space-2);
    }
    .brand-text {
      font-size: var(--font-sm);
    }
    .waking-pill {
      display: none;
    }
  }
  .header-controls {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  .capacity-pill {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    font-size: var(--font-xs);
    color: var(--text-secondary);
    background: var(--bg-subtle);
    padding: 3px 8px;
    border-radius: var(--radius-full);
    border: 1px solid var(--border-subtle);
  }
  .waking-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    font-size: var(--font-xs);
    color: var(--warning);
    background: var(--warning-subtle);
    padding: 2px 8px;
    border-radius: var(--radius-full);
  }
  .pulse-amber {
    width: 6px;
    height: 6px;
    background: var(--warning);
    border-radius: 50%;
    animation: pulse 1s infinite alternate;
  }
  @keyframes pulse {
    from { opacity: 0.3; }
    to { opacity: 1; }
  }
  .mock-select {
    font-size: var(--font-xs);
    padding: 4px 6px;
    border-radius: var(--radius-sm);
    border: 1px solid var(--border-default);
    background: var(--bg-surface);
    color: var(--text-secondary);
  }
  .btn-sm {
    padding: 4px var(--space-3);
    font-size: var(--font-xs);
  }
  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    padding: 0;
    margin: -1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    border-width: 0;
  }
</style>
