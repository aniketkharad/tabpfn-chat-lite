<script lang="ts">
  import type { ResultBlock as BlockType } from '../types/contract';
  import MetricCard from './MetricCard.svelte';
  import DataTable from './DataTable.svelte';
  import LazyChart from './LazyChart.svelte';
  import { parseMarkdown } from '../lib/utils/markdown';
  import { formatBytes } from '../lib/utils/formatters';

  let { block }: { block: BlockType } = $props();

  function triggerDownload(content: string, filename: string, format: string): void {
    const mime = format === 'json' ? 'application/json' : 'text/csv';
    const blob = new Blob([content], { type: `${mime};charset=utf-8;` });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }
</script>

{#if block.type === 'metric'}
  <MetricCard metric={block} />
{:else if block.type === 'table'}
  <DataTable table={block.table} title={block.title} description={block.description} />
{:else if block.type === 'chart'}
  <LazyChart kind={block.kind} title={block.title} description={block.description} data={block.data} />
{:else if block.type === 'text'}
  <div class="result-text-block">
    {#if block.title}
      <h4 class="text-block-title">{block.title}</h4>
    {/if}
    <div class="text-content">
      {#each parseMarkdown(block.content) as b}
        {#if b.type === 'paragraph'}
          <p class="paragraph">
            {#each b.inlines || [] as token}
              {#if token.type === 'strong'}
                <strong>{token.value}</strong>
              {:else if token.type === 'em'}
                <em>{token.value}</em>
              {:else if token.type === 'code'}
                <code>{token.value}</code>
              {:else}
                <span>{token.value}</span>
              {/if}
            {/each}
          </p>
        {:else if b.type === 'list'}
          <ul class="list">
            {#each b.items || [] as item}
              <li>
                {#each item as token}
                  {#if token.type === 'strong'}
                    <strong>{token.value}</strong>
                  {:else if token.type === 'em'}
                    <em>{token.value}</em>
                  {:else if token.type === 'code'}
                    <code>{token.value}</code>
                  {:else}
                    <span>{token.value}</span>
                  {/if}
                {/each}
              </li>
            {/each}
          </ul>
        {:else if b.type === 'codeblock'}
          <pre class="codeblock"><code>{b.code}</code></pre>
        {/if}
      {/each}
    </div>
  </div>
{:else if block.type === 'download'}
  <div class="download-block">
    <div class="download-info">
      <div class="download-name">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
          <polyline points="14 2 14 8 20 8"></polyline>
          <line x1="16" y1="13" x2="8" y2="13"></line>
          <line x1="16" y1="17" x2="8" y2="17"></line>
        </svg>
        <span>{block.filename}</span>
      </div>
      {#if block.description}
        <p class="download-desc">{block.description}</p>
      {/if}
      {#if block.size_bytes}
        <span class="download-size tabular-nums">{formatBytes(block.size_bytes)}</span>
      {/if}
    </div>

    <button
      type="button"
      class="btn btn-primary"
      onclick={() => triggerDownload(block.content, block.filename, block.format)}
    >
      Download {block.format.toUpperCase()}
    </button>
  </div>
{/if}

<style>
  .result-text-block {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    margin: var(--space-3) 0;
  }
  .text-block-title {
    font-size: var(--font-sm);
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: var(--space-2);
  }
  .paragraph {
    font-size: var(--font-sm);
    color: var(--text-secondary);
    line-height: var(--leading-relaxed);
    margin-bottom: var(--space-2);
  }
  .list {
    margin-left: var(--space-6);
    font-size: var(--font-sm);
    color: var(--text-secondary);
    line-height: var(--leading-normal);
    margin-bottom: var(--space-2);
  }
  code {
    background: var(--bg-subtle);
    padding: 2px 4px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: var(--font-xs);
  }
  .download-block {
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-md);
    padding: var(--space-4);
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    margin: var(--space-3) 0;
  }
  .download-name {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-sm);
    font-weight: 600;
    color: var(--text-primary);
  }
  .download-desc {
    font-size: var(--font-xs);
    color: var(--text-secondary);
    margin-top: 2px;
  }
  .download-size {
    font-size: var(--font-xs);
    color: var(--text-muted);
  }
</style>
