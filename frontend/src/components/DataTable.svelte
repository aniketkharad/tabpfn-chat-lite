<script lang="ts">
  import type { CellValue, TableData } from '../types/contract';
  import { downloadTableAsCSV } from '../lib/csv/parser';
  import { formatNumber } from '../lib/utils/formatters';

  let {
    table,
    title,
    description,
    filename = 'dataset.csv',
    allowDownload = true,
  }: {
    table: TableData;
    title?: string;
    description?: string;
    filename?: string;
    allowDownload?: boolean;
  } = $props();

  function isNumericType(type: string): boolean {
    return type === 'int' || type === 'float';
  }

  function handleDownload(): void {
    downloadTableAsCSV(table, filename);
  }

  function formatCell(val: CellValue, type: string): string {
    if (val === null || val === undefined) return '—';
    if (typeof val === 'boolean') return val ? 'true' : 'false';
    if (type === 'float') return formatNumber(val, 3);
    if (type === 'int') return formatNumber(val, 0);
    return String(val);
  }
</script>

<div class="datatable-container" role="region" aria-label={title || 'Data Table'}>
  <div class="datatable-header">
    <div class="header-text">
      {#if title}
        <h3 class="datatable-title">{title}</h3>
      {/if}
      {#if description}
        <p class="datatable-desc">{description}</p>
      {/if}
    </div>

    <div class="header-meta">
      <span class="meta-pill tabular-nums">
        {table.rows.length} {table.rows.length === 1 ? 'row' : 'rows'} × {table.cols.length} cols
      </span>

      {#if allowDownload && table.rows.length > 0}
        <button
          type="button"
          class="btn btn-secondary btn-sm"
          onclick={handleDownload}
          aria-label="Download table as CSV"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
            <polyline points="7 10 12 15 17 10"></polyline>
            <line x1="12" y1="15" x2="12" y2="3"></line>
          </svg>
          Download CSV
        </button>
      {/if}
    </div>
  </div>

  <!-- svelte-ignore a11y_no_noninteractive_tabindex -->
  <div class="table-scroll-pane" tabindex="0" role="region" aria-label="Scrollable table rows">
    <table class="datatable">
      <thead>
        <tr>
          <th class="col-index">#</th>
          {#each table.cols as col, idx}
            {@const type = table.types[idx] ?? 'string'}
            <th class:align-right={isNumericType(type)} scope="col">
              <div class="th-content" class:justify-right={isNumericType(type)}>
                <span class="col-name">{col}</span>
                <span class="badge badge-type">{type}</span>
              </div>
            </th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#if table.rows.length === 0}
          <tr>
            <td colspan={table.cols.length + 1} class="empty-state">
              No data rows to display.
            </td>
          </tr>
        {:else}
          {#each table.rows as row, rIdx}
            <tr>
              <td class="col-index tabular-nums">{rIdx + 1}</td>
              {#each row as cell, cIdx}
                {@const type = table.types[cIdx] ?? 'string'}
                {@const isNum = isNumericType(type)}
                {@const isNull = cell === null || cell === undefined}
                <td class:align-right={isNum} class:cell-null={isNull}>
                  {#if isNull}
                    <span class="null-indicator" title="Null value">—</span>
                  {:else if isNum}
                    <span class="tabular-nums">{formatCell(cell, type)}</span>
                  {:else if type === 'boolean'}
                    <span class="badge badge-bool" class:badge-bool-true={cell === true}>{cell ? 'TRUE' : 'FALSE'}</span>
                  {:else}
                    <span>{formatCell(cell, type)}</span>
                  {/if}
                </td>
              {/each}
            </tr>
          {/each}
        {/if}
      </tbody>
    </table>
  </div>
</div>

<style>
  .datatable-container {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    box-shadow: var(--shadow-sm);
    margin: var(--space-4) 0;
    overflow: hidden;
  }
  .datatable-container:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }
  .datatable-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding: var(--space-3) var(--space-4);
    background: var(--bg-surface);
    border-bottom: 1px solid var(--border-subtle);
  }
  .datatable-title {
    font-size: var(--font-base);
    font-weight: 600;
    color: var(--text-primary);
  }
  .datatable-desc {
    font-size: var(--font-xs);
    color: var(--text-secondary);
    margin-top: 2px;
  }
  .header-meta {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  .meta-pill {
    font-size: var(--font-xs);
    color: var(--text-muted);
    background: var(--bg-subtle);
    padding: 3px var(--space-2);
    border-radius: var(--radius-full);
  }
  .table-scroll-pane {
    max-height: 440px;
    overflow: auto;
    position: relative;
    -webkit-overflow-scrolling: touch;
  }
  .datatable {
    width: 100%;
    border-collapse: collapse;
    font-size: var(--font-xs);
    text-align: left;
  }
  .datatable th {
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--bg-surface);
    color: var(--text-secondary);
    font-weight: 600;
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--border-default);
    white-space: nowrap;
    box-shadow: 0 1px 0 var(--border-default);
  }
  .th-content {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
  }
  .justify-right {
    justify-content: flex-end;
    width: 100%;
  }
  .col-name {
    color: var(--text-primary);
  }
  .badge-type {
    font-size: 9px;
    padding: 1px 4px;
    text-transform: lowercase;
    background: var(--bg-subtle);
    color: var(--text-muted);
  }
  .datatable td {
    padding: 6px var(--space-3);
    border-bottom: 1px solid var(--border-subtle);
    color: var(--text-primary);
    white-space: nowrap;
  }
  .datatable tr:hover td {
    background-color: var(--bg-subtle);
  }
  .col-index {
    width: 44px;
    text-align: center;
    color: var(--text-muted);
    font-size: 10px;
    user-select: none;
    background: var(--bg-surface);
  }
  .align-right {
    text-align: right;
  }
  .cell-null {
    color: var(--text-muted);
  }
  .null-indicator {
    font-style: italic;
    opacity: 0.6;
  }
  .badge-bool {
    font-size: 9px;
    padding: 1px 4px;
    border-radius: 3px;
    background: var(--bg-subtle);
    color: var(--text-secondary);
  }
  .badge-bool-true {
    background: var(--accent-subtle);
    color: var(--accent);
  }
  .btn-sm {
    padding: 4px var(--space-3);
    font-size: var(--font-xs);
  }
  .empty-state {
    text-align: center;
    padding: var(--space-8);
    color: var(--text-muted);
    font-style: italic;
  }
</style>
