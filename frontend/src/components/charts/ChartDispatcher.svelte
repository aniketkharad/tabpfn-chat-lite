<script lang="ts">
  import type { ChartKind } from '../../types/contract';
  import SvgBarChart from './SvgBarChart.svelte';
  import SvgLineChart from './SvgLineChart.svelte';
  import SvgScatterChart from './SvgScatterChart.svelte';
  import SvgReliabilityChart from './SvgReliabilityChart.svelte';
  import SvgIntervalChart from './SvgIntervalChart.svelte';
  import SvgImportanceChart from './SvgImportanceChart.svelte';

  let { kind, title, description, data }: {
    kind: ChartKind;
    title?: string;
    description?: string;
    data: Record<string, any>;
  } = $props();
</script>

{#if kind === 'bar'}
  <SvgBarChart {data} {title} {description} />
{:else if kind === 'line'}
  <SvgLineChart {data} {title} {description} />
{:else if kind === 'scatter'}
  <SvgScatterChart {data} {title} {description} />
{:else if kind === 'reliability'}
  <SvgReliabilityChart {data} {title} {description} />
{:else if kind === 'interval'}
  <SvgIntervalChart {data} {title} {description} />
{:else if kind === 'importance'}
  <SvgImportanceChart {data} {title} {description} />
{:else}
  <SvgBarChart {data} {title} {description} />
{/if}
