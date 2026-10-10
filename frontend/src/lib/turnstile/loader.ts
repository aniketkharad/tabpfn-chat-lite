import { mockApi } from '../api/mock';

declare global {
  interface Window {
    turnstile?: {
      render: (
        container: string | HTMLElement,
        options: {
          sitekey: string;
          callback: (token: string) => void;
          'error-callback'?: () => void;
        }
      ) => string;
      reset: (widgetId: string) => void;
      remove: (widgetId: string) => void;
    };
  }
}

let turnstileLoadedPromise: Promise<void> | null = null;

/**
 * Lazily loads the Cloudflare Turnstile script ONLY when the user initiates Live mode.
 * In Mock Mode, resolves immediately with a synthetic token without loading external scripts.
 */
export async function getTurnstileToken(containerId: string, siteKey = '0x4AAAAAAAxMockSiteKey'): Promise<string> {
  if (mockApi.isMockActive) {
    // Zero external network calls in mock mode
    return 'mock_turnstile_token_' + Math.random().toString(36).substring(2, 9);
  }

  // Load Cloudflare Turnstile script lazily
  if (!turnstileLoadedPromise) {
    turnstileLoadedPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';
      script.async = true;
      script.defer = true;
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Failed to load Turnstile anti-bot script'));
      document.head.appendChild(script);
    });
  }

  await turnstileLoadedPromise;

  return new Promise((resolve, reject) => {
    if (!window.turnstile) {
      reject(new Error('Turnstile API object unavailable on window'));
      return;
    }

    const container = document.getElementById(containerId);
    if (!container) {
      reject(new Error(`Container element #${containerId} not found for Turnstile widget`));
      return;
    }

    window.turnstile.render(container, {
      sitekey: siteKey,
      callback: (token: string) => {
        resolve(token);
      },
      'error-callback': () => {
        reject(new Error('Turnstile verification failed or was dismissed'));
      },
    });
  });
}
