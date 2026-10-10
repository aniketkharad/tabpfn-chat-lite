<script lang="ts">
  let { data, title, description }: {
    data: {
      x?: (string | number)[];
      historical?: (number | null)[];
      forecast?: (number | null)[];
      lower_80?: (number | null)[];
      upper_80?: (number | null)[];
      pdp_mean?: number[];
    };
    title?: string;
    description?: string;
  } = $props();

  const width = 560;
  const height = 260;
  const padding = { top: 25, right: 30, bottom: 45, left: 55 };

  const chartWidth = $derived(width - padding.left - padding.right);
  const chartHeight = $derived(height - padding.top - padding.bottom);

  const xLabels = $derived(data.x ?? []);
  const historical = $derived(data.historical ?? []);
  const forecast = $derived(data.forecast ?? []);
  const lower80 = $derived(data.lower_80 ?? data.lower80 ?? []);
  const upper80 = $derived(data.upper_80 ?? data.upper80 ?? []);
  const pdpMean = $derived(data.pdp_mean ?? []);

  // Compute scale boundaries
  const allValues = $derived(
    [...historical, ...forecast, ...lower80, ...upper80, ...pdpMean].filter(
      (v): v is number => v !== null && v !== undefined
    )
  );
  const minVal = $derived(allValues.length ? Math.min(...allValues) * 0.9 : 0);
  const maxVal = $derived(allValues.length ? Math.max(...allValues) * 1.1 : 1);
  const valRange = $derived(Math.max(0.001, maxVal - minVal));

  function getX(i: number, total: number): number {
    if (total <= 1) return padding.left + chartWidth / 2;
    return padding.left + (i / (total - 1)) * chartWidth;
  }

  function getY(val: number): number {
    return padding.top + chartHeight - ((val - minVal) / valRange) * chartHeight;
  }

  // Generate ribbon polygon points
  const ribbonPath = $derived.by(() => {
    if (!upper80.length || !lower80.length) return '';
    const upperPts: [number, number][] = [];
    const lowerPts: [number, number][] = [];

    for (let i = 0; i < xLabels.length; i++) {
      const u = upper80[i];
      const l = lower80[i];
      if (u !== null && u !== undefined && l !== null && l !== undefined) {
        upperPts.push([getX(i, xLabels.length), getY(u)]);
        lowerPts.push([getX(i, xLabels.length), getY(l)]);
      }
    }
    if (upperPts.length < 2) return '';
    const revLower = [...lowerPts].reverse();
    return [...upperPts, ...revLower].map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  });

  // Polyline generator
  function makePolyline(arr: (number | null)[]): string {
    return arr
      .map((val, i) => (val !== null && val !== undefined ? `${getX(i, xLabels.length).toFixed(1)},${getY(val).toFixed(1)}` : null))
      .filter(Boolean)
      .join(' ');
  }

  const histPath = $derived(makePolyline(historical));
  const forecastPath = $derived(makePolyline(forecast));
  const pdpPath = $derived(makePolyline(pdpMean));

  // Tooltip state
  let tooltip = $state<{
    visible: boolean;
    x: number;
    y: number;
    label: string;
    series: string;
    value: string;
  }>({
    visible: false,
    x: 0,
    y: 0,
    label: '',
    series: '',
    value: '',
  });

  function showTooltip(x: number, y: number, label: string, series: string, val: number): void {
    tooltip = {
      visible: true,
      x: Math.min(width - 90, Math.max(80, x)),
      y: Math.max(35, y - 12),
      label: String(label),
      series,
      value: val.toFixed(1),
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

<div class="chart-container" role="figure" aria-label={title || 'Line Chart'}>
  {#if title}
    <h4 class="chart-title">{title}</h4>
  {/if}
  {#if description}
    <p class="chart-desc">{description}</p>
  {/if}

  <div class="svg-wrapper">
    <svg viewBox="0 0 {width} {height}" class="chart-svg" aria-hidden="true">
      <!-- Grid lines -->
      {#each [0, 0.25, 0.5, 0.75, 1.0] as tick}
        {@const y = padding.top + chartHeight * (1 - tick)}
        <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} class="grid-line" />
        <text x={padding.left - 8} y={y + 4} text-anchor="end" class="tick-label tabular-nums">
          {(minVal + valRange * tick).toFixed(1)}
        </text>
      {/each}

      <!-- Confidence Ribbon (Shaded Area + Dotted Boundary Lines) -->
      {#if ribbonPath}
        <polygon points={ribbonPath} class="ribbon-polygon" />
        {#each upper80 as u, i}
          {@const l = lower80[i]}
          {#if u !== null && u !== undefined && l !== null && l !== undefined && i < xLabels.length - 1}
            {@const nextU = upper80[i + 1]}
            {@const nextL = lower80[i + 1]}
            {#if nextU !== null && nextU !== undefined && nextL !== null && nextL !== undefined}
              <line
                x1={getX(i, xLabels.length)}
                y1={getY(u)}
                x2={getX(i + 1, xLabels.length)}
                y2={getY(nextU)}
                class="ribbon-bound-line"
              />
              <line
                x1={getX(i, xLabels.length)}
                y1={getY(l)}
                x2={getX(i + 1, xLabels.length)}
                y2={getY(nextL)}
                class="ribbon-bound-line"
              />
            {/if}
          {/if}
        {/each}
      {/if}

      <!-- Historical Series (Solid Line + Circle Dots) -->
      {#if histPath}
        <polyline points={histPath} class="line-historical" />
        {#each historical as val, i}
          {#if val !== null && val !== undefined}
            {@const cx = getX(i, xLabels.length)}
            {@const cy = getY(val)}
            <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
            <circle
              cx={cx}
              cy={cy}
              r="4"
              class="point point-historical"
              tabindex="0"
              role="graphics-symbol"
              aria-label="{xLabels[i]} Historical: {val}"
              onmouseenter={() => showTooltip(cx, cy, String(xLabels[i]), 'Historical', val)}
              onmouseleave={hideTooltip}
              onfocus={() => showTooltip(cx, cy, String(xLabels[i]), 'Historical', val)}
              onblur={hideTooltip}
            />
          {/if}
        {/each}
      {/if}

      <!-- Forecast Line (Dashed Line + Diamond Dots) -->
      {#if forecastPath}
        <polyline points={forecastPath} class="line-forecast" />
        {#each forecast as val, i}
          {#if val !== null && val !== undefined}
            {@const cx = getX(i, xLabels.length)}
            {@const cy = getY(val)}
            <!-- Diamond shape for colour-blind differentiation -->
            <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
            <polygon
              points="{cx},{cy - 5} {cx + 5},{cy} {cx},{cy + 5} {cx - 5},{cy}"
              class="point point-forecast"
              tabindex="0"
              role="graphics-symbol"
              aria-label="{xLabels[i]} Forecast: {val}"
              onmouseenter={() => showTooltip(cx, cy, String(xLabels[i]), 'Forecast', val)}
              onmouseleave={hideTooltip}
              onfocus={() => showTooltip(cx, cy, String(xLabels[i]), 'Forecast', val)}
              onblur={hideTooltip}
            />
          {/if}
        {/each}
      {/if}

      <!-- PDP Line -->
      {#if pdpPath}
        <polyline points={pdpPath} class="line-pdp" />
        {#each pdpMean as val, i}
          {@const cx = getX(i, xLabels.length)}
          {@const cy = getY(val)}
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
          <circle
            cx={cx}
            cy={cy}
            r="4"
            class="point point-pdp"
            tabindex="0"
            role="graphics-symbol"
            aria-label="{xLabels[i]} PDP: {val}"
            onmouseenter={() => showTooltip(cx, cy, String(xLabels[i]), 'Partial Dependence', val)}
            onmouseleave={hideTooltip}
            onfocus={() => showTooltip(cx, cy, String(xLabels[i]), 'Partial Dependence', val)}
            onblur={hideTooltip}
          />
        {/each}
      {/if}

      <!-- X Axis Labels -->
      {#each xLabels as lbl, i}
        <text x={getX(i, xLabels.length)} y={height - 12} text-anchor="middle" class="axis-label">
          {lbl}
        </text>
      {/each}

      <!-- Tooltip -->
      {#if tooltip.visible}
        <g class="tooltip-group" transform="translate({tooltip.x}, {tooltip.y})">
          <rect x="-65" y="-30" width="130" height="32" rx="4" class="tooltip-bg" />
          <text x="0" y="-18" text-anchor="middle" class="tooltip-title">{tooltip.label}</text>
          <text x="0" y="-6" text-anchor="middle" class="tooltip-val tabular-nums">{tooltip.series}: {tooltip.value}</text>
        </g>
      {/if}
    </svg>
  </div>

  <div class="legend" aria-hidden="true">
    {#if histPath && forecastPath}
      <span class="legend-item">
        <span class="legend-circle-swatch"></span>
        <span>Historical (Solid, Circles)</span>
      </span>
      <span class="legend-item">
        <span class="legend-diamond-swatch"></span>
        <span>Forecast (Dashed, Diamonds)</span>
      </span>
      <span class="legend-item">
        <span class="legend-ribbon-swatch"></span>
        <span>80% Bound (Dotted Ribbon)</span>
      </span>
    {:else if pdpPath}
      <span class="legend-item">
        <span class="legend-circle-swatch"></span>
        <span>Partial Dependence (Mean)</span>
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
            <th scope="col">Timepoint / X</th>
            {#if histPath}
              <th scope="col" class="align-right">Historical</th>
            {/if}
            {#if forecastPath}
              <th scope="col" class="align-right">Forecast Mean</th>
              <th scope="col" class="align-right">Lower 80%</th>
              <th scope="col" class="align-right">Upper 80%</th>
            {/if}
            {#if pdpPath}
              <th scope="col" class="align-right">Partial Dependence</th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each xLabels as lbl, i}
            <tr>
              <td>{lbl}</td>
              {#if histPath}
                <td class="align-right tabular-nums">{historical[i] !== null && historical[i] !== undefined ? historical[i] : '—'}</td>
              {/if}
              {#if forecastPath}
                <td class="align-right tabular-nums">{forecast[i] !== null && forecast[i] !== undefined ? forecast[i] : '—'}</td>
                <td class="align-right tabular-nums">{lower80[i] !== null && lower80[i] !== undefined ? lower80[i] : '—'}</td>
                <td class="align-right tabular-nums">{upper80[i] !== null && upper80[i] !== undefined ? upper80[i] : '—'}</td>
              {/if}
              {#if pdpPath}
                <td class="align-right tabular-nums">{pdpMean[i] !== null && pdpMean[i] !== undefined ? pdpMean[i] : '—'}</td>
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
  .axis-label {
    font-size: 10px;
    fill: var(--text-secondary);
  }
  .ribbon-polygon {
    fill: var(--accent);
    opacity: 0.16;
  }
  .ribbon-bound-line {
    stroke: var(--accent);
    stroke-width: 1;
    stroke-dasharray: 2,2;
  }
  .line-historical {
    fill: none;
    stroke: var(--text-secondary);
    stroke-width: 2.5;
  }
  .line-forecast {
    fill: none;
    stroke: var(--accent);
    stroke-width: 2.5;
    stroke-dasharray: 6,4;
  }
  .line-pdp {
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
  .point-historical {
    fill: var(--text-secondary);
  }
  .point-forecast {
    fill: var(--accent);
    stroke: #ffffff;
    stroke-width: 1;
  }
  .point-pdp {
    fill: var(--accent);
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
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--text-secondary);
  }
  .legend-diamond-swatch {
    width: 8px;
    height: 8px;
    background: var(--accent);
    transform: rotate(45deg);
  }
  .legend-ribbon-swatch {
    width: 12px;
    height: 8px;
    background: var(--accent);
    opacity: 0.25;
    border: 1px dotted var(--accent);
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
    .line-historical {
      stroke: var(--text-primary);
      stroke-width: 3;
    }
    .line-forecast {
      stroke: var(--text-primary);
      stroke-width: 3;
      stroke-dasharray: 4,4;
    }
    .point-historical {
      fill: var(--text-primary);
    }
    .point-forecast {
      fill: var(--text-primary);
      stroke: var(--bg-surface);
      stroke-width: 1.5;
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
