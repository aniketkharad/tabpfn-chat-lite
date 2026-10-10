<script lang="ts">
  let { data, title, description }: {
    data: {
      actual?: number[];
      predicted?: number[];
      x?: number[];
      y?: number[];
      is_outlier?: boolean[];
    };
    title?: string;
    description?: string;
  } = $props();

  const width = 560;
  const height = 260;
  const padding = { top: 25, right: 30, bottom: 45, left: 55 };

  const chartWidth = $derived(width - padding.left - padding.right);
  const chartHeight = $derived(height - padding.top - padding.bottom);

  const xPts = $derived(data.actual ?? data.x ?? []);
  const yPts = $derived(data.predicted ?? data.y ?? []);
  const isOutlier = $derived(data.is_outlier ?? []);
  const isActualVsPredicted = $derived(!!data.actual && !!data.predicted);

  const minX = $derived(xPts.length ? Math.min(...xPts) * 0.9 : 0);
  const maxX = $derived(xPts.length ? Math.max(...xPts) * 1.1 : 1);
  const rangeX = $derived(Math.max(0.001, maxX - minX));

  const minY = $derived(yPts.length ? Math.min(...yPts) * 0.9 : 0);
  const maxY = $derived(yPts.length ? Math.max(...yPts) * 1.1 : 1);
  const rangeY = $derived(Math.max(0.001, maxY - minY));

  // Global bounds for identity line if actual vs predicted
  const minCoord = $derived(Math.min(minX, minY));
  const maxCoord = $derived(Math.max(maxX, maxY));
  const coordRange = $derived(Math.max(0.001, maxCoord - minCoord));

  function getX(val: number): number {
    const min = isActualVsPredicted ? minCoord : minX;
    const r = isActualVsPredicted ? coordRange : rangeX;
    return padding.left + ((val - min) / r) * chartWidth;
  }

  function getY(val: number): number {
    const min = isActualVsPredicted ? minCoord : minY;
    const r = isActualVsPredicted ? coordRange : rangeY;
    return padding.top + chartHeight - ((val - min) / r) * chartHeight;
  }

  // Tooltip state
  let tooltip = $state<{
    visible: boolean;
    x: number;
    y: number;
    label: string;
    detail: string;
  }>({
    visible: false,
    x: 0,
    y: 0,
    label: '',
    detail: '',
  });

  function showTooltip(cx: number, cy: number, xVal: number, yVal: number, outlier: boolean): void {
    const xName = isActualVsPredicted ? 'Actual' : 'X';
    const yName = isActualVsPredicted ? 'Predicted' : 'Y';
    tooltip = {
      visible: true,
      x: Math.min(width - 90, Math.max(80, cx)),
      y: Math.max(35, cy - 14),
      label: `${xName}: ${xVal.toFixed(2)}, ${yName}: ${yVal.toFixed(2)}`,
      detail: outlier ? 'FLAGGED OUTLIER' : isActualVsPredicted ? `Residual: ${(yVal - xVal >= 0 ? '+' : '')}${(yVal - xVal).toFixed(2)}` : 'Normal Inlier',
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

<div class="chart-container" role="figure" aria-label={title || 'Scatter Chart'}>
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
          {((isActualVsPredicted ? minCoord : minY) + (isActualVsPredicted ? coordRange : rangeY) * tick).toFixed(1)}
        </text>
      {/each}

      <!-- Identity line for Actual vs Predicted (Dashed) -->
      {#if isActualVsPredicted}
        <line
          x1={getX(minCoord)}
          y1={getY(minCoord)}
          x2={getX(maxCoord)}
          y2={getY(maxCoord)}
          class="identity-line"
        />
      {/if}

      <!-- Points -->
      {#each xPts as xVal, i}
        {@const yVal = yPts[i] ?? 0}
        {@const cx = getX(xVal)}
        {@const cy = getY(yVal)}
        {@const outlier = isOutlier[i] ?? false}

        {#if outlier}
          <!-- Distinct triangle marker for outliers (never rely on colour alone) -->
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
          <polygon
            points="{cx},{cy - 8} {cx + 7},{cy + 5} {cx - 7},{cy + 5}"
            class="point point-outlier"
            tabindex="0"
            role="graphics-symbol"
            aria-label="Outlier: X={xVal.toFixed(2)}, Y={yVal.toFixed(2)}"
            onmouseenter={() => showTooltip(cx, cy, xVal, yVal, true)}
            onmouseleave={hideTooltip}
            onfocus={() => showTooltip(cx, cy, xVal, yVal, true)}
            onblur={hideTooltip}
          />
        {:else}
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
          <circle
            cx={cx}
            cy={cy}
            r="4.5"
            class="point point-normal"
            tabindex="0"
            role="graphics-symbol"
            aria-label="{isActualVsPredicted ? 'Sample' : 'Inlier'}: X={xVal.toFixed(2)}, Y={yVal.toFixed(2)}"
            onmouseenter={() => showTooltip(cx, cy, xVal, yVal, false)}
            onmouseleave={hideTooltip}
            onfocus={() => showTooltip(cx, cy, xVal, yVal, false)}
            onblur={hideTooltip}
          />
        {/if}
      {/each}

      <!-- X Axis title -->
      <text x={width / 2} y={height - 10} text-anchor="middle" class="axis-title">
        {isActualVsPredicted ? 'Actual Observed Value' : 'Metric X'}
      </text>

      <!-- Tooltip -->
      {#if tooltip.visible}
        <g class="tooltip-group" transform="translate({tooltip.x}, {tooltip.y})">
          <rect x="-75" y="-32" width="150" height="34" rx="4" class="tooltip-bg" />
          <text x="0" y="-19" text-anchor="middle" class="tooltip-title tabular-nums">{tooltip.label}</text>
          <text x="0" y="-7" text-anchor="middle" class="tooltip-val">{tooltip.detail}</text>
        </g>
      {/if}
    </svg>
  </div>

  <div class="legend" aria-hidden="true">
    {#if isActualVsPredicted}
      <span class="legend-item">
        <span class="legend-circle-swatch"></span>
        <span>Holdout Prediction Samples (Circles)</span>
      </span>
      <span class="legend-item">
        <span class="legend-identity-line"></span>
        <span>Perfect Identity y = x (Dashed Line)</span>
      </span>
    {:else if isOutlier.length}
      <span class="legend-item">
        <span class="legend-circle-swatch"></span>
        <span>Normal Inliers (Circles)</span>
      </span>
      <span class="legend-item">
        <span class="legend-triangle-swatch">▲</span>
        <span>Flagged Outliers (Triangles)</span>
      </span>
    {/if}
  </div>

  <!-- Accessible Table Fallback -->
  <details class="chart-table-fallback">
    <summary class="fallback-summary">View data table (accessible fallback)</summary>
    <div class="fallback-table-wrapper">
      <table class="fallback-table">
        <thead>
          <tr>
            <th scope="col">#</th>
            <th scope="col" class="align-right">{isActualVsPredicted ? 'Actual Observed' : 'X Coordinate'}</th>
            <th scope="col" class="align-right">{isActualVsPredicted ? 'Predicted Value' : 'Y Coordinate'}</th>
            {#if isActualVsPredicted}
              <th scope="col" class="align-right">Residual</th>
            {/if}
            {#if isOutlier.length}
              <th scope="col" class="align-right">Outlier Status</th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each xPts as xVal, i}
            {@const yVal = yPts[i] ?? 0}
            <tr>
              <td>{i + 1}</td>
              <td class="align-right tabular-nums">{xVal.toFixed(2)}</td>
              <td class="align-right tabular-nums">{yVal.toFixed(2)}</td>
              {#if isActualVsPredicted}
                <td class="align-right tabular-nums">{(yVal - xVal >= 0 ? '+' : '')}{(yVal - xVal).toFixed(2)}</td>
              {/if}
              {#if isOutlier.length}
                <td class="align-right">
                  <span class="badge {isOutlier[i] ? 'badge-danger' : 'badge-success'}">
                    {isOutlier[i] ? 'ANOMALY' : 'NORMAL'}
                  </span>
                </td>
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
  .identity-line {
    stroke: var(--text-muted);
    stroke-width: 1.5;
    stroke-dasharray: 6,4;
  }
  .point {
    cursor: pointer;
    transition: transform var(--duration-fast) var(--ease-standard);
  }
  .point:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .point-normal {
    fill: var(--accent);
    stroke: #ffffff;
    stroke-width: 1;
    opacity: 0.85;
  }
  .point-outlier {
    fill: var(--danger);
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
  .legend-triangle-swatch {
    color: var(--danger);
    font-size: 12px;
    line-height: 1;
  }
  .legend-identity-line {
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
    .point-normal {
      fill: var(--text-primary);
      stroke: var(--bg-surface);
      stroke-width: 1.5;
    }
    .point-outlier {
      fill: var(--text-primary);
      stroke: var(--bg-surface);
      stroke-width: 2;
    }
    .identity-line {
      stroke: var(--text-primary);
      stroke-dasharray: 4,4;
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
