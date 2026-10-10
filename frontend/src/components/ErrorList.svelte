<script lang="ts">
  import type { ErrorCode } from '../types/contract';
  import { getErrorMessage } from '../lib/api/messages';

  export interface DisplayError {
    id: string;
    code: ErrorCode;
    message?: string;
    request_id?: string;
    retry_after_s?: number;
  }

  let {
    errors = [],
    onDismiss,
    onRetry,
  }: {
    errors: DisplayError[];
    onDismiss?: (id: string) => void;
    onRetry?: (error: DisplayError) => void;
  } = $props();
</script>

{#if errors.length > 0}
  <div class="error-container" role="alert" aria-live="assertive">
    {#each errors as err (err.id)}
      {@const meta = getErrorMessage(err.code)}
      <div class="error-card">
        <div class="error-icon" aria-hidden="true">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="10"></circle>
            <line x1="12" y1="8" x2="12" y2="12"></line>
            <line x1="12" y1="16" x2="12.01" y2="16"></line>
          </svg>
        </div>

        <div class="error-body">
          <div class="error-header">
            <h4 class="error-title">{meta.title}</h4>
            <span class="badge badge-danger">{err.code}</span>
          </div>

          <p class="error-msg">{err.message || meta.message}</p>
          <p class="error-action"><strong>Recommended Action:</strong> {meta.action}</p>

          {#if err.retry_after_s}
            <span class="retry-hint tabular-nums">Suggested retry delay: {err.retry_after_s}s</span>
          {/if}

          {#if err.request_id}
            <span class="trace-id font-mono">Trace ID: {err.request_id}</span>
          {/if}

          <div class="error-actions">
            {#if meta.retryable && onRetry}
              <button
                type="button"
                class="btn btn-secondary btn-sm"
                onclick={() => onRetry(err)}
              >
                Retry Request
              </button>
            {/if}

            {#if onDismiss}
              <button
                type="button"
                class="btn btn-ghost btn-sm"
                onclick={() => onDismiss(err.id)}
              >
                Dismiss
              </button>
            {/if}
          </div>
        </div>
      </div>
    {/each}
  </div>
{/if}

<style>
  .error-container {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    margin: var(--space-4) 0;
  }
  .error-card {
    display: flex;
    gap: var(--space-3);
    background: var(--danger-subtle);
    border: 1px solid var(--danger-border);
    border-radius: var(--radius-md);
    padding: var(--space-4);
  }
  .error-icon {
    color: var(--danger);
    flex-shrink: 0;
    margin-top: 2px;
  }
  .error-body {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    width: 100%;
  }
  .error-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .error-title {
    font-size: var(--font-sm);
    font-weight: 700;
    color: var(--danger);
  }
  .error-msg {
    font-size: var(--font-xs);
    color: var(--text-primary);
    line-height: var(--leading-normal);
  }
  .error-action {
    font-size: var(--font-xs);
    color: var(--text-secondary);
    line-height: var(--leading-normal);
  }
  .retry-hint, .trace-id {
    font-size: 11px;
    color: var(--text-muted);
  }
  .font-mono {
    font-family: var(--font-mono);
  }
  .error-actions {
    display: flex;
    gap: var(--space-2);
    margin-top: var(--space-1);
  }
  .btn-sm {
    padding: 3px var(--space-3);
    font-size: var(--font-xs);
  }
</style>
