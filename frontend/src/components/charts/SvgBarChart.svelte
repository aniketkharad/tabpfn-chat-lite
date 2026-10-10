<script lang="ts">
  let { data, title, description }: {
    data: {
      categories?: string[];
      real_percentages?: number[];
      synthetic_percentages?: number[];
      labels?: string[];
      values?: number[];
    };
    title?: string;
    description?: string;
  } = $props();

  const categories = $derived(data.categories || data.labels || []);
  const real = $derived(data.real_percentages || data.values || []);
  const synthetic = $derived(data.synthetic_percentages || []);
  const isComparison = $derived(synthetic.length > 0);

  const width = 560;
  const height = 260;
  const padding = { top: 25, right: 30, bottom: 45, left: 55 };

  const chartWidth = $derived(width - padding.left - padding.right);
  const chartHeight = $derived(height - padding.top - padding.bottom);

  const maxVal = $derived(
    Math.max(1, ...real, ...synthetic) * 1.15
  );

  const groupWidth = $derived(categories.length > 0 ? chartWidth / categories.length : chartWidth);

  // Tooltip state
  let tooltip = $state<{
    visible: boolean;
    x: number;
    y: number;
    title: string;
    series: string;
    value: string;
  }>({
    visible: false,
    x: 0,
    y: 0,
    title: '',
    series: '',
    value: '',
  });

  function showTooltip(x: number, y: number, catTitle: string, seriesName: string, val: number): void {
    tooltip = {
      visible: true,
      x: Math.min(width - 100, Math.max(80, x)),
      y: Math.max(35, y - 10),
      title: catTitle,
      series: seriesName,
      value: `${val.toFixed(1)}%`,
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

<div class="chart-container" role="figure" aria-label={title || 'Bar Chart'}>
  {#if title}
    <h4 class="chart-title">{title}</h4>
  {/if}
  {#if description}
    <p class="chart-desc">{description}</p>
  {/if}

  <div class="svg-wrapper">
    <svg viewBox="0 0 {width} {height}" class="chart-svg" aria-hidden="true">
      <defs>
        <!-- Accessible diagonal hatch pattern for synthetic data (never rely on colour alone) -->
        <pattern id="bar-hatch-pattern" width="8" height="8" patternTransform="rotate(45 0 0)" patternUnits="userSpaceOnUse">
          <line x1="0" y1="0" x2="0" y2="8" stroke="#0d9488" stroke-width="2.5" />
        </pattern>
      </defs>

      <!-- Grid lines -->
      {#each [0, 0.25, 0.5, 0.75, 1.0] as tick}
        {@const y = padding.top + chartHeight * (1 - tick)}
        <line x1={padding.left} y1={y} x2={width - padding.right} y2={y} class="grid-line" />
        <text x={padding.left - 8} y={y + 4} text-anchor="end" class="tick-label tabular-nums">
          {(maxVal * tick).toFixed(0)}%
        </text>
      {/each}

      <!-- Bars -->
      {#each categories as cat, i}
        {@const groupX = padding.left + i * groupWidth}
        {@const valReal = real[i] ?? 0}
        {@const hReal = (valReal / maxVal) * chartHeight}
        {@const yReal = padding.top + chartHeight - hReal}

        {#if isComparison}
          {@const valSyn = synthetic[i] ?? 0}
          {@const hSyn = (valSyn / maxVal) * chartHeight}
          {@const ySyn = padding.top + chartHeight - hSyn}
          {@const barW = Math.max(14, groupWidth * 0.35)}
          {@const xReal = groupX + groupWidth * 0.1}
          {@const xSyn = groupX + groupWidth * 0.52}

          <!-- Real bar (Solid Fill) -->
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
          <rect
            x={xReal}
            y={yReal}
            width={barW}
            height={hReal}
            rx="3"
            class="bar bar-real"
            tabindex="0"
            role="graphics-symbol"
            aria-label="{cat} - Real Data: {valReal.toFixed(1)}%"
            onmouseenter={() => showTooltip(xReal + barW / 2, yReal, cat, 'Real Data', valReal)}
            onmouseleave={hideTooltip}
            onfocus={() => showTooltip(xReal + barW / 2, yReal, cat, 'Real Data', valReal)}
            onblur={hideTooltip}
          />

          <!-- Synthetic bar (Hatched Texture + Distinct Outline) -->
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
          <rect
            x={xSyn}
            y={ySyn}
            width={barW}
            height={hSyn}
            rx="3"
            class="bar bar-synthetic"
            tabindex="0"
            role="graphics-symbol"
            aria-label="{cat} - Synthetic Data: {valSyn.toFixed(1)}%"
            onmouseenter={() => showTooltip(xSyn + barW / 2, ySyn, cat, 'Synthetic Data', valSyn)}
            onmouseleave={hideTooltip}
            onfocus={() => showTooltip(xSyn + barW / 2, ySyn, cat, 'Synthetic Data', valSyn)}
            onblur={hideTooltip}
          />
        {:else}
          {@const barW = Math.max(20, groupWidth * 0.6)}
          {@const barX = groupX + (groupWidth - barW) / 2}
          <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
          <rect
            x={barX}
            y={yReal}
            width={barW}
            height={hReal}
            rx="3"
            class="bar bar-real"
            tabindex="0"
            role="graphics-symbol"
            aria-label="{cat}: {valReal.toFixed(1)}%"
            onmouseenter={() => showTooltip(barX + barW / 2, yReal, cat, 'Value', valReal)}
            onmouseleave={hideTooltip}
            onfocus={() => showTooltip(barX + barW / 2, yReal, cat, 'Value', valReal)}
            onblur={hideTooltip}
          />
        {/if}

        <!-- X label -->
        <text x={groupX + groupWidth / 2} y={height - 12} text-anchor="middle" class="axis-label">
          {cat}
        </text>
      {/each}

      <!-- Interactive Tooltip Pill -->
      {#if tooltip.visible}
        <g class="tooltip-group" transform="translate({tooltip.x}, {tooltip.y})">
          <rect x="-65" y="-30" width="130" height="32" rx="4" class="tooltip-bg" />
          <text x="0" y="-18" text-anchor="middle" class="tooltip-title">{tooltip.title}</text>
          <text x="0" y="-6" text-anchor="middle" class="tooltip-val tabular-nums">{tooltip.series}: {tooltip.value}</text>
        </g>
      {/if}
    </svg>
  </div>

  {#if isComparison}
    <div class="legend" aria-hidden="true">
      <span class="legend-item">
        <span class="legend-swatch swatch-solid"></span>
        <span>Real Training Data (Solid)</span>
      </span>
      <span class="legend-item">
        <span class="legend-swatch swatch-hatched"></span>
        <span>Synthetic Generated (Hatched)</span>
      </span>
    </div>
  {/if}

  <!-- Accessible Table Fallback -->
  <details class="chart-table-fallback">
    <summary class="fallback-summary">View data table (accessible fallback)</summary>
    <div class="fallback-table-wrapper">
      <table class="fallback-table">
        <thead>
          <tr>
            <th scope="col">Category</th>
            <th scope="col" class="align-right">Real Percentage</th>
            {#if isComparison}
              <th scope="col" class="align-right">Synthetic Percentage</th>
              <th scope="col" class="align-right">Delta</th>
            {/if}
          </tr>
        </thead>
        <tbody>
          {#each categories as cat, i}
            <tr>
              <td>{cat}</td>
              <td class="align-right tabular-nums">{(real[i] ?? 0).toFixed(1)}%</td>
              {#if isComparison}
                <td class="align-right tabular-nums">{(synthetic[i] ?? 0).toFixed(1)}%</td>
                <td class="align-right tabular-nums">{((synthetic[i] ?? 0) - (real[i] ?? 0) >= 0 ? '+' : '')}{((synthetic[i] ?? 0) - (real[i] ?? 0)).toFixed(1)}%</td>
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
    font-size: 11px;
    fill: var(--text-secondary);
  }
  .bar {
    cursor: pointer;
    transition: opacity var(--duration-fast) var(--ease-standard);
  }
  .bar:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .bar-real {
    fill: var(--accent);
    stroke: var(--accent);
    stroke-width: 1;
    opacity: 0.9;
  }
  .bar-real:hover, .bar-real:focus {
    opacity: 1;
  }
  .bar-synthetic {
    fill: url(#bar-hatch-pattern);
    stroke: #0d9488;
    stroke-width: 1.5;
    stroke-dasharray: 4,2;
  }
  .bar-synthetic:hover, .bar-synthetic:focus {
    stroke-width: 2;
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
  .legend-swatch {
    width: 12px;
    height: 12px;
    border-radius: 2px;
  }
  .swatch-solid {
    background: var(--accent);
    border: 1px solid var(--accent);
  }
  .swatch-hatched {
    background: repeating-linear-gradient(45deg, #0d9488, #0d9488 2px, transparent 2px, transparent 5px);
    border: 1.5px dashed #0d9488;
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
    .bar-real {
      fill: var(--text-primary);
      stroke: var(--text-primary);
      stroke-width: 2;
    }
    .bar-synthetic {
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
    .bar {
      transition: none !important;
    }
  }
</style>
