# TabPFN Chat Lite (`tabpfn-chat-lite`)

A lightweight, local-first web application for fast conversational tabular AI powered by **Prior Labs' TabPFN Foundation Model** and **Gemini** structured planning. Upload small tabular datasets, inspect pre-screened tables, converse to clarify modeling goals, confirm strict execution plans with upfront token estimates, and stream verified predictions, baseline comparisons, and hand-rolled SVG visualizations.

- **Instant Demo Mode**: Operates entirely offline in the browser with zero backend and zero API quota required.
- **Privacy & Grounding Invariants**: Full tables are never sent to the LLM—only column names, types, summary statistics, and up to 3 sanitized samples. Numeric outputs and charts originate purely from deterministic code.
- **Strict Size & Performance Budgets**: Initial payload $\le 50.0\text{ KB}$ gzipped, zero runtime dependencies, 60 fps under 4x CPU throttle, and 0 layout shifts.

---

## 📸 Product Tour

### 1. Instant Landing (Desktop & 360px Mobile)
Zero-configuration front door featuring 1-click sample datasets (Classification, Regression, Forecasting) or custom CSV upload.

| Desktop (1280px) | Mobile (360px) |
| :---: | :---: |
| ![Landing Desktop](docs/screenshots/landing_desktop.png) | ![Landing Mobile](docs/screenshots/landing_mobile_360.png) |

---

### 2. Pre-Screened Table Viewer & Conversational Goal Setting
Local-first RFC 4180 parsing with client- and server-side PII screening (rejecting phone numbers, emails, SSNs, credit cards). Users inspect columns and summary distributions before any modeling begins.

![Table Preview](docs/screenshots/table_preview.png)

---

### 3. Contract-Verified Plan & Upfront Resource Estimates
Before executing any prediction, Gemini emits a structured `Plan` strictly validated against `contract/schemas/plan.json`. The user is presented with target columns, extracted feature sets, and pre-computed token/quota estimates.

![Chat Plan](docs/screenshots/chat_plan.png)

---

### 4. Deterministic Results, Calibrated Intervals & Visualizations
Results stream progressively over Server-Sent Events (SSE). Numeric metrics compare against naive baselines (e.g. majority-class or mean), accompanied by accessible, color-blind safe SVG charts with accessible data table disclosures.

![Result Classification](docs/screenshots/result_classification.png)

---

## ⚡ Measured Benchmarks & Budgets

All metrics are deterministically measured in `docs/PERF.md` and verified in CI via `make verify`:

| Metric | Target / Budget | Measured Result | Status | Notes |
| :--- | :--- | :--- | :---: | :--- |
| **Initial JS + CSS** | $\le 50.0\text{ KB}$ gzipped | **39.97 KB** | ✅ PASS | 20.1% headroom under budget |
| **Lazy Hand-Rolled Chart Kit** | $\le 15.0\text{ KB}$ gzipped | **12.22 KB** | ✅ PASS | 6 SVG chart types, 0 chart libraries |
| **Edge Worker Gateway** | $\le 100.0\text{ KB}$ gzipped | **13.71 KB** | ✅ PASS | Cloudflare Worker + Durable Object |
| **Docker Image Filesystem** | $\le 400.0\text{ MB}$ uncompressed | **360 MB** | ✅ PASS | Multi-stage uv build on python:3.12-slim |
| **Docker Registry Download** | N/A | **97.18 MB** | ✅ PASS | Highly compressed distribution size |
| **Container Idle RSS** | $\le 200.0\text{ MB}$ | **68.59 MiB** | ✅ PASS | Single process uvicorn |
| **Container Cold Start** | $\le 3.0\text{ s}$ | **620.55 ms** | ✅ PASS | Sub-second ready latency to /health |
| **Cumulative Layout Shift (CLS)** | $0.000$ | **0.001** | ✅ PASS | Native system font stack, 0 FOUT/FOIT |
| **Compositor FPS (4x CPU Throttle)** | $\ge 58.0\text{ fps}$ | **60.5 fps** | ✅ PASS | Animates GPU `transform` & `opacity` only |
| **WCAG Contrast Ratios** | $\ge 4.5:1$ (AA) | **Min 4.51:1** | ✅ PASS | All tokens meet WCAG AA & AAA |
| **prefers-reduced-motion** | $0\text{ ms}$ duration | **0.01 ms** | ✅ PASS | Transitions collapse instantly |
| **Automated Test Suite** | 100% green | **154 / 154** | ✅ PASS | 132 pytest + 22 vitest |

