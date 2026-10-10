<script lang="ts">
  import { onMount } from 'svelte';
  import type {
    Capability,
    ErrorCode,
    PipelineStage,
    Plan,
    ResultBlock,
    ServiceStatus,
    TableData,
  } from './types/contract';
  import { api, ApiError } from './lib/api/client';
  import { mockApi } from './lib/api/mock';
  import { CAPABILITY_RESULTS } from './lib/api/fixtures';
  import { demoRunner, DEMO_DATASETS, type DemoDatasetInfo } from './lib/demo/runner';
  import Header from './components/Header.svelte';
  import Landing from './components/Landing.svelte';
  import UploadDropZone from './components/UploadDropZone.svelte';
  import DataTable from './components/DataTable.svelte';
  import ChatShell, { type ExtendedMessage } from './components/ChatShell.svelte';
  import ErrorList, { type DisplayError } from './components/ErrorList.svelte';
  import Footer from './components/Footer.svelte';

  // Synchronous URL Parameter Detection for instant zero-CLS rendering
  const initParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
  const initCap = initParams?.get('capability') || initParams?.get('preview');
  const initDemo = initParams?.get('demo');
  const initStep = initParams?.get('step');
  const initMock = initParams?.get('mock') === '1' || initParams?.get('mock') === 'true';

  let initialMode: 'demo' | 'mock' | 'live' = initMock || initCap ? 'mock' : 'demo';
  let initialStepVal: 'landing' | 'upload' | 'view_table' | 'chat' = 'landing';
  let initialTable: TableData | null = null;
  let initialFilename = '';
  let initialCapability: Capability = 'classification';
  let initialMessages: ExtendedMessage[] = [];

  if (initCap && initCap in CAPABILITY_RESULTS) {
    const cap = initCap as Capability;
    initialCapability = cap;
    initialStepVal = 'chat';
    const details = CAPABILITY_RESULTS[cap];
    initialMessages = [
      {
        id: `msg_preview_${cap}`,
        role: 'assistant',
        content: details.summary ?? `Completed ${cap} analysis.`,
        blocks: details.blocks,
        timestamp: Date.now(),
      },
    ];
  } else if (initDemo) {
    const demo = DEMO_DATASETS.find((d) => d.id === initDemo) || DEMO_DATASETS[0];
    initialCapability = demo.capability;
    initialFilename = `${demo.id}_sample.csv`;
    initialTable = demoRunner.getParsedDemoTable(demo.id);
    initialStepVal = (initStep === 'chat_plan' || initStep === 'chat') ? 'chat' : 'view_table';
    initialMessages = [
      {
        id: 'msg_welcome',
        role: 'assistant',
        content: `Loaded sample dataset **${demo.name}** (${initialTable.rows.length} rows, ${initialTable.cols.length} columns). Here is the proposed TabPFN plan to analyze it:`,
        plan: demo.plan,
        timestamp: Date.now(),
      },
    ];
  }

  // Application State Runes
  let mode = $state<'demo' | 'mock' | 'live'>(initialMode);
  let currentStep = $state<'landing' | 'upload' | 'view_table' | 'chat'>(initialStepVal);

  function goToStep(nextStep: 'landing' | 'upload' | 'view_table' | 'chat'): void {
    if (typeof document !== 'undefined' && 'startViewTransition' in document) {
      (document as any).startViewTransition(() => {
        currentStep = nextStep;
      });
    } else {
      currentStep = nextStep;
    }
  }

  let serviceStatus = $state<ServiceStatus | null>(null);
  let isWaking = $state(false);
  let isDeleting = $state(false);

  let activeTable = $state<TableData | null>(initialTable);
  let activeFilename = $state(initialFilename);
  let activeCapability = $state<Capability>(initialCapability);

  let messages = $state<ExtendedMessage[]>(initialMessages);
  let isPending = $state(false);
  let pipelineStage = $state<PipelineStage | null>(null);
  let queuePosition = $state<number | null>(null);
  let queueEta = $state<number | null>(null);
  let stageMessage = $state<string | null>(null);

  let errors = $state<DisplayError[]>([]);

  function addError(code: ErrorCode, message?: string, retry_after_s?: number, request_id?: string): void {
    const newErr: DisplayError = {
      id: `err_${Date.now()}_${Math.random().toString(36).substring(2, 6)}`,
      code,
      message,
      retry_after_s,
      request_id,
    };
    errors = [newErr, ...errors];
  }

  function dismissError(id: string): void {
    errors = errors.filter((e) => e.id !== id);
  }

  function handleDropError(code: ErrorCode, msg: string): void {
    addError(code, msg);
  }

  onMount(async () => {
    // 1. Activate mock API if mock mode or capability preview active
    if (mode === 'mock') {
      mockApi.setMockActive(true);
    }

    // 2. Setup Waking status listener
    api.setWakingCallback((waking) => {
      isWaking = waking;
    });

    // 3. Fire-and-forget backend warm-up request (live mode only)
    if (mode === 'live') {
      api.warmUpBackend();
    }

    // 4. Fetch initial service status & capacity limits (live mode or mock)
    if (mode !== 'demo') {
      try {
        serviceStatus = await api.getStatus();
      } catch {
        // Quiet fallback
      }
    }

    // 5. Attempt session resume after refresh (if active live session exists)
    if (mode === 'live') {
      try {
        const sess = await api.getSession();
        if (sess && sess.session_id) {
          if (sess.dataset_card) {
            activeFilename = 'resumed_dataset.csv';
            const cols = sess.dataset_card.columns.map((c) => c.name);
            const types = sess.dataset_card.columns.map((c) => c.type as any);
            activeTable = {
              cols,
              types,
              rows: sess.dataset_card.preview_rows,
            };
            currentStep = 'view_table';
          }
          if (sess.history && sess.history.length > 0) {
            messages = sess.history.map((h, i) => ({
              id: `msg_resumed_${i}`,
              role: h.role as 'user' | 'assistant',
              content: h.content,
              timestamp: h.timestamp ? new Date(h.timestamp).getTime() : Date.now(),
            }));
            currentStep = 'chat';
          }
          if (sess.results?.blocks) {
            messages = [
              ...messages,
              {
                id: `msg_resumed_results`,
                role: 'assistant',
                content: sess.results.narration || 'Resumed completed analysis results.',
                blocks: sess.results.blocks,
                timestamp: Date.now(),
              },
            ];
            currentStep = 'chat';
          }
        }
      } catch {
        // Silently continue in default state
      }
    }
  });

  // Flow Handlers
  function handleSelectDemo(demo: DemoDatasetInfo): void {
    if (mode !== 'mock') {
      mode = 'demo';
    }
    activeCapability = demo.capability;
    activeFilename = `${demo.id}_sample.csv`;
    activeTable = demoRunner.getParsedDemoTable(demo.id);
    currentStep = 'view_table';

    // Populate initial conversation with welcome and proposed plan
    messages = [
      {
        id: 'msg_welcome',
        role: 'assistant',
        content: `Loaded sample dataset **${demo.name}** (${activeTable.rows.length} rows, ${activeTable.cols.length} columns). Here is the proposed TabPFN plan to analyze it:`,
        plan: demo.plan,
        timestamp: Date.now(),
      },
    ];
  }

  function handleChooseCustomFile(): void {
    if (mode === 'demo') {
      mode = 'live';
    }
    goToStep('upload');
  }

  async function handleParsedUploadTable(table: TableData, filename: string): Promise<void> {
    activeTable = table;
    activeFilename = filename;
    goToStep('view_table');

    if (mode === 'live') {
      try {
        await api.upload(table, filename);
      } catch (err) {
        if (err instanceof ApiError) {
          addError(err.code, err.message, err.retry_after_s, err.request_id);
        } else {
          addError('validation', 'Failed to upload dataset to backend.');
        }
      }
    }

    // Create assistant greeting message
    messages = [
      {
        id: 'msg_greet_upload',
        role: 'assistant',
        content: `I've successfully verified and loaded **${filename}** (${table.rows.length} rows, ${table.cols.length} columns). What analysis would you like to perform? You can ask to predict a target column, forecast forward trends, detect anomalies, or evaluate feature importance.`,
        timestamp: Date.now(),
      },
    ];
  }

  function handleContinueToChat(): void {
    goToStep('chat');
  }

  async function handleSendMessage(text: string): Promise<void> {
    if (isPending) return;

    const userMsg: ExtendedMessage = {
      id: `msg_u_${Date.now()}`,
      role: 'user',
      content: text,
      timestamp: Date.now(),
    };
    messages = [...messages, userMsg];
    isPending = true;

    try {
      const history = messages
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content }));

      const res = await api.chatTurn(text, history, activeTable ?? undefined);

      if (res.plan) {
        activeCapability = res.plan.capability;
      }

      const assistantMsg: ExtendedMessage = {
        id: `msg_a_${Date.now()}`,
        role: 'assistant',
        content: res.message,
        plan: res.plan,
        timestamp: Date.now(),
      };
      messages = [...messages, assistantMsg];
    } catch (err) {
      if (err instanceof ApiError) {
        addError(err.code, err.message, err.retry_after_s, err.request_id);
      } else if (err && typeof err === 'object' && 'error' in err) {
        const e = (err as any).error;
        addError(e.code, e.message, e.retry_after_s, e.request_id);
      } else {
        addError('internal', 'Failed to communicate with conversational planner.');
      }
    } finally {
      isPending = false;
    }
  }

  async function handleConfirmPlan(plan: Plan): Promise<void> {
    if (isPending) return;
    isPending = true;
    pipelineStage = 'planning';
    queuePosition = 1;
    queueEta = 1.0;
    stageMessage = 'Queuing run and verifying JobSpec';

    const accumulatedBlocks: ResultBlock[] = [];
    const runResultMsgId = `msg_res_${Date.now()}`;

    // Add placeholder assistant message that will receive streaming blocks
    const streamMsg: ExtendedMessage = {
      id: runResultMsgId,
      role: 'assistant',
      content: `Executing **${plan.capability}** plan with TabPFN...`,
      blocks: [],
      timestamp: Date.now(),
    };
    messages = [...messages, streamMsg];

    // Robustness: 15-second "still working" progress indicator
    let lastEventTime = Date.now();
    const stillWorkingTimer = setInterval(() => {
      if (isPending && Date.now() - lastEventTime >= 15000) {
        stageMessage = `${stageMessage?.replace(/ — Still working.*/, '') || 'Processing'} — Still working on your analysis (deterministic models running)...`;
      }
    }, 3000);

    try {
      let eventStream: AsyncGenerator<any, void, unknown>;

      if (mode === 'demo') {
        // Run demo mode under <= 2s budget
        eventStream = demoRunner.runDemo(plan.capability);
      } else {
        const runRes = await api.executeRun(plan.plan_id);
        eventStream = api.streamEvents(runRes.run_id, plan.capability);
      }

      for await (const ev of eventStream) {
        lastEventTime = Date.now();
        if (ev.event === 'queued') {
          queuePosition = ev.data.position;
          queueEta = ev.data.eta_s;
        } else if (ev.event === 'status') {
          queuePosition = null;
          pipelineStage = ev.data.stage;
          stageMessage = ev.data.message ?? `Stage: ${ev.data.stage}`;
        } else if (ev.event === 'block') {
          accumulatedBlocks.push(ev.data.block);
          messages = messages.map((m) =>
            m.id === runResultMsgId ? { ...m, blocks: [...accumulatedBlocks] } : m
          );
        } else if (ev.event === 'done') {
          pipelineStage = null;
          stageMessage = null;
          messages = messages.map((m) =>
            m.id === runResultMsgId
              ? { ...m, content: ev.data.summary, blocks: [...accumulatedBlocks] }
              : m
          );
        } else if (ev.event === 'error') {
          const err = ev.data.error;
          addError(err.code, err.message, err.retry_after_s, err.request_id);
          break;
        }
      }
    } catch (err) {
      if (err instanceof ApiError) {
        addError(err.code, err.message, err.retry_after_s, err.request_id);
      } else if (err && typeof err === 'object' && 'error' in err) {
        const e = (err as any).error;
        addError(e.code, e.message, e.retry_after_s, e.request_id);
      } else {
        addError('internal', 'Execution interrupted due to network error.');
      }
    } finally {
      clearInterval(stillWorkingTimer);
      isPending = false;
      pipelineStage = null;
      queuePosition = null;
      stageMessage = null;
    }
  }

  async function handleDownloadLog(): Promise<void> {
    try {
      await api.downloadSessionLog();
    } catch (err: any) {
      if (err instanceof ApiError) {
        addError(err.code, err.message, err.retry_after_s, err.request_id);
      } else {
        addError('internal', `Failed to download session log: ${err?.message || err}`);
      }
    }
  }

  async function handleDeleteData(): Promise<void> {
    isDeleting = true;
    try {
      await api.deleteSession();
    } catch {
      // Ephemeral reset locally regardless of backend state
    } finally {
      isDeleting = false;
      handleResetSession();
    }
  }

  function handleResetSession(): void {
    activeTable = null;
    activeFilename = '';
    messages = [];
    errors = [];
    goToStep('landing');
    isPending = false;
    pipelineStage = null;
    queuePosition = null;
  }

  function handleTriggerMockError(code: ErrorCode | null): void {
    mockApi.setInjectedError(code);
    if (code) {
      try {
        mockApi.getStatus();
      } catch (err) {
        if (err && typeof err === 'object' && 'error' in err) {
          const e = (err as any).error;
          addError(e.code, e.message, e.retry_after_s, e.request_id);
        }
      }
    }
  }
