# K · FlowSense × TrustGraph — Interactive Web Prototype

[![Live Demo](https://img.shields.io/badge/Render-Live_Demo-00C7B7?style=for-the-badge&logo=render&logoColor=white)](https://k-web-application.onrender.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-4.0.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-1.30-005CED?style=for-the-badge&logo=onnx&logoColor=white)](https://onnxruntime.ai)
[![License](https://img.shields.io/badge/Status-Independent_Prototype-green?style=for-the-badge)](#disclaimer--prototype-boundaries)

An independent, production-grade UX concept prototype demonstrating two next-generation financial AI capabilities designed for modern mobile banking experiences (inspired by K+ / MAKE by KBank):

1. **FlowSense**: 30-day proactive liquidity runway forecasting and autonomous, surplus-only flexible micro-savings (Micro-Sweep).
2. **TrustGraph**: Pre-transfer mule account interdiction and transaction fraud intelligence with an explainable AI (XAI) risk panel and simulated step-up micro-authentication.

Engineered with a responsive, bank-grade mobile/desktop web interface, strict session isolation, and sub-second machine learning inference.

---

##  Live Demo & Endpoints

- **Live Web Application:** [https://k-web-application.onrender.com](https://k-web-application.onrender.com)
- **API Health Check:** [https://k-web-application.onrender.com/api/v2/health](https://k-web-application.onrender.com/api/v2/health)

> [!TIP]
> **Zero Cold-Start:** Configured with an automated keep-awake ping every 10 minutes via Cron-job. The application stays active 24/7 on Render and loads instantly (1–2 seconds) without spin-down latency.

---

##  Key Capabilities

### 1. FlowSense — Liquidity Forecasting & Smart Micro-Sweep
- **30-Day Liquidity Forecast:** High-resolution balance and cash flow projection across 30 future days, today, and 7 synthetic historical days powered by ONNX inference (`flowsense.onnx`).
- **Status Horizon & Runway Health:** Real-time liquidity runway bar and calculated daily safe-spending limit based on fixed debits, upcoming payday, and emergency buffers.
- **Normal-Dip Suppression:** Intelligent alert gating that suppresses noise during routine balance drops, alerting only when upcoming fixed obligations (rent, bills, debt) are projected to be at risk.
- **Surplus-Only Micro-Sweep:** Autonomous micro-savings engine that recommends moving only genuine surplus into an interest-bearing vault without impacting daily liquidity.
- **1-Tap Undo & Immediate Recall:** Instant one-tap reversal of the latest sweep, with partial or full emergency vault recall at zero penalty.

### 2. TrustGraph — Pre-Transfer Fraud & Mule Interdiction
- **Real-Time Graph Embedding & Risk Scoring:** Millisecond-level inference with ONNX graph node embeddings (`trustgraph.onnx`) evaluating beneficiary account age, velocity anomalies, and relational mule patterns.
- **Explainable AI (XAI) Risk Factors:** Human-readable risk explanations (e.g., dormant account reactivated, sudden deviation from historical averages, recipient velocity surge).
- **Simulated Micro-Auth (5s Step-Up):** A simulated 5-second facial liveness verification gate that generates a cryptographically signed clearance token (HMAC-SHA256, 120s TTL) binding source, recipient, amount, and visitor session.
- **Blocked Mule Interdiction:** Immediate transfer prevention for known or flagged mule accounts before debit execution.
- **Downloadable E-Slip:** Generates formatted, verifiable text receipts with unique demo transaction references.

### 3. Behavioral Personas & Interactive Data Lab
- **3 Synthetic Personas:** Switch between realistic financial profiles with distinct income rhythms:
  - **May (Early Career):** Stable entry-level salary, predictable living expenses.
  - **Golf (Freelancer / Business Owner):** Irregular lump-sum inflows, volatile spending cycles.
  - **Ann (Corporate Professional):** High income, multiple concurrent debt and family obligations.
- **SecOps & Data Lab:** Explore an interactive sample graph of 18 synthetic transactions, inspect node embeddings, and simulate deposit growth scenarios with an interactive CASA slider.

---

## 🛠 System Architecture & Tech Stack

```
k-web-application/
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
- **DoS Mitigation:** Enforces strict request body limits (max 8 KiB) and IP-based rate limiting on session creation and API operations.

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

## ☁️ Deployment Guide (Render)

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

### 3. Keep-Awake / Zero Cold-Start Setup (100% Free)
To prevent the Render free-tier instance from sleeping after 15 minutes of inactivity:
1. Register a free account at **[cron-job.org](https://cron-job.org)**.
2. Create a new Cronjob:
   - **URL:** `https://<your-service-name>.onrender.com/api/v2/health`
   - **Schedule:** `Every 10 minutes`
   - **Request Method:** `GET`
3. The lightweight health endpoint (~60 bytes) will be pinged periodically, keeping your service active 24/7 without incurring cold starts.

---

##  Testing & Security Verification

```powershell
# Install test dependencies
pip install -r requirements-dev.txt

# Run the complete test suite (19 test cases)
python -m unittest discover -s tests -p 'test_*.py' -v

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
4. **Volatile In-Memory Storage:** Session balances and history expire after 1 hour of inactivity or upon container restart/redeployment.
