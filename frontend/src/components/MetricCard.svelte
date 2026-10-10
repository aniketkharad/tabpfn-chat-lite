<script lang="ts">
  import type { MetricBlock } from '../types/contract';
  import { formatDelta, formatNumber } from '../lib/utils/formatters';

  let { metric }: { metric: MetricBlock } = $props();

  const isPositiveDelta = $derived(
    metric.delta !== null && metric.delta !== undefined && metric.delta > 0
  );
  const isNegativeDelta = $derived(
    metric.delta !== null && metric.delta !== undefined && metric.delta < 0
  );
</script>

<div class="metric-card card animate-enter" role="region" aria-label={metric.name}>
  <div class="metric-header">
    <span class="metric-name">{metric.name}</span>
    {#if metric.delta !== null && metric.delta !== undefined}
      <span
        class="badge delta-badge"
        class:badge-success={isPositiveDelta}
        class:badge-danger={isNegativeDelta}
      >
        {formatDelta(metric.delta)}
      </span>
    {/if}
  </div>

  <div class="metric-main">
    {#if metric.value === null || metric.value === undefined}
      <div class="skeleton skeleton-val" aria-hidden="true"></div>
    {:else}
      {#key metric.value}
        <span class="metric-value tabular-nums">{formatNumber(metric.value, 3)}</span>
      {/key}
    {/if}
    {#if metric.unit}
      <span class="metric-unit">{metric.unit}</span>
    {/if}
  </div>

  {#if metric.baseline_value !== null && metric.baseline_value !== undefined}
    <div class="metric-baseline">
      vs naive baseline: <span class="tabular-nums font-medium">{formatNumber(metric.baseline_value, 3)}</span>
    </div>
  {/if}

  {#if metric.uncertainty}
    <div class="metric-ci">
      {(metric.uncertainty.confidence_level * 100).toFixed(0)}% CI:
      <span class="tabular-nums">[{formatNumber(metric.uncertainty.lower, 3)} – {formatNumber(metric.uncertainty.upper, 3)}]</span>
    </div>
  {/if}

  {#if metric.description}
    <p class="metric-desc">{metric.description}</p>
  {/if}
</div>

<style>
  .metric-card {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    min-width: 200px;
    flex: 1;
    box-shadow: var(--shadow-xs);
  }

  .metric-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .metric-name {
    font-size: var(--font-xs);
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .metric-main {
    display: flex;
    align-items: baseline;
    gap: var(--space-2);
    margin-top: 2px;
  }

  @keyframes metric-num-enter {
    from {
      opacity: 0;
      transform: translateY(2px);
    }
    to {
      opacity: 1;
      transform: translateY(0);
    }
  }

  .metric-value {
    display: inline-block;
    font-size: var(--font-3xl);
    font-weight: 700;
    line-height: var(--leading-none);
    color: var(--text-primary);
    animation: metric-num-enter var(--duration-fast) var(--ease-out) both;
    will-change: transform, opacity;
  }

  .skeleton-val {
    width: 90px;
    height: 32px;
    border-radius: var(--radius-sm);
  }

  .metric-unit {
    font-size: var(--font-sm);
    color: var(--text-muted);
  }

  .metric-baseline {
    font-size: var(--font-xs);
    color: var(--text-muted);
    margin-top: 2px;
  }

  .font-medium {
    font-weight: 600;
    color: var(--text-secondary);
  }

  .metric-ci {
    font-size: var(--font-xs);
    color: var(--accent);
    font-weight: 500;
    margin-top: 2px;
  }

  .metric-desc {
    font-size: var(--font-xs);
    color: var(--text-secondary);
    margin-top: var(--space-2);
    line-height: var(--leading-tight);
  }

  .delta-badge {
    font-size: 11px;
    font-weight: 600;
  }

  @media (prefers-reduced-motion: reduce) {
    .metric-value {
      animation: none !important;
      transform: none !important;
    }
  }
</style>
