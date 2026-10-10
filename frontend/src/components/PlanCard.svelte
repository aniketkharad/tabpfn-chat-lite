<script lang="ts">
  import type { Plan } from '../types/contract';
  import { formatNumber, formatPercent } from '../lib/utils/formatters';

  let {
    plan,
    onConfirm,
    isExecuting = false,
  }: {
    plan: Plan;
    onConfirm: (plan: Plan) => void;
    isExecuting?: boolean;
  } = $props();
</script>

<div class="plan-card card" role="region" aria-label="Proposed Analysis Plan">
  <div class="plan-header">
    <div class="header-left">
      <span class="badge badge-accent">{plan.capability}</span>
      <h3 class="plan-title">Proposed Execution Plan</h3>
    </div>
    <span class="plan-id">{plan.plan_id}</span>
  </div>

  <div class="plan-body">
    <div class="plan-grid">
      {#if plan.target}
        <div class="plan-item">
          <span class="item-label">Target Column</span>
          <span class="item-value font-mono">{plan.target}</span>
        </div>
      {/if}

      <div class="plan-item">
        <span class="item-label">Features ({plan.features.length})</span>
        <div class="feature-tags">
          {#each plan.features as f}
            <span class="feature-chip">{f}</span>
          {/each}
        </div>
      </div>
    </div>

    <!-- Pre-execution Cost Projections -->
    <div class="estimate-box">
      <span class="estimate-title">Resource & Quota Estimate</span>
      <div class="estimate-metrics">
        <div class="est-item">
          <span class="est-label">Gemini Calls</span>
          <span class="est-value tabular-nums">{plan.estimate.gemini_calls}</span>
        </div>
        <div class="est-item">
          <span class="est-label">TabPFN Tokens</span>
          <span class="est-value tabular-nums">{formatNumber(plan.estimate.tabpfn_tokens, 0)}</span>
        </div>
        <div class="est-item">
          <span class="est-label">Daily Budget Share</span>
          <span class="est-value tabular-nums">{plan.estimate.pct_of_daily_budget.toFixed(1)}%</span>
        </div>
      </div>
    </div>
  </div>

  <div class="plan-footer">
    <button
      type="button"
      class="btn btn-primary"
      disabled={isExecuting}
      onclick={() => onConfirm(plan)}
    >
      {#if isExecuting}
        <span class="spinner-sm" aria-hidden="true"></span>
        <span>Running Analysis...</span>
      {:else}
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <polygon points="5 3 19 12 5 21 5 3"></polygon>
        </svg>
        <span>Confirm & Run Analysis</span>
      {/if}
    </button>
  </div>
</div>

<style>
  .plan-card {
    border-color: var(--border-default);
    margin: var(--space-3) 0;
    background: var(--bg-surface);
  }
  .plan-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    padding-bottom: var(--space-3);
    border-bottom: 1px solid var(--border-subtle);
  }
  .header-left {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  .plan-title {
    font-size: var(--font-base);
    font-weight: 600;
    color: var(--text-primary);
  }
  .plan-id {
    font-size: var(--font-xs);
    font-family: var(--font-mono);
    color: var(--text-muted);
  }
  .plan-body {
    padding: var(--space-3) 0;
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .plan-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-3);
  }
  @media (min-width: 500px) {
    .plan-grid {
      grid-template-columns: auto 1fr;
    }
  }
  .plan-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .item-label {
    font-size: var(--font-xs);
    font-weight: 500;
    color: var(--text-muted);
    text-transform: uppercase;
  }
  .item-value {
    font-size: var(--font-sm);
    color: var(--text-primary);
    font-weight: 600;
  }
  .font-mono {
    font-family: var(--font-mono);
  }
  .feature-tags {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
  }
  .feature-chip {
    font-size: var(--font-xs);
    font-family: var(--font-mono);
    background: var(--bg-subtle);
    color: var(--text-secondary);
    padding: 2px 6px;
    border-radius: 4px;
    border: 1px solid var(--border-subtle);
  }
  .estimate-box {
    background: var(--bg-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-3);
  }
  .estimate-title {
    font-size: var(--font-xs);
    font-weight: 600;
    color: var(--text-secondary);
    display: block;
    margin-bottom: var(--space-2);
  }
  .estimate-metrics {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
  }
  .est-item {
    display: flex;
    flex-direction: column;
  }
  .est-label {
    font-size: 10px;
    color: var(--text-muted);
  }
  .est-value {
    font-size: var(--font-base);
    font-weight: 700;
    color: var(--text-primary);
  }
  .plan-footer {
    display: flex;
    justify-content: flex-end;
    padding-top: var(--space-2);
  }
  .spinner-sm {
    width: 14px;
    height: 14px;
    border: 2px solid rgba(255, 255, 255, 0.4);
    border-top-color: #ffffff;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
