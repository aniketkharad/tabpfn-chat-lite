<script lang="ts">
  import { onMount, type Component } from 'svelte';
  import type { ChartKind } from '../types/contract';

  let { kind, title, description, data }: {
    kind: ChartKind;
    title?: string;
    description?: string;
    data: Record<string, any>;
  } = $props();

  let ChartComp: Component<{ kind: ChartKind; title?: string; description?: string; data: Record<string, any> }> | null = $state(null);
  let loadError: string | null = $state(null);

  onMount(async () => {
    try {
      const module = await import('./charts/ChartDispatcher.svelte');
      ChartComp = module.default;
    } catch (err) {
      loadError = 'Failed to load chart module';
    }
  });
</script>

{#if ChartComp}
  <ChartComp {kind} {title} {description} {data} />
{:else if loadError}
  <div class="chart-fallback">
    <p>{loadError}</p>
  </div>
{:else}
  <div class="chart-loading" aria-busy="true">
    <div class="spinner"></div>
    <span>Rendering SVG chart...</span>
  </div>
{/if}

<style>
  .chart-loading, .chart-fallback {
    min-height: 200px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--space-2);
    background: var(--bg-surface);
    border: 1px dashed var(--border-subtle);
    border-radius: var(--radius-md);
    color: var(--text-muted);
    font-size: var(--font-xs);
    margin: var(--space-3) 0;
  }
  .spinner {
    width: 20px;
    height: 20px;
    border: 2px solid var(--border-subtle);
    border-top-color: var(--accent);
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
  }
  @keyframes spin {
    to { transform: rotate(360deg); }
  }
</style>