</script>

<Header
  {mode}
  status={serviceStatus}
  {isWaking}
  onReset={handleResetSession}
  onTriggerMockError={handleTriggerMockError}
/>

<main class="container main-content">
  <ErrorList
    {errors}
    onDismiss={dismissError}
    onRetry={() => {
      errors = [];
      if (activeTable) handleContinueToChat();
    }}
  />

  {#if currentStep === 'landing'}
    <Landing
      onSelectDemo={handleSelectDemo}
      onChooseCustomFile={handleChooseCustomFile}
    />
  {:else if currentStep === 'upload'}
    <div class="step-view">
      <div class="step-nav">
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => goToStep('landing')}>
          ← Back to Samples
        </button>
        <span class="step-title">Step 1: Upload Tabular Dataset</span>
      </div>

      <UploadDropZone
        status={serviceStatus}
        onParsedTable={handleParsedUploadTable}
        onError={handleDropError}
      />
    </div>
  {:else if currentStep === 'view_table' && activeTable}
    <div class="step-view">
      <div class="step-nav">
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => goToStep('landing')}>
          ← Change Dataset
        </button>
        <span class="step-title">Step 2: Table Viewer ({activeFilename})</span>
      </div>

      <DataTable
        table={activeTable}
        title={activeFilename}
        description="Local pre-screened table preview. Ready for conversational goal setting."
        filename={activeFilename}
      />

      <div class="step-action-bar">
        <button
          type="button"
          class="btn btn-primary btn-lg"
          onclick={handleContinueToChat}
        >
          <span>Continue to Chat & Analysis</span>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
            <line x1="5" y1="12" x2="19" y2="12"></line>
            <polyline points="12 5 19 12 12 19"></polyline>
          </svg>
        </button>
      </div>
    </div>
  {:else if currentStep === 'chat'}
    <div class="step-view">
      <div class="step-nav">
        <button type="button" class="btn btn-ghost btn-sm" onclick={() => goToStep('view_table')}>
          ← View Table Data
        </button>
        <span class="step-title">Step 3: Goal Clarification & Results ({activeFilename})</span>
      </div>

      <ChatShell
        {messages}
        {isPending}
        {pipelineStage}
        {queuePosition}
        {queueEta}
        {stageMessage}
        onSendMessage={handleSendMessage}
        onConfirmPlan={handleConfirmPlan}
      />
    </div>
  {/if}
</main>

<Footer
  onDeleteData={handleDeleteData}
  onDownloadLog={handleDownloadLog}
  {isDeleting}
/>

<style>
  .main-content {
    flex-grow: 1;
    padding-top: var(--space-4);
    padding-bottom: var(--space-6);
  }
  .step-view {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }
  .step-nav {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
    padding-bottom: var(--space-2);
    border-bottom: 1px solid var(--border-subtle);
  }
  .step-title {
    font-size: var(--font-sm);
    font-weight: 600;
    color: var(--text-secondary);
  }
  .step-action-bar {
    display: flex;
    justify-content: flex-end;
    margin-top: var(--space-2);
  }
  .btn-lg {
    padding: var(--space-3) var(--space-6);
    font-size: var(--font-base);
  }
  .btn-sm {
    padding: 4px var(--space-3);
    font-size: var(--font-xs);
  }
</style>
