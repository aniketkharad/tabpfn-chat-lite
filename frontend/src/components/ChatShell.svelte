<script lang="ts">
  import type { ChatMessage, PipelineStage, Plan, ResultBlock as BlockType } from '../types/contract';
  import { parseMarkdown } from '../lib/utils/markdown';
  import PlanCard from './PlanCard.svelte';
  import ResultBlock from './ResultBlock.svelte';
  import StatusBar from './StatusBar.svelte';

  export interface ExtendedMessage extends ChatMessage {
    blocks?: BlockType[];
  }

  let {
    messages = [],
    isPending = false,
    pipelineStage = null,
    queuePosition = null,
    queueEta = null,
    stageMessage = null,
    onSendMessage,
    onConfirmPlan,
  }: {
    messages: ExtendedMessage[];
    isPending?: boolean;
    pipelineStage?: PipelineStage | null;
    queuePosition?: number | null;
    queueEta?: number | null;
    stageMessage?: string | null;
    onSendMessage: (text: string) => void;
    onConfirmPlan: (plan: Plan) => void;
  } = $props();

  let inputVal = $state('');

  function handleKeyDown(e: KeyboardEvent): void {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submitMessage();
    }
  }

  function submitMessage(): void {
    const trimmed = inputVal.trim();
    if (!trimmed || isPending) return;
    onSendMessage(trimmed);
    inputVal = '';
  }
</script>

<div class="chat-shell card" role="region" aria-label="Analysis Conversation">
  <div class="chat-messages" role="log" aria-live="polite">
    {#each messages as msg (msg.id)}
      <div class="message-row" class:user-row={msg.role === 'user'} class:assistant-row={msg.role === 'assistant'}>
        <div class="message-bubble" class:user-bubble={msg.role === 'user'} class:assistant-bubble={msg.role === 'assistant'}>
          <div class="message-sender">
            {msg.role === 'user' ? 'You' : 'TabPFN Assistant'}
          </div>

          <div class="message-body">
            {#each parseMarkdown(msg.content) as b}
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

          <!-- Embedded Plan Confirmation Card -->
          {#if msg.plan}
            <div class="embedded-plan">
              <PlanCard plan={msg.plan} onConfirm={onConfirmPlan} isExecuting={isPending} />
            </div>
          {/if}

          <!-- Embedded Result Blocks -->
          {#if msg.blocks && msg.blocks.length > 0}
            <div class="embedded-results">
              {#each msg.blocks as block}
                <ResultBlock {block} />
              {/each}
            </div>
          {/if}
        </div>
      </div>
    {/each}

    <!-- Real-time Pipeline Execution Status Bar -->
    {#if isPending && (pipelineStage || queuePosition !== null)}
      <StatusBar
        stage={pipelineStage}
        queuePosition={queuePosition}
        queueEta={queueEta}
        message={stageMessage}
      />
    {/if}
  </div>

  <div class="chat-input-pane">
    <div class="input-wrapper">
      <textarea
        bind:value={inputVal}
        onkeydown={handleKeyDown}
        placeholder="Type your message (e.g. 'Predict customer churn based on tenure') — Enter to send"
        rows="2"
        disabled={isPending}
        class="chat-textarea"
        aria-label="Chat input message"
      ></textarea>

      <button
        type="button"
        class="btn btn-primary send-btn"
        disabled={!inputVal.trim() || isPending}
        onclick={submitMessage}
        aria-label="Send message"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true">
          <line x1="22" y1="2" x2="11" y2="13"></line>
          <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
        </svg>
        <span>Send</span>
      </button>
    </div>
    <span class="input-tip">Press <strong>Enter</strong> to send, <strong>Shift+Enter</strong> for newline</span>
  </div>
</div>

<style>
  .chat-shell {
    display: flex;
    flex-direction: column;
    margin: var(--space-4) 0;
    padding: 0;
    overflow: hidden;
  }
  .chat-messages {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    padding: var(--space-4);
    min-height: 320px;
    background: var(--bg-surface);
  }
  .message-row {
    display: flex;
    width: 100%;
  }
  .user-row {
    justify-content: flex-end;
  }
  .assistant-row {
    justify-content: flex-start;
  }
  .message-bubble {
    max-width: 90%;
    border-radius: var(--radius-lg);
    padding: var(--space-3) var(--space-4);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  .assistant-row .message-bubble {
    width: 100%;
    max-width: 100%;
  }
  @media (min-width: 640px) {
    .user-bubble {
      max-width: 80%;
    }
  }
  .user-bubble {
    background: var(--accent);
    color: var(--accent-contrast);
    border-bottom-right-radius: var(--radius-sm);
  }
  .assistant-bubble {
    background: var(--bg-subtle);
    color: var(--text-primary);
    border: 1px solid var(--border-subtle);
    border-bottom-left-radius: var(--radius-sm);
  }
  .message-sender {
    font-size: 11px;
    font-weight: 600;
    opacity: 0.8;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-bottom: 2px;
  }
  .message-body {
    font-size: var(--font-sm);
    line-height: var(--leading-relaxed);
  }
  .paragraph {
    margin-bottom: var(--space-2);
  }
  .list {
    margin-left: var(--space-4);
    margin-bottom: var(--space-2);
  }
  code {
    background: rgba(0, 0, 0, 0.08);
    padding: 2px 4px;
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: var(--font-xs);
  }
  .user-bubble code {
    background: rgba(255, 255, 255, 0.2);
    color: #ffffff;
  }
  .embedded-plan, .embedded-results {
    margin-top: var(--space-2);
    width: 100%;
  }
  .chat-input-pane {
    padding: var(--space-3) var(--space-4);
    background: var(--bg-surface);
    border-top: 1px solid var(--border-subtle);
  }
  .input-wrapper {
    display: flex;
    gap: var(--space-2);
  }
  .chat-textarea {
    flex-grow: 1;
    font-family: var(--font-sans);
    font-size: var(--font-sm);
    line-height: var(--leading-normal);
    padding: var(--space-2) var(--space-3);
    border-radius: var(--radius-md);
    border: 1px solid var(--border-default);
    background: var(--bg-input);
    color: var(--text-primary);
    resize: none;
    transition: border-color var(--duration-fast) var(--ease-standard);
  }
  .chat-textarea:focus {
    outline: none;
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }
  .send-btn {
    align-self: flex-end;
  }
  .input-tip {
    font-size: 11px;
    color: var(--text-muted);
    margin-top: 4px;
    display: block;
  }
</style>