---

## 🎬 2–3 Minute Demo Script

Follow this script to deliver a concise, complete demonstration of `tabpfn-chat-lite`:

1. **Minute 0:00 – 0:30: The Front Door & Demo Mode**
   - *"Welcome to TabPFN Chat Lite. This is a lightweight, zero-cookie-tracking public web app for tabular analysis. Notice how fast it loaded: initial JS+CSS is under 40 KB gzipped with zero external libraries."*
   - Click the **California Housing** sample card. Show that all 11 OpenAPI endpoints operate client-side in instant Demo Mode with zero backend calls or cloud quota required.
2. **Minute 0:30 – 1:15: Uploading Data & Privacy Minimization**
   - Click **New Session** -> **Use My Own CSV File**. Upload a test dataset (e.g. `demos/01-churn/churn_sample.csv`).
   - Highlight the **Table Viewer**: *"Before any data leaves the browser, our client and server perform automated PII screening. Emails, phone numbers, and card numbers are refused immediately."*
   - Point out the footer: *"Our architecture enforces strict data minimization: Google Gemini only receives column names, summary statistics, and up to 3 sanitized samples—never your full table. TabPFN receives only the feature rows needed to fit models."*
3. **Minute 1:15 – 2:00: Conversational Plan & Deterministic Execution**
   - Type in chat: *"Predict whether a customer churns based on their balance and age."*
   - Show Gemini formulating the `Plan`: *"Notice how Gemini doesn't execute anything yet—it compiles our goal into a formal contract (`Plan`) with an upfront TabPFN token estimate (10,000 tokens)."*
   - Click **Confirm Plan**. Watch the live Server-Sent Events (SSE) stream progress: `fitting` -> holdout metrics -> accessible SVG charts -> grounded narration.
   - Emphasize grounding: *"The numbers you see did not come from an LLM. All metrics and charts come purely from deterministic Python code; our narrator guard audits the narrative to guarantee zero hallucinations."*
4. **Minute 2:00 – 2:30: Verification & Data Purge**
   - Click **Download Session Log** to show the SHA-256 cryptographic hash chain verifying event continuity.
   - Click **Delete My Data** in the top navigation. Show that all session records in RAM are flushed instantly and the session cookie is destroyed.

---

## ⚠️ Known Limits & Operational Constraints

`tabpfn-chat-lite` is engineered for ultra-lightweight, zero-cost operation on public free tiers. The following operational constraints apply:

1. **Free-Tier Upstream Data Terms**:
   - **Google Gemini Free Tier**: Under Google's AI Studio free terms, prompts may be evaluated for product improvement. To protect user privacy, our backend **never sends raw tabular datasets to Google**—only column names, data types, summary statistics, and up to 3 sanitized preview samples ($\le 64$ characters).
   - **Prior Labs TabPFN Free Tier**: TabPFN receives only the numeric/categorical rows required for the approved split. Transmitted over encrypted TLS directly to `api.priorlabs.ai`.
2. **Strict PII Prohibition**:
   - The application is designed strictly for numerical and categorical analytics, not personal records. Uploaded datasets containing detected email addresses, phone numbers, SSNs, Aadhaar numbers, or credit card numbers are refused client-side and server-side with code `pii_detected`.
3. **Sleeping Backend (Cold Starts)**:
   - On Render Free Web Service, compute containers automatically spin down after 15 minutes of inactivity. The first visitor to wake a sleeping backend experiences a cold start of 30–50 seconds. During this window, the Edge Gateway displays a friendly `backend_waking` notice and offers instant zero-backend **Demo Mode** fallback.
