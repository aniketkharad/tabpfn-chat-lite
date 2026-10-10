<script lang="ts">
  let { data, title, description }: {
    data: {
      indices?: number[];
      actuals?: number[];
      q10?: number[];
      q50?: number[];
      q90?: number[];
    };
    title?: string;
    description?: string;
  } = $props();

  const width = 560;
  const height = 260;
  const padding = { top: 25, right: 30, bottom: 45, left: 55 };

  const chartWidth = $derived(width - padding.left - padding.right);
  const chartHeight = $derived(height - padding.top - padding.bottom);

  const indices = $derived(data.indices ?? []);
  const actuals = $derived(data.actuals ?? data.actual ?? []);
  const q10 = $derived(data.q10 ?? []);
  const q50 = $derived(data.q50 ?? []);
  const q90 = $derived(data.q90 ?? []);

  const allVals = $derived([...actuals, ...q10, ...q50, ...q90].filter((v): v is number => typeof v === 'number'));
  const minVal = $derived(allVals.length ? Math.min(...allVals) * 0.9 : 0);
  const maxVal = $derived(allVals.length ? Math.max(...allVals) * 1.1 : 1);
  const valRange = $derived(Math.max(0.001, maxVal - minVal));

  const pointSpacing = $derived(indices.length > 1 ? chartWidth / (indices.length + 1) : chartWidth / 2);

  function getX(i: number): number {
    return padding.left + (i + 1) * pointSpacing;
  }

  function getY(val: number): number {
    return padding.top + chartHeight - ((val - minVal) / valRange) * chartHeight;
  }

  // Tooltip state
  let tooltip = $state<{
    visible: boolean;
    x: number;
    y: number;
    index: string;
    actual: string;
    median: string;
    interval: string;
  }>({
    visible: false,
    x: 0,
    y: 0,
    index: '',
    actual: '',
    median: '',
    interval: '',
  });

  function showTooltip(cx: number, cy: number, idx: number, act: number, med: number, low: number, high: number): void {
    tooltip = {
      visible: true,
      x: Math.min(width - 95, Math.max(85, cx)),
      y: Math.max(38, cy - 14),
      index: `Sample #${idx}`,
      actual: `Actual: ${act.toFixed(2)}`,
      median: `Median (q50): ${med.toFixed(2)}`,
      interval: `80% CI: [${low.toFixed(1)} – ${high.toFixed(1)}]`,
    };
  }

  function hideTooltip(): void {
    tooltip.visible = false;
  }

  function handleKeydown(e: KeyboardEvent): void {
    if (e.key === 'Escape') hideTooltip();
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="chart-container" role="figure" aria-label={title || 'Quantile Interval Chart'}>
  {#if title}
    <h4 class="chart-title">{title}</h4>
  {/if}
  {#if description}
    <p class="chart-desc">{description}</p>
  {/if}

  <div class="svg-wrapper">
    <svg viewBox="0 0 {width} {height}" class="chart-svg" aria-hidden="true">
      <!-- Grid -->
      {#each [0, 0.25, 0.5, 0.75, 1.0] as tick}
        {@const y = padding.top + chartHeight * (1 - tick)}
        <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} class="grid-line" />
        <text x={padding.left - 8} y={y + 4} text-anchor="end" class="tick-label tabular-nums">
          {(minVal + valRange * tick).toFixed(1)}
        </text>
      {/each}

      <!-- Intervals and Points -->
      {#each indices as idx, i}
        {@const cx = getX(i)}
        {@const low = q10[i] ?? 0}
        {@const med = q50[i] ?? 0}
        {@const high = q90[i] ?? 0}
        {@const act = actuals[i] ?? 0}
        {@const yLow = getY(low)}
        {@const yHigh = getY(high)}
        {@const yMed = getY(med)}
        {@const yAct = getY(act)}

        <!-- Interval vertical whisker -->
        <line
          x1={cx}
          y1={yLow}
          x2={cx}
          y2={yHigh}
          class="interval-whisker"
        />
        <!-- Interval caps -->
        <line x1={cx - 7} y1={yLow} x2={cx + 7} y2={yLow} class="interval-cap" />
        <line x1={cx - 7} y1={yHigh} x2={cx + 7} y2={yHigh} class="interval-cap" />

        <!-- Predicted median point (Diamond shape) -->
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <polygon
          points="{cx},{yMed - 5} {cx + 5},{yMed} {cx},{yMed + 5} {cx - 5},{yMed}"
          class="point point-median"
          tabindex="0"
          role="graphics-symbol"
          aria-label="Sample #{idx}: Predicted Median {med.toFixed(2)}, 80% CI [{low.toFixed(1)} – {high.toFixed(1)}]"
          onmouseenter={() => showTooltip(cx, yMed, idx, act, med, low, high)}
          onmouseleave={hideTooltip}
          onfocus={() => showTooltip(cx, yMed, idx, act, med, low, high)}
          onblur={hideTooltip}
        />

        <!-- Actual observed point (Outlined Circle) -->
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <circle
          cx={cx}
          cy={yAct}
          r="4.5"
          class="point point-actual"
          tabindex="0"
          role="graphics-symbol"
          aria-label="Sample #{idx}: Actual Observed {act.toFixed(2)}"
          onmouseenter={() => showTooltip(cx, yAct, idx, act, med, low, high)}
          onmouseleave={hideTooltip}
          onfocus={() => showTooltip(cx, yAct, idx, act, med, low, high)}
          onblur={hideTooltip}
        />

        <!-- X label -->
        <text x={cx} y={height - 12} text-anchor="middle" class="axis-label">
          #{idx}
        </text>
      {/each}

      <text x={width / 2} y={height - 2} text-anchor="middle" class="axis-title">
        Holdout Test Instance Index
      </text>

      <!-- Tooltip -->
      {#if tooltip.visible}
        <g class="tooltip-group" transform="translate({tooltip.x}, {tooltip.y})">
          <rect x="-80" y="-38" width="160" height="42" rx="4" class="tooltip-bg" />
          <text x="0" y="-24" text-anchor="middle" class="tooltip-title">{tooltip.index} • {tooltip.actual}</text>
          <text x="0" y="-12" text-anchor="middle" class="tooltip-val tabular-nums">{tooltip.median}</text>
          <text x="0" y="0" text-anchor="middle" class="tooltip-ci tabular-nums">{tooltip.interval}</text>
        </g>
      {/if}
    </svg>
  </div>

  <div class="legend" aria-hidden="true">
    <span class="legend-item">
      <span class="legend-diamond-swatch"></span>
      <span>Predicted Median q50 (Diamond)</span>
    </span>
    <span class="legend-item">
      <span class="legend-whisker-swatch"></span>
      <span>80% Credible Interval q10–q90 (Capped Whisker)</span>
    </span>
    <span class="legend-item">
      <span class="legend-circle-swatch"></span>
      <span>Actual Observed Value (Circle)</span>
    </span>
  </div>

  <!-- Accessible Table Fallback -->
  <details class="chart-table-fallback">
    <summary class="fallback-summary">View data table (accessible fallback)</summary>
    <div class="fallback-table-wrapper">
      <table class="fallback-table">
        <thead>
          <tr>
            <th scope="col">Sample Index</th>
            <th scope="col" class="align-right">Actual Observed</th>
            <th scope="col" class="align-right">Predicted Median (q50)</th>
            <th scope="col" class="align-right">Lower Bound (q10)</th>
            <th scope="col" class="align-right">Upper Bound (q90)</th>
            <th scope="col" class="align-right">In Credible Range</th>
          </tr>
        </thead>
        <tbody>
          {#each indices as idx, i}
            {@const act = actuals[i] ?? 0}
            {@const med = q50[i] ?? 0}
            {@const low = q10[i] ?? 0}
            {@const high = q90[i] ?? 0}
            {@const inside = act >= low && act <= high}
            <tr>
              <td>#{idx}</td>
              <td class="align-right tabular-nums">{act.toFixed(2)}</td>
              <td class="align-right tabular-nums">{med.toFixed(2)}</td>
              <td class="align-right tabular-nums">{low.toFixed(2)}</td>
              <td class="align-right tabular-nums">{high.toFixed(2)}</td>
              <td class="align-right">
                <span class="badge {inside ? 'badge-success' : 'badge-warning'}">
                  {inside ? 'INSIDE 80%' : 'OUTSIDE'}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  </details>
</div>

<style>
  .chart-container {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    margin: var(--space-3) 0;
  }
  .chart-title {
    font-size: var(--font-sm);
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-1);
  }
  .chart-desc {
    font-size: var(--font-xs);
    color: var(--text-secondary);
    margin-bottom: var(--space-3);
  }
  .svg-wrapper {
    position: relative;
    width: 100%;
  }
  .chart-svg {
    width: 100%;
    height: auto;
    overflow: visible;
  }
  .grid-line {
    stroke: var(--border-subtle);
    stroke-dasharray: 3,3;
  }
  .tick-label {
    font-size: 10px;
    fill: var(--text-muted);
  }
  .axis-label {
    font-size: 10px;
    fill: var(--text-secondary);
  }
  .axis-title {
    font-size: 11px;
    fill: var(--text-secondary);
  }
  .interval-whisker {
    stroke: var(--accent);
    stroke-width: 3.5;
    stroke-linecap: round;
    opacity: 0.65;
  }
  .interval-cap {
    stroke: var(--accent);
    stroke-width: 2;
  }
  .point {
    cursor: pointer;
    transition: transform var(--duration-fast) var(--ease-standard);
  }
  .point:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .point-median {
    fill: var(--accent);
    stroke: #ffffff;
    stroke-width: 1;
  }
  .point-actual {
    fill: #f59e0b;
    stroke: #ffffff;
    stroke-width: 1.5;
  }
  .tooltip-bg {
    fill: var(--text-primary);
    filter: drop-shadow(0 2px 4px rgba(0,0,0,0.25));
  }
  .tooltip-title {
    fill: var(--bg-surface);
    font-size: 10px;
    font-weight: 500;
  }
  .tooltip-val {
    fill: var(--bg-surface);
    font-size: 11px;
    font-weight: 700;
  }
  .tooltip-ci {
    fill: var(--border-default);
    font-size: 9px;
  }
  .legend {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-4);
    justify-content: center;
    margin-top: var(--space-2);
    font-size: var(--font-xs);
    color: var(--text-secondary);
  }
  .legend-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }
  .legend-diamond-swatch {
    width: 8px;
    height: 8px;
    background: var(--accent);
    transform: rotate(45deg);
  }
  .legend-whisker-swatch {
    width: 14px;
    height: 4px;
    background: var(--accent);
    border-radius: 2px;
  }
  .legend-circle-swatch {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: #f59e0b;
  }
  .chart-table-fallback {
    margin-top: var(--space-3);
    border-top: 1px solid var(--border-subtle);
    padding-top: var(--space-2);
  }
  .fallback-summary {
    font-size: var(--font-xs);
    color: var(--text-muted);
    cursor: pointer;
    user-select: none;
    font-weight: 500;
  }
  .fallback-summary:hover {
    color: var(--text-primary);
  }
  .fallback-table-wrapper {
    margin-top: var(--space-2);
    max-height: 200px;
    overflow-y: auto;
  }
  .fallback-table {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-xs);
  }
  .fallback-table th, .fallback-table td {
    padding: 4px 8px;
    border-bottom: 1px solid var(--border-subtle);
    text-align: left;
  }
  .align-right {
    text-align: right;
  }

  /* High Contrast Mode */
  @media (prefers-contrast: more) {
    .chart-container {
      border: 2px solid var(--text-primary);
    }
    .interval-whisker {
      stroke: var(--text-primary);
      stroke-width: 4;
      opacity: 1;
    }
    .interval-cap {
      stroke: var(--text-primary);
      stroke-width: 3;
    }
    .point-median {
      fill: var(--text-primary);
      stroke: var(--bg-surface);
      stroke-width: 2;
    }
    .point-actual {
      fill: var(--bg-surface);
      stroke: var(--text-primary);
      stroke-width: 2.5;
    }
    .grid-line {
      stroke: var(--text-primary);
      stroke-dasharray: 2,2;
    }
  }

  /* Reduced Motion */
  @media (prefers-reduced-motion: reduce) {
    .point {
      transition: none !important;
    }
  }
</style>
