# K-NEXUS — FlowSense × TrustGraph Interactive Web Prototype

[![Live Demo](https://img.shields.io/badge/Render-Live_Demo-00C7B7?style=for-the-badge&logo=render&logoColor=white)](https://k-nexus-app.onrender.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-4.0.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-1.30-005CED?style=for-the-badge&logo=onnx&logoColor=white)](https://onnxruntime.ai)
[![License](https://img.shields.io/badge/Status-Independent_Prototype-green?style=for-the-badge)](#disclaimer--prototype-boundaries)

An independent interactive UX prototype demonstrating two next-generation financial AI capabilities designed for modern mobile banking experiences (inspired by K+ / MAKE by KBank):

1. **FlowSense**: daily spending guidance, a budget simulator, 30-day cashflow forecasting, and surplus-only simulated micro-savings (Micro-Sweep).
2. **TrustGraph**: Pre-transfer mule account interdiction and transaction fraud intelligence with an explainable AI (XAI) risk panel and simulated step-up micro-authentication.

Built with a responsive mobile/desktop interface and isolated visitor sessions. Financial data and transfers are synthetic; this is not a production banking service.

Users can preview and confirm their own planning reserve, with consistent effects on daily spending, savings capacity and transfer review. The liquidity guide explains reducing future spending, withdrawing existing savings and saving only surplus. See [reserve behavior and liquidity UX](docs/liquidity-reserve.md) for rules, limitations and verification.

The home screen keeps its illustrated hero and offers an eight-step spotlight tutorial with arrows, explanations, back/next controls and optional replay. It introduces budgeting, reserves, recipient checks and savings without confirming transfers or moving money. See [the tutorial walkthrough](docs/try-first-demo.md) for behavior and review notes.

---

##  Live Demo & Endpoints

- **Live Web Application:** [https://k-nexus-app.onrender.com](https://k-nexus-app.onrender.com)
- **API Health Check:** [https://k-nexus-app.onrender.com/api/v2/health](https://k-nexus-app.onrender.com/api/v2/health)

> [!TIP]
> Availability and startup time depend on the hosting plan and service state. The health endpoint reports current readiness; this project does not guarantee continuous uptime or a fixed load time.

---

##  Key Capabilities

The current interface follows the user-supplied K+ visual reference: a teal home/transaction/profile shell, circular actions, geometric account cards and light task sheets. The daily plan is promoted in home important items and linked from Transactions and Profile; [the Thai placement plan](docs/KPLUS_FEATURE_PLACEMENT_TH.md) separates this working prototype from a proposed real K+ integration. All balances remain synthetic.

### 1. FlowSense — Liquidity Forecasting & Smart Micro-Sweep
- **30-Day Liquidity Forecast:** High-resolution balance and cash flow projection across 30 future days, today, and 7 synthetic historical days powered by ONNX inference (`flowsense.onnx`).
- **Daily Spending Plan:** The home screen highlights how much more can be spent today, the total daily allowance, and spending already posted. The allowance reserves known bills and an emergency buffer until payday. It is a transparent calculation, separate from model-predicted spending.
- **Budget Simulator:** Try a daily budget and see the projected balance before payday, reserve shortfall, and bill risk without changing account balances.
- **Status Horizon:** Calendar-aware bill-risk checks and a model-based 30-day balance projection. These are prototype estimates, not verified financial recommendations.
- **Normal-Dip Suppression:** Intelligent alert gating that suppresses noise during routine balance drops, alerting only when upcoming fixed obligations (rent, bills, debt) are projected to be at risk.
- **Optional Savings:** Off by default, enabled per visitor/persona. Enabling never moves money; each saving action is explicitly requested. Every sweep reserves living costs, all profile bills and an emergency buffer of at least THB 500, with the existing forecast-minimum guard applied as an additional check. Each sweep is limited to the available capacity and THB 500.
- **Standard Savings Withdrawals:** Withdraw an explicit positive amount or select the full savings balance, including while new saving is disabled. No Undo, scheduled saving, interest accrual or real bank transaction is implemented. See [the source-sync notes](docs/savings-sync-2026-10-16.md).

### 2. TrustGraph — Pre-Transfer Fraud & Mule Interdiction
- **Plan Before Transfer:** Every evaluation previews without debiting, including routine transfers. The review shows remaining average daily allocation before/after the transfer, outstanding bills, emergency reserve and any reserve shortfall. A separate explicit confirmation is required; routine transfers have no simulated authentication or timed pause.
- **Match a Reserved Bill:** Users explicitly match a full or partial payment to an unpaid bill before payday. Only a successful transfer records the payment, reducing remaining reserves in the daily plan, savings capacity and forecast without counting the bill as discretionary spending. Matching a bill never changes the fraud score or verifies a recipient.
- **Context and Sequence:** Job/task payments, requests to pay more to withdraw funds, and changed recipient accounts receive tailored verification guidance. Reviews show successful transfers to the same recipient today in the demo session. These are decision aids, not validated scam detection outcomes. See [implementation and validation notes](docs/transfer-planning.md).
- **Fresh Plan at Confirmation:** Confirmation checks the server-side plan snapshot and refuses a stale balance, bill allocation or calendar date until the user reviews again. Separate signed review and simulated-auth token purposes prevent routine review tokens from authorizing risky transfers.
- **Risk Scoring with Precomputed Graph Features:** ONNX inference uses saved graph embeddings and synthetic account/behavioral features. It does not build a live banking graph.
- **Explainable AI (XAI) Risk Factors:** Human-readable risk explanations (e.g., dormant account reactivated, sudden deviation from historical averages, recipient velocity surge).
- **Risky Transfer Review Period:** Enabled by default: a 15-minute server-enforced pause only for risky transfers, with reasons and verification guidance. A visible settings card controls the optional pause for new risky transfers. Existing active reviews retain their policy, while cancellation ends that transaction and its timer; the next request uses current settings. Risk evaluation, simulated authentication and blocked destinations remain enforced. Results open in an accessible modal instead of scrolling the page. Reload restores the pending review within the in-memory visitor session. Time elapsed never automatically sends money or certifies safety. See [cooldown policy and verification](docs/transfer-cooldown.md).
- **Bank Contact from Risk Warnings:** Risky and blocked transfer dialogs keep a contact action visible alongside cancellation where available. It opens official KBank contact information within the existing dialog, without cancelling, resetting the review timer, approving the recipient or transmitting transaction data. The phone link opens a real dialer; this prototype does not connect to bank staff or simulate a completed consultation. K-Contact Center 02-888-8888, 24-hour service and fraud information menu 00 were checked against [KBank's official contact page](https://www.kasikornbank.com/th/contact/pages/k-contact-center.aspx) on 17 October 2026. Recheck the official page before changing these details.
- **Simulated Micro-Auth (5s Step-Up):** A simulated 5-second facial liveness verification gate that generates a cryptographically signed clearance token (HMAC-SHA256, 120s TTL) binding source, recipient, amount, and visitor session.
- **Blocked Mule Interdiction:** Immediate transfer prevention for known or flagged mule accounts before debit execution.
- **Downloadable E-Slip:** Generates plain-text demo receipts with unique demo transaction references.

### 3. Behavioral Personas & Interactive Data Lab
- **3 Synthetic Personas:** Switch between realistic financial profiles with distinct income rhythms:
  - **May (Early Career):** Stable entry-level salary, predictable living expenses.
  - **Non (Multiple Commitments):** A demo profile with several expense obligations.
  - **Praew (Reserve Builder):** A demo profile focused on financial reserves.
- **SecOps & Data Lab:** Explore an interactive sample graph of 18 synthetic transactions, inspect node embeddings, and simulate deposit growth scenarios with an interactive CASA slider.

---

##  System Architecture & Tech Stack

```
K-NEXUS-Web/
├── frontend/             # Production static SPA bundle
│   └── dist/             # Built React assets (HTML/CSS/JS)
├── src/
│   ├── app_v2.py         # FastAPI application & REST API routes
│   ├── demo_security.py  # Session isolation, CSRF, idempotency & security headers
│   └── ui/               # React UI components (Dashboard, TransferForm, Styles)
├── models/
│   ├── flowsense.onnx    # ONNX liquidity projection model
│   └── trustgraph.onnx   # ONNX mule & fraud classification model
├── data/                 # Synthetic banking profiles & graph node embeddings
├── tests/
│   └── test_security.py  # Automated security boundaries & regression tests
├── Dockerfile            # Multi-stage production build (Node 22 + Python 3.13)
├── render.yaml           # Render Infrastructure-as-Code (Blueprint)
└── run.py                # Production ASGI entrypoint (Uvicorn)
```

- **Frontend:** React 18, Vite 8, Lucide React, Custom Mobile-First CSS Design System
- **Backend:** Python 3.13, FastAPI 0.141, Starlette 1.6, Uvicorn 0.53 (Single instance/worker)
- **Machine Learning Runtime:** ONNX Runtime 1.30 with OpenMP (`libgomp1`), Pandas 3.0, NumPy 2.5
- **Data & State Tier:** In-Memory Redis Simulation with Per-Visitor Isolated Session Context

---

##  Security by Design

- **Strict Session Isolation:** Visitor balances, pending step-up tokens, and transaction history are completely isolated in separate in-memory session contexts (`DemoSession`).
- **Tamper-Proof Micro-Auth Tokens:** Clearance tokens are signed using HMAC-SHA256 with an ephemeral 120-second expiration, strictly bound to the visitor session and transaction parameters.
- **CSRF & Idempotency Enforcement:** All state-mutating requests require valid `X-CSRF-Token` headers and unique `X-Idempotency-Key` headers (UUID) to prevent double debits.
- **Model Checksum Integrity:** Validates SHA-256 hashes of all `.onnx` model files at runtime startup to guard against tampering.
- **Hardened Cookies & Headers:** Production cookies utilize the `__Host-` prefix, `Secure`, `HttpOnly`, and `SameSite=Strict`. Response headers enforce Strict Content-Security-Policy (CSP), HSTS, `X-Content-Type-Options: nosniff`, and `X-Frame-Options: DENY`.
- **DoS Mitigation:** Enforces strict request body limits (max 8 KiB) and IP-based limits on session creation and per-session limits on API requests.

---

##  Local Development

### Prerequisites
- **Node.js:** v22.12 or newer
- **Python:** v3.13 or newer

### 1. Setup & Run Full-Stack Server
```powershell
# Create and activate virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install locked dependencies
pip install -r requirements.lock
npm ci

# Build the frontend SPA
npm run build

# Start the production server
python run.py
```
Open your browser at <http://127.0.0.1:8000/> (Health check: <http://127.0.0.1:8000/api/v2/health>).

### 2. Frontend Hot-Reload Development
To develop UI components with instant hot reload:
```powershell
# In a separate terminal
npm run dev
```
Navigate to <http://127.0.0.1:5173/>. Vite will automatically proxy all `/api` calls to the Python backend on port 8000.

---

##  Deployment Guide (Render)

This repository includes a production-ready [Dockerfile](Dockerfile) and [render.yaml](render.yaml) Blueprint:

### 1. Environment Variables Configuration

| Key | Value | Purpose |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | Enables production security controls and strict cookie policies |
| `HOST` | `0.0.0.0` | Binds server to all interfaces inside the Docker container |
| `FORWARDED_ALLOW_IPS` | `*` | Trusts Render reverse proxy headers for real client IP extraction |
| `DEMO_SESSION_SECRET` | *(At least 32 characters)* | Master HMAC secret key (use Render's `Generate` button) |

### 2. Health Check Configuration
- **Health Check Path:** `/api/v2/health`

### 3. Optional Availability Monitoring
Monitor `/api/v2/health` with your chosen monitoring service. A periodic health request is not an uptime guarantee; verify hosting limits and deployment readiness for a live demonstration.

---

##  Testing & Security Verification

```powershell
# Install test dependencies
pip install -r requirements-dev.txt

# Run the backend and frontend checks
python -m unittest discover -s tests -p 'test_*.py' -v
npm run test:ui

# Perform automated security audits on dependencies
pip-audit -r requirements.lock --disable-pip --no-deps
npm audit --audit-level=low

# Validate frontend production build
npm run build
```

---

##  Disclaimer & Prototype Boundaries

1. **Independent UX Prototype:** This project is an independent conceptual research prototype created for UX exploration. It is not affiliated with, endorsed by, or connected to KASIKORNBANK (KBank), KBTG, K PLUS, or MAKE by KBank.
2. **100% Synthetic Data:** All accounts, balances, transaction histories, risk labels, and biometric verification checks are completely synthetic and simulated.
3. **No Real Banking Connectivity:** There is no integration with live banking cores, payment networks, or facial recognition hardware.
4. **Volatile In-Memory Storage:** Session balances and history expire 1 hour after session creation or upon container restart/redeployment.

## Product review and daily-plan validation

See [the UX, product, and security review](docs/PRODUCT_REVIEW_2026-10-15.md) for the findings, changes, verification, and remaining prototype boundaries.
