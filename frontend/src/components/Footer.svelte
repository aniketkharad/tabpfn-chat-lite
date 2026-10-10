<script lang="ts">
  let {
    onDeleteData,
    onDownloadLog,
    isDeleting = false,
  }: {
    onDeleteData: () => void;
    onDownloadLog?: () => void;
    isDeleting?: boolean;
  } = $props();
</script>

<footer class="app-footer">
  <div class="footer-inner container">
    <div class="privacy-box card">
      <div class="privacy-header">
        <div class="privacy-title-group">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="shield-icon" aria-hidden="true">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path>
          </svg>
          <h4 class="privacy-heading">Privacy & Data Notice: Strict Minimization Architecture</h4>
        </div>

        <div class="footer-actions">
          {#if onDownloadLog}
            <button
              type="button"
              class="btn btn-secondary btn-sm"
              onclick={onDownloadLog}
              aria-label="Download cryptographically verifiable session audit log"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="7 10 12 15 17 10"></polyline>
                <line x1="12" y1="15" x2="12" y2="3"></line>
              </svg>
              <span>Download Session Log</span>
            </button>
          {/if}

          <button
            type="button"
            class="btn btn-danger btn-sm"
            disabled={isDeleting}
            onclick={onDeleteData}
            aria-label="Immediately purge all session records and delete my data"
          >
            {#if isDeleting}
              <span>Purging RAM...</span>
            {:else}
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
                <polyline points="3 6 5 6 21 6"></polyline>
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
              </svg>
              <span>Delete My Data</span>
            {/if}
          </button>
        </div>
      </div>

      <div class="privacy-text-content">
        <p class="privacy-summary">
          <strong>Privacy & Data Notice</strong>: Your data is handled with strict minimization.
        </p>

        <ul class="privacy-bullet-list">
          <li>
            <strong>Google Gemini</strong>: Receives only column names, summary statistics, and up to 5 sanitized preview samples to clarify goals and draft plans. Your full dataset is never sent to Google.
          </li>
          <li>
            <strong>Prior Labs TabPFN API</strong>: Receives only the numerical and categorical rows required to fit models and generate predictions. Transmitted securely over encrypted TLS.
          </li>
          <li>
            <strong>Zero Permanent Storage</strong>: All uploaded rows and chat history are held in ephemeral container memory only. No data is stored on disk or saved beyond your session TTL (24 hours).
          </li>
          <li>
            <strong>Delete Anytime</strong>: Click <strong>[Delete My Data]</strong> in the top navigation or footer at any point to immediately purge all session records and destroy your session cookie.
          </li>
          <li>
            <strong>PII Screening</strong>: Files containing detected emails, phone numbers, or credit card numbers are refused automatically.
          </li>
        </ul>
      </div>
    </div>

    <div class="footer-meta">
      <span class="meta-item">TabPFN-3.5 Prior-Data Fitted Inference</span>
      <span class="meta-separator">•</span>
      <span class="meta-item">Ephemeral In-Memory Only</span>
      <span class="meta-separator">•</span>
      <span class="meta-item">Open-Source Contract Verified</span>
    </div>
  </div>
</footer>

<style>
  .app-footer {
    margin-top: auto;
    border-top: 1px solid var(--border-subtle);
    background: var(--bg-surface);
    padding: var(--space-6) 0 var(--space-8);
  }
  .footer-inner {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
  }
  .privacy-box {
    background: var(--bg-subtle);
    border-color: var(--border-subtle);
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .privacy-header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-3);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--border-subtle);
  }
  .privacy-title-group {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  .shield-icon {
    color: var(--accent);
  }
  .privacy-heading {
    font-size: var(--font-sm);
    font-weight: 700;
    color: var(--text-primary);
  }
  .privacy-text-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-size: var(--font-xs);
    color: var(--text-secondary);
    line-height: var(--leading-relaxed);
  }
  .privacy-summary {
    font-size: var(--font-xs);
    color: var(--text-primary);
  }
  .privacy-bullet-list {
    margin-left: var(--space-4);
    display: flex;
    flex-direction: column;
    gap: 6px;
  }
  .footer-meta {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    align-items: center;
    gap: var(--space-2);
    font-size: 11px;
    color: var(--text-muted);
  }
  .meta-separator {
    opacity: 0.5;
  }
  .footer-actions {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
  .btn-sm {
    padding: 4px var(--space-3);
    font-size: var(--font-xs);
  }
</style>
