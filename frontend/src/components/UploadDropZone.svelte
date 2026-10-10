<script lang="ts">
  import type { ErrorCode, ServiceStatus, TableData } from '../types/contract';
  import { parseCSV } from '../lib/csv/parser';
  import { screenForPII } from '../lib/csv/pii';

  let {
    status,
    onParsedTable,
    onError,
  }: {
    status: ServiceStatus | null;
    onParsedTable: (table: TableData, filename: string) => void;
    onError: (code: ErrorCode, message: string) => void;
  } = $props();

  let isDragging = $state(false);
  let fileInputRef: HTMLInputElement | null = $state(null);

  const limits = $derived(
    status?.limits ?? {
      max_rows: 200,
      max_cols: 50,
      max_cells: 10000,
      max_file_size_bytes: 1048576,
      max_turns: 15,
    }
  );

  function handleDragOver(e: DragEvent): void {
    e.preventDefault();
    isDragging = true;
  }

  function handleDragLeave(): void {
    isDragging = false;
  }

  function handleDrop(e: DragEvent): void {
    e.preventDefault();
    isDragging = false;
    const file = e.dataTransfer?.files?.[0];
    if (file) {
      processSelectedFile(file);
    }
  }

  function handleFileInputChange(e: Event): void {
    const target = e.target as HTMLInputElement;
    const file = target.files?.[0];
    if (file) {
      processSelectedFile(file);
    }
  }

  async function processSelectedFile(file: File): Promise<void> {
    // 1. Pre-check file size
    if (file.size > limits.max_file_size_bytes) {
      onError(
        'validation',
        `File size (${(file.size / 1024).toFixed(1)} KB) exceeds limit of ${(limits.max_file_size_bytes / 1024).toFixed(0)} KB.`
      );
      return;
    }

    try {
      const text = await file.text();

      // 2. Client-side RFC 4180 parsing with type inference
      const result = parseCSV(text, {
        maxRows: limits.max_rows,
        maxCols: limits.max_cols,
      });

      if (result.errors.length > 0) {
        onError('validation', result.errors.join(' '));
        return;
      }

      if (result.table.rows.length === 0 || result.table.cols.length === 0) {
        onError('validation', 'Uploaded file contains no rows or columns.');
        return;
      }

      // 3. Client-side PII Screening
      const pii = screenForPII(result.table);
      if (pii.detected) {
        onError('pii_detected', pii.message);
        return;
      }

      // Preview renders client-side before any network call
      onParsedTable(result.table, file.name);
    } catch (err) {
      onError('validation', 'Failed to read or parse CSV file. Please ensure it is standard UTF-8 CSV text.');
    }
  }
</script>

<div
  class="dropzone-card card"
  class:dragging={isDragging}
  role="region"
  aria-label="CSV Upload Drop Zone"
  ondragover={handleDragOver}
  ondragleave={handleDragLeave}
  ondrop={handleDrop}
>
  <input
    type="file"
    accept=".csv,text/csv"
    bind:this={fileInputRef}
    onchange={handleFileInputChange}
    class="file-input-hidden"
    id="csv-file-upload"
  />

  <div class="dropzone-content">
    <div class="drop-icon" aria-hidden="true">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="17 8 12 3 7 8"></polyline>
        <line x1="12" y1="3" x2="12" y2="15"></line>
      </svg>
    </div>

    <div class="drop-text">
      <h3 class="drop-title">Drop your CSV here, or browse</h3>
      <p class="drop-subtitle">
        Supports RFC 4180 CSV tables up to {limits.max_rows} rows and {limits.max_cols} columns.
      </p>
    </div>

    <button
      type="button"
      class="btn btn-primary"
      onclick={() => fileInputRef?.click()}
    >
      Browse Files
    </button>

    <div class="safety-pills">
      <span class="pill">✓ Client-side PII screened</span>
      <span class="pill">✓ Previewed before upload</span>
      <span class="pill">✓ Ephemeral RAM only</span>
    </div>
  </div>
</div>

<style>
  .dropzone-card {
    border: 2px dashed var(--border-default);
    background: var(--bg-surface);
    transition: all var(--duration-fast) var(--ease-standard);
    margin: var(--space-4) 0;
  }
  .dropzone-card.dragging {
    border-color: var(--accent);
    background: var(--accent-subtle);
  }
  .file-input-hidden {
    position: absolute;
    width: 1px;
    height: 1px;
    opacity: 0;
    pointer-events: none;
  }
  .dropzone-content {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-3);
    padding: var(--space-6) var(--space-4);
    text-align: center;
  }
  .drop-icon {
    color: var(--accent);
  }
  .drop-title {
    font-size: var(--font-base);
    font-weight: 700;
    color: var(--text-primary);
  }
  .drop-subtitle {
    font-size: var(--font-xs);
    color: var(--text-secondary);
    margin-top: 4px;
  }
  .safety-pills {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }
  .pill {
    font-size: 11px;
    color: var(--text-muted);
    background: var(--bg-subtle);
    padding: 2px 8px;
    border-radius: var(--radius-full);
  }
</style>
