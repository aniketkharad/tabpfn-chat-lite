<script lang="ts">
  import { DEMO_DATASETS, type DemoDatasetInfo } from '../lib/demo/runner';

  let {
    onSelectDemo,
    onChooseCustomFile,
  }: {
    onSelectDemo: (demo: DemoDatasetInfo) => void;
    onChooseCustomFile: () => void;
  } = $props();

  // Helper metadata tags for quick inspection on cards
  const DEMO_META: Record<string, { rows: string; metric: string }> = {
    churn: { rows: '140 rows', metric: 'Accuracy / ROC AUC' },
    housing: { rows: '100 rows', metric: 'RMSE / Quantiles' },
    air: { rows: '144 rows', metric: '12-mo Forecast' },
  };
</script>

<div class="landing-hero animate-enter" role="region" aria-label="Dataset Selection and Demo Modes">
  <div class="hero-intro">
    <div class="hero-pill-badge">
      <span class="pill-dot"></span>
      <span class="pill-text">TabPFN Foundation Model • Gemini Planning</span>
    </div>

    <h1 class="hero-title">Instant Tabular AI, Powered by TabPFN</h1>
    <p class="hero-subtitle">
      Zero training, deterministic in-context inference, and guided planning.
      Explore pre-recorded workflows in instant Demo Mode, or analyze your own CSV.
    </p>
  </div>

  <div class="demo-grid" role="list" aria-label="Demo Workflows">
    {#each DEMO_DATASETS as demo (demo.id)}
      {@const meta = DEMO_META[demo.id] || { rows: 'Sample', metric: 'Metrics' }}
      <div class="demo-card card" role="listitem">
        <div class="card-top">
          <div class="card-badge-row">
            <span class="badge badge-accent">{demo.badge}</span>
            <span class="meta-chip tabular-nums">{meta.rows}</span>
          </div>

          <h2 class="demo-card-title">{demo.name}</h2>
          <p class="demo-card-desc">{demo.description}</p>
        </div>

        <div class="card-bottom">
          <div class="card-meta-row">
            <span class="meta-label">Output:</span>
            <span class="meta-value">{meta.metric}</span>
          </div>

          <button
            type="button"
            class="btn btn-primary demo-action-btn"
            onclick={() => onSelectDemo(demo)}
            aria-label={`Explore ${demo.name} in instant Demo Mode`}
          >
            <span>Explore Demo</span>
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
              <polygon points="5 3 19 12 5 21 5 3"></polygon>
            </svg>
          </button>
        </div>
      </div>
    {/each}
  </div>

  <div class="custom-file-divider" aria-hidden="true">
    <div class="divider-line"></div>
    <span class="divider-text">OR</span>
    <div class="divider-line"></div>
  </div>

  <div class="custom-action-container">
    <button
      type="button"
      class="btn btn-secondary btn-upload-cta"
      onclick={onChooseCustomFile}
      aria-label="Upload custom CSV table"
    >
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
        <polyline points="17 8 12 3 7 8"></polyline>
        <line x1="12" y1="3" x2="12" y2="15"></line>
      </svg>
      <span>Use My Own CSV File</span>
    </button>
    <p class="custom-note">Max 200 rows × 50 cols • Ephemeral in RAM • Zero persistent data</p>
  </div>
</div>

<style>
  .landing-hero {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-6);
    padding: var(--space-4) 0 var(--space-8);
    text-align: center;
    width: 100%;
  }

  .hero-intro {
    max-width: 640px;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
  }

  .hero-pill-badge {
    display: inline-flex;
    align-items: center;
    gap: var(--space-2);
    padding: 3px var(--space-3);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-full);
    box-shadow: var(--shadow-xs);
    margin-bottom: var(--space-2);
  }

  .pill-dot {
    width: 6px;
    height: 6px;
    border-radius: var(--radius-full);
    background-color: var(--accent);
  }

  .pill-text {
    font-size: var(--font-xs);
    font-weight: 600;
    color: var(--text-secondary);
    letter-spacing: 0.02em;
  }

  .hero-title {
    font-size: clamp(1.4rem, 4.5vw, 2.1rem);
    font-weight: 800;
    color: var(--text-primary);
    line-height: var(--leading-tight);
    letter-spacing: -0.025em;
  }

  .hero-subtitle {
    font-size: var(--font-sm);
    color: var(--text-secondary);
    line-height: var(--leading-relaxed);
    max-width: 580px;
    margin-top: 2px;
  }

  @media (max-width: 480px) {
    .hero-title {
      font-size: 1.45rem;
    }
    .hero-subtitle {
      font-size: var(--font-xs);
    }
    .pill-text {
      font-size: 11px;
    }
    .hero-pill-badge {
      padding: 2px var(--space-2);
    }
  }

  /* Demo Grid: 1 col on 360px mobile, 3 cols on desktop */
  .demo-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: var(--space-4);
    width: 100%;
    margin-top: var(--space-1);
    text-align: left;
  }

  @media (min-width: 680px) {
    .demo-grid {
      grid-template-columns: repeat(3, 1fr);
    }
  }

  .demo-card {
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    gap: var(--space-4);
    background: var(--bg-surface);
    border: 1px solid var(--border-subtle);
    border-radius: var(--radius-lg);
    padding: var(--space-4);
    box-shadow: var(--shadow-xs);
    transition: transform var(--duration-fast) var(--ease-standard),
                box-shadow var(--duration-fast) var(--ease-standard),
                border-color var(--duration-fast) var(--ease-standard);
  }

  .demo-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-md);
    border-color: var(--border-default);
  }

  .card-top {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  .card-badge-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .meta-chip {
    font-size: var(--font-xs);
    font-weight: 500;
    color: var(--text-muted);
    background: var(--bg-subtle);
    padding: 1px var(--space-2);
    border-radius: var(--radius-sm);
  }

  .demo-card-title {
    font-size: var(--font-base);
    font-weight: 700;
    color: var(--text-primary);
    line-height: var(--leading-tight);
    margin-top: 2px;
  }

  .demo-card-desc {
    font-size: var(--font-xs);
    color: var(--text-secondary);
    line-height: var(--leading-normal);
  }

  .card-bottom {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding-top: var(--space-2);
    border-top: 1px solid var(--border-subtle);
  }

  .card-meta-row {
    display: flex;
    align-items: baseline;
    gap: var(--space-1);
    font-size: var(--font-xs);
  }

  .meta-label {
    color: var(--text-muted);
  }

  .meta-value {
    color: var(--text-secondary);
    font-weight: 500;
  }

  .demo-action-btn {
    width: 100%;
    min-height: 42px;
  }

  /* Divider */
  .custom-file-divider {
    display: flex;
    align-items: center;
    width: 100%;
    max-width: 380px;
    gap: var(--space-3);
    margin: var(--space-2) 0;
  }

  .divider-line {
    flex-grow: 1;
    height: 1px;
    background: var(--border-subtle);
  }

  .divider-text {
    font-size: var(--font-xs);
    font-weight: 700;
    color: var(--text-muted);
    letter-spacing: 0.08em;
  }

  /* Upload Action */
  .custom-action-container {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--space-2);
    width: 100%;
    max-width: 380px;
  }

  .btn-upload-cta {
    width: 100%;
    min-height: 46px;
    font-size: var(--font-sm);
    font-weight: 600;
    box-shadow: var(--shadow-xs);
  }

  .btn-upload-cta:hover {
    box-shadow: var(--shadow-sm);
  }

  .custom-note {
    font-size: var(--font-xs);
    color: var(--text-muted);
    line-height: var(--leading-normal);
  }
</style>
