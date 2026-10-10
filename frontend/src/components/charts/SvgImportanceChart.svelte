<script lang="ts">
  let { data, title, description }: {
    data: {
      features?: string[];
      scores?: number[];
      std_dev?: number[];
    };
    title?: string;
    description?: string;
  } = $props();

  const width = 560;
  const padding = { top: 25, right: 70, bottom: 35, left: 135 };

  const rawFeatures = $derived(data.features ?? []);
  const rawScores = $derived(data.scores ?? []);
  const rawStd = $derived(data.std_dev ?? []);

  // Pair and sort by score descending
  const items = $derived(
    rawFeatures.map((f, i) => ({
      feature: f,
      score: rawScores[i] ?? 0,
      std: rawStd[i] ?? 0,
    })).sort((a, b) => b.score - a.score)
  );

  const rowHeight = 36;
  const height = $derived(padding.top + padding.bottom + Math.max(1, items.length) * rowHeight);
  const chartWidth = $derived(width - padding.left - padding.right);

  const maxScore = $derived(
    Math.max(0.001, ...items.map((it) => it.score + it.std)) * 1.15
  );

  function getBarWidth(score: number): number {
    return (score / maxScore) * chartWidth;
  }

  // Tooltip state
  let tooltip = $state<{
    visible: boolean;
    x: number;
    y: number;
    feature: string;
    score: string;
    std: string;
  }>({
    visible: false,
    x: 0,
    y: 0,
    feature: '',
    score: '',
    std: '',
  });

  function showTooltip(bx: number, by: number, feat: string, score: number, std: number): void {
    tooltip = {
      visible: true,
      x: Math.min(width - 95, Math.max(90, bx)),
      y: Math.max(30, by - 10),
      feature: feat,
      score: `Drop: ${score.toFixed(3)}`,
      std: std > 0 ? `±${std.toFixed(3)} std dev` : '',
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

<div class="chart-container" role="figure" aria-label={title || 'Feature Importance Chart'}>
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
        {@const x = padding.left + tick * chartWidth}
        <line x1={x} y1={padding.top} x2={x} y2={height - padding.bottom} class="grid-line" />
        <text x={x} y={height - 12} text-anchor="middle" class="tick-label tabular-nums">
          {(maxScore * tick).toFixed(3)}
        </text>
      {/each}

      <!-- Horizontal Bars -->
      {#each items as item, i}
        {@const y = padding.top + i * rowHeight}
        {@const barW = getBarWidth(item.score)}
        {@const barX = padding.left}

        <!-- Feature Label -->
        <text x={padding.left - 10} y={y + 16} text-anchor="end" class="feature-label">
          {item.feature}
        </text>

        <!-- Bar (Focusable with tooltips) -->
        <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
        <rect
          x={barX}
          y={y + 4}
          width={Math.max(3, barW)}
          height={18}
          rx="3"
          class="bar bar-importance"
          tabindex="0"
          role="graphics-symbol"
          aria-label="{item.feature}: score drop {item.score.toFixed(3)}{item.std ? ` ±${item.std.toFixed(3)}` : ''}"
          onmouseenter={() => showTooltip(barX + barW / 2, y, item.feature, item.score, item.std)}
          onmouseleave={hideTooltip}
          onfocus={() => showTooltip(barX + barW / 2, y, item.feature, item.score, item.std)}
          onblur={hideTooltip}
        />

        <!-- Std Dev Error Whiskers with Capped Ticks -->
        {#if item.std > 0}
          {@const whiskerLeft = padding.left + getBarWidth(Math.max(0, item.score - item.std))}
          {@const whiskerRight = padding.left + getBarWidth(item.score + item.std)}
          <line x1={whiskerLeft} y1={y + 13} x2={whiskerRight} y2={y + 13} class="whisker-line" />
          <line x1={whiskerLeft} y1={y + 8} x2={whiskerLeft} y2={y + 18} class="whisker-cap" />
          <line x1={whiskerRight} y1={y + 8} x2={whiskerRight} y2={y + 18} class="whisker-cap" />
        {/if}

        <!-- Direct Score Label Beside Bar (Never rely on visual length alone) -->
        {@const labelX = Math.max(
          padding.left + barW + 8,
          item.std > 0 ? padding.left + getBarWidth(item.score + item.std) + 8 : padding.left + barW + 8
        )}
        <text x={labelX} y={y + 16} class="score-label tabular-nums">
          {item.score.toFixed(3)}
        </text>
      {/each}

      <!-- Tooltip -->
      {#if tooltip.visible}
        <g class="tooltip-group" transform="translate({tooltip.x}, {tooltip.y})">
          <rect x="-65" y="-30" width="130" height="32" rx="4" class="tooltip-bg" />
          <text x="0" y="-18" text-anchor="middle" class="tooltip-title">{tooltip.feature}</text>
          <text x="0" y="-6" text-anchor="middle" class="tooltip-val tabular-nums">{tooltip.score} {tooltip.std ? `(${tooltip.std})` : ''}</text>
        </g>
      {/if}
    </svg>
  </div>

  <div class="legend" aria-hidden="true">
    <span class="legend-item">
      <span class="legend-bar-swatch"></span>
      <span>Permutation Importance Score (Metric Drop)</span>
    </span>
    {#if rawStd.length > 0}
      <span class="legend-item">
        <span class="legend-whisker-swatch"></span>
        <span>±1 Standard Deviation (Capped Whisker)</span>
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
            <th scope="col">Rank</th>
            <th scope="col">Feature Name</th>
            <th scope="col" class="align-right">Importance Drop</th>
            {#if rawStd.length > 0}
              <th scope="col" class="align-right">Std Dev (±)</th>
            {/if}
            <th scope="col" class="align-right">Relative Share</th>
          </tr>
        </thead>
        <tbody>
          {#each items as item, i}
            {@const share = maxScore > 0 ? (item.score / maxScore) * 100 : 0}
            <tr>
              <td>#{i + 1}</td>
              <td class="font-mono">{item.feature}</td>
              <td class="align-right tabular-nums">{item.score.toFixed(3)}</td>
              {#if rawStd.length > 0}
                <td class="align-right tabular-nums">{item.std > 0 ? `±${item.std.toFixed(3)}` : '—'}</td>
              {/if}
              <td class="align-right tabular-nums">{share.toFixed(1)}%</td>
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
  .feature-label {
    font-size: 11px;
    font-weight: 500;
    fill: var(--text-secondary);
  }
  .score-label {
    font-size: 11px;
    font-weight: 600;
    fill: var(--text-primary);
  }
  .bar {
    cursor: pointer;
    transition: opacity var(--duration-fast) var(--ease-standard);
  }
  .bar:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: 2px;
  }
  .bar-importance {
    fill: var(--accent);
    opacity: 0.88;
  }
  .bar-importance:hover, .bar-importance:focus {
    opacity: 1;
  }
  .whisker-line {
    stroke: var(--text-primary);
    stroke-width: 1.5;
  }
  .whisker-cap {
    stroke: var(--text-primary);
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
  .legend-bar-swatch {
    width: 12px;
    height: 8px;
    background: var(--accent);
    border-radius: 2px;
  }
  .legend-whisker-swatch {
    width: 14px;
    height: 2px;
    background: var(--text-primary);
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
  .font-mono {
    font-family: var(--font-mono);
  }
  .align-right {
    text-align: right;
  }

  /* High Contrast Mode */
  @media (prefers-contrast: more) {
    .chart-container {
      border: 2px solid var(--text-primary);
    }
    .bar-importance {
      fill: var(--text-primary);
      stroke: var(--text-primary);
      stroke-width: 1.5;
    }
    .whisker-line, .whisker-cap {
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
