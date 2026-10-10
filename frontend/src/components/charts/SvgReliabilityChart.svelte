<script lang="ts">
  let { data, title, description }: {
    data: {
      bins?: number[];
      observed_frequencies?: number[];
      sample_counts?: number[];
    };
    title?: string;
    description?: string;
  } = $props();

  const width = 560;
  const height = 260;
  const padding = { top: 25, right: 30, bottom: 45, left: 55 };

  const chartWidth = $derived(width - padding.left - padding.right);
  const chartHeight = $derived(height - padding.top - padding.bottom);

  const bins = $derived(data.bins ?? [0.1, 0.3, 0.5, 0.7, 0.9]);
  const obs = $derived(data.observed_frequencies ?? []);
  const sampleCounts = $derived(data.sample_counts ?? []);

  function getX(val: number): number {
    return padding.left + val * chartWidth;
  }

  function getY(val: number): number {
    return padding.top + chartHeight - val * chartHeight;
  }

  const polylinePts = $derived(
    bins.map((b, i) => `${getX(b).toFixed(1)},${getY(obs[i] ?? b).toFixed(1)}`).join(' ')
  );

  // Tooltip state
  let tooltip = $state<{
    visible: boolean;
    x: number;
    y: number;
    binMid: string;
    observed: string;
    samples: string;
  }>({
    visible: false,
    x: 0,
    y: 0,
    binMid: '',
    observed: '',
    samples: '',
  });

  function showTooltip(cx: number, cy: number, bVal: number, oVal: number, count?: number): void {
    tooltip = {
      visible: true,
      x: Math.min(width - 90, Math.max(80, cx)),
      y: Math.max(35, cy - 14),
      binMid: `Predicted: ${(bVal * 100).toFixed(0)}%`,
      observed: `Observed: ${(oVal * 100).toFixed(1)}%`,
      samples: count !== undefined ? `N=${count} cases` : '',
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

<div class="chart-container" role="figure" aria-label={title || 'Calibration Reliability Curve'}>
  {#if title}
    <h4 class="chart-title">{title}</h4>
  {/if}
  {#if description}
    <p class="chart-desc">{description}</p>
  {/if}

  <div class="svg-wrapper">
    <svg viewBox="0 0 {width} {height}" class="chart-svg" aria-hidden="true">
      <!-- Grid -->
      {#each [0, 0.2, 0.4, 0.6, 0.8, 1.0] as tick}
        {@const y = padding.top + chartHeight * (1 - tick)}
        <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} class="grid-line" />
        <text x={padding.left - 8} y={y + 4} text-anchor="end" class="tick-label tabular-nums">
          {(tick * 100).toFixed(0)}%
        </text>

        {@const x = padding.left + tick * chartWidth}
        <line x1={x} y1={padding.top} x2={x} y2={height - padding.bottom} class="grid-line" />
        <text x={x} y={height - 12} text-anchor="middle" class="tick-label tabular-nums">
          {(tick * 100).toFixed(0)}%
        </text>
      {/each}

      <!-- Ideal Calibration Diagonal (y = x) - Dotted line -->
      <line
        x1={getX(0)}
        y1={getY(0)}
        x2={getX(1)}
        y2={getY(1)}
        class="ideal-calibration-line"
      />

      <!-- Observed Curve (Solid Line + Focusable Circles) -->
      {#if polylinePts}
        <polyline points={polylinePts} class="observed-curve" />
        {#each bins as b, i}
          {@const freq = obs[i] ?? b}
          {@const cx = getX(b)}
          {@const cy = getY(freq)}
          {@const count = sampleCounts[i]}
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
          <circle
            cx={cx}
            cy={cy}
            r="4.5"
            class="point point-reliability"
            tabindex="0"
            role="graphics-symbol"
            aria-label="Decile {b * 100}%: Observed {(freq * 100).toFixed(1)}%{count ? ` (${count} samples)` : ''}"
            onmouseenter={() => showTooltip(cx, cy, b, freq, count)}
            onmouseleave={hideTooltip}
            onfocus={() => showTooltip(cx, cy, b, freq, count)}
            onblur={hideTooltip}
          />
        {/each}
      {/if}

      <text x={width / 2} y={height - 2} text-anchor="middle" class="axis-title">
        Mean Predicted Probability Decile
      </text>

      <!-- Tooltip -->
      {#if tooltip.visible}
        <g class="tooltip-group" transform="translate({tooltip.x}, {tooltip.y})">
          <rect x="-70" y="-32" width="140" height="34" rx="4" class="tooltip-bg" />
          <text x="0" y="-19" text-anchor="middle" class="tooltip-title tabular-nums">{tooltip.binMid}</text>
          <text x="0" y="-7" text-anchor="middle" class="tooltip-val tabular-nums">{tooltip.observed} {tooltip.samples ? `(${tooltip.samples})` : ''}</text>
        </g>
      {/if}
    </svg>
  </div>

  <div class="legend" aria-hidden="true">
    <span class="legend-item">
      <span class="legend-circle-swatch"></span>
      <span>Empirical TabPFN Accuracy (Solid, Circles)</span>
    </span>
    <span class="legend-item">
      <span class="legend-dotted-line"></span>
      <span>Perfect Calibration y = x (Dotted Line)</span>
    </span>
  </div>

  <!-- Accessible Table Fallback -->
  <details class="chart-table-fallback">
    <summary class="fallback-summary">View data table (accessible fallback)</summary>
    <div class="fallback-table-wrapper">
      <table class="fallback-table">
        <thead>
          <tr>
            <th scope="col">Probability Bin</th>
            <th scope="col" class="align-right">Observed Frequency</th>
            <th scope="col" class="align-right">Ideal Calibration</th>
            <th scope="col" class="align-right">Calibration Error</th>
            {#if sampleCounts.length > 0}
              <th scope="col" class="align-right">Samples in Bin</th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each bins as b, i}
            {@const freq = obs[i] ?? b}
            {@const diff = freq - b}
            <tr>
              <td class="tabular-nums">{(b * 100).toFixed(0)}%</td>
              <td class="align-right tabular-nums">{(freq * 100).toFixed(1)}%</td>
              <td class="align-right tabular-nums">{(b * 100).toFixed(1)}%</td>
              <td class="align-right tabular-nums">{(diff >= 0 ? '+' : '')}{(diff * 100).toFixed(1)}%</td>
              {#if sampleCounts.length > 0}
                <td class="align-right tabular-nums">{sampleCounts[i] ?? '—'}</td>
              {/if}
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
  .axis-title {
    font-size: 11px;
    fill: var(--text-secondary);
  }
  .ideal-calibration-line {
    stroke: var(--text-muted);
    stroke-width: 1.5;
    stroke-dasharray: 4,4;
  }
  .observed-curve {
    fill: none;
    stroke: var(--accent);
    stroke-width: 2.5;
  }
  .point {
    cursor: pointer;
    transition: transform var(--duration-fast) var(--ease-standard);
  }
  .point:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .point-reliability {
    fill: var(--accent);
    stroke: #ffffff;
    stroke-width: 1;
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
    font-size: 10px;
    font-weight: 700;
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
  .legend-circle-swatch {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    background: var(--accent);
  }
  .legend-dotted-line {
    width: 16px;
    height: 2px;
    border-top: 1.5px dashed var(--text-muted);
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
    .observed-curve {
      stroke: var(--text-primary);
      stroke-width: 3;
    }
    .point-reliability {
      fill: var(--text-primary);
      stroke: var(--bg-surface);
      stroke-width: 1.5;
    }
    .ideal-calibration-line {
      stroke: var(--text-primary);
      stroke-dasharray: 2,2;
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
