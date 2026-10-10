<script lang="ts">
  import type { PipelineStage } from '../types/contract';

  let {
    stage = null,
    queuePosition = null,
    queueEta = null,
    message = null,
  }: {
    stage?: PipelineStage | null;
    queuePosition?: number | null;
    queueEta?: number | null;
    message?: string | null;
  } = $props();

  const stages: { key: PipelineStage; label: string }[] = [
    { key: 'planning', label: '1. Plan' },
    { key: 'estimating', label: '2. Cost' },
    { key: 'fitting', label: '3. Fit' },
    { key: 'narrating', label: '4. Narrate' },
  ];

  function isStageComplete(current: PipelineStage | null, target: PipelineStage): boolean {
    if (!current) return false;
    const order: PipelineStage[] = ['planning', 'estimating', 'fitting', 'narrating'];
    return order.indexOf(current) > order.indexOf(target);
  }

  function isStageActive(current: PipelineStage | null, target: PipelineStage): boolean {
    return current === target;
  }
</script>

<div class="status-bar-container" role="status" aria-live="polite">
  {#if queuePosition !== null && queuePosition > 0}
    <div class="queue-notice">
      <div class="spinner-sm" aria-hidden="true"></div>
      <span>Queued at position <strong>#{queuePosition}</strong></span>
      {#if queueEta !== null}
        <span class="eta tabular-nums">(ETA ~{queueEta.toFixed(1)}s)</span>
      {/if}
    </div>
  {/if}

  {#if stage}
    <div class="stage-stepper">
      {#each stages as st}
        {@const active = isStageActive(stage, st.key)}
        {@const completed = isStageComplete(stage, st.key)}
        <div class="stage-step" class:active class:completed>
          <span class="step-indicator">
            {#if completed}
              ✓
            {:else if active}
              <span class="pulse-dot"></span>
            {:else}
              •
            {/if}
          </span>
          <span class="step-label">{st.label}</span>
        </div>
      {/each}
    </div>

    {#if message}
      <p class="stage-message">{message}</p>
    {/if}
  {/if}
</div>

<style>
  .status-bar-container {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-3);
    margin: var(--space-3) 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }
  .queue-notice {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-xs);
    color: var(--warning);
    font-weight: 500;
  }
  .eta {
    color: var(--text-muted);
  }
  .stage-stepper {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--space-2);
  }
  .stage-step {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 8px;
    border-radius: var(--radius-sm);
    background: var(--bg-subtle);
    font-size: var(--font-xs);
    color: var(--text-muted);
    transition: all var(--duration-fast) var(--ease-standard);
  }
  .stage-step.active {
    background: var(--accent-subtle);
    color: var(--accent);
    font-weight: 600;
  }
  .stage-step.completed {
    background: var(--bg-subtle);
    color: var(--success);
    font-weight: 500;
  }
  .step-indicator {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 14px;
    height: 14px;
  }
  .pulse-dot {
    width: 8px;
    height: 8px;
    background: var(--accent);
    border-radius: 50%;
    animation: pulse 1s infinite alternate;
  }
  @keyframes pulse {
    from { transform: scale(0.8); opacity: 0.6; }
    to { transform: scale(1.2); opacity: 1; }
  }
  .spinner-sm {
    width: 12px;
    height: 12px;
    border: 2px solid var(--warning);
    border-top-color: transparent;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
  .stage-message {
    font-size: var(--font-xs);
    color: var(--text-secondary);
    font-style: italic;
    margin-top: 2px;
  }
</style>