4. **Single-Instance Deployment (`--max-instances 1`)**:
   - The backend runs as a single worker process with in-memory session state (`MemoryStore`) and strict FIFO queueing. This prevents API quota thrashing and keeps memory consumption well within the 200 MB idle / 400 MB peak budget.
5. **Daily Quota Pools**:
   - **Gemini Free Pool**: 20 requests per day (RPD) and 15 requests per minute (RPM).
   - **TabPFN Free Pool**: 5,000,000 tokens per day (~500 standard analyses per day).
   - When daily pools are exhausted, the app cleanly falls back to zero-quota Demo Mode until 00:00:00 UTC reset.

---

## 🏗️ Architecture & Security Invariants

```text
+------------------------+
|   Browser (Origin)     |  <-- Svelte 5 + TypeScript (strict), 0 UI runtime libs
+-----------+------------+
            | (Cookies stripped at edge; CSRF & Turnstile verified)
            v
+------------------------+
|  Cloudflare Worker     |  <-- Enforces IP-salt daily quotas, body caps, admin kill-switch;
|  Gateway & DO Edge     |      signs backend requests with SHA-256 HMAC (30s skew tolerance)
+-----------+------------+
            | (HMAC Header: X-Gateway-Timestamp, X-Gateway-Signature, X-Session-ID)
            v
+------------------------+
|  FastAPI Backend Host  |  <-- Ephemeral RAM storage (30m TTL), 0 persistent user data;
|  (Render / Cloud Run)  |      upstream gates pace Gemini (12 RPM) & TabPFN tokens;
+-----------+------------+      grounded narrator guard catches floating-point hallucinations
```

1. **Browser talks only to its own origin**: No third-party analytics, no font CDNs, no external scripts (Cloudflare Turnstile excepted in live mode).
2. **Secrets live only on backend and edge**: Worker holds Turnstile secret, IP salt, and HMAC secret. Backend holds TabPFN token, Gemini API key, and HMAC secret. Keys never leak into client bundles, git, or logs.
3. **LLM output is never trusted**: Gemini generates a `Plan` validated against `contract/schemas/plan.json`. The executor verifies schema compliance before running. Tabular numbers come strictly from deterministic code.
4. **Data handling & PII screening**: Gemini receives schema metadata and at most 3 sanitized sample values. Files matching phone numbers, emails, identification numbers, or credit card numbers are refused client- and server-side.
5. **Cryptographic audit logging**: Every session event is recorded in sequence with a SHA-256 hash chain (`prev_hash` $\to$ `hash`), verifiable offline via `src/tabchat/replay.py`.

---

## 🛠️ Quickstart

### Prerequisites
- **Python 3.12** with [uv](https://github.com/astral-sh/uv): `curl -LsSf https://astral.sh/uv/install.sh | sh`
- **Bun**: `curl -fsSL https://bun.sh/install | bash`

### 1. Build and Run Web Application (Demo Mode)
No API keys or cloud accounts needed:
```bash
# Build frontend and copy static demo fixtures
make frontend-build

# Serve locally
cd frontend && bun run preview
```
Open **[http://localhost:4173](http://localhost:4173)** in your browser to explore Customer Churn, California Housing, and Airline Passengers workflows offline.

### 2. Run Full System Verification
Runs OpenAPI schema validation, 132 Python tests, 22 Gateway unit tests, bundle size checks, and secret scans:
```bash
make verify
```

### 3. Measure Performance & Accessibility
Deterministically audits CLS, frame rates on 4x CPU throttle, contrast tokens, focus order, and reduced-motion behavior via headless Chrome CDP:
```bash
uv run python scripts/measure_perf.py
```

### 4. Capture Visual Screenshots
Deterministically renders and captures all capability outputs and README product tour screenshots:
```bash
make screenshots
```

---

## 📄 License

Released under the [Apache License, Version 2.0](LICENSE).
- **TabPFN Foundation Model API**: Subject to Prior Labs terms and model licenses ([Prior Labs](https://priorlabs.ai)).
- **Google Gemini API**: Subject to Google APIs Terms of Service ([ai.google.dev](https://ai.google.dev)).
