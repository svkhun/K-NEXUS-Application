from src.flowsense_engine import demo_now, next_payday, commitments, reserve_settings, horizon as calculate_horizon
from src.transfer_planning import (transfer_impact, plan_fingerprint, bill_for_transfer,
                                   apply_planned_debit, verification_guidance)
from fastapi import FastAPI, HTTPException, Query, Header, Path, Request
from starlette.middleware.trustedhost import TrustedHostMiddleware
from src.demo_security import (PRODUCTION, SECRET, ALLOWED_HOSTS, DEMO_ACCOUNTS, DEMO_RECIPIENTS, SEED_ACCOUNTS, SessionMapping, current_session, DemoSessionMiddleware, BodyLimitMiddleware, SecurityHeadersMiddleware)
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from functools import lru_cache
from typing import Optional, List, Dict, Any, Literal
import onnxruntime as rt
import pandas as pd
import numpy as np
import time
import math
import os
import hmac
import hashlib
import secrets
import base64
import json
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")

app = FastAPI(
    title="K-NEXUS — FlowSense & TrustGraph Prototype",
    description="Synthetic-data API for exploring liquidity, flexible saving, and transfer-risk interactions. No real bank connection or biometric verification.",
    version="4.0.0", docs_url=None, redoc_url=None, openapi_url=None
)

app.add_middleware(DemoSessionMiddleware)
app.add_middleware(BodyLimitMiddleware)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=ALLOWED_HOSTS)
app.add_middleware(SecurityHeadersMiddleware)
HMAC_SECRET = SECRET

@app.exception_handler(RequestValidationError)
async def validation_error_response(request, error):
    # Never echo raw request values, non-finite numbers, or auth tokens.
    return JSONResponse(status_code=422, content={
        "detail": "ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบบัญชี จำนวนเงิน และข้อมูลที่ส่ง",
        "errors": [{"field": list(item["loc"]), "type": item["type"]} for item in error.errors()],
    })

def get_account_lock(account_id: str):
    return current_session().account_lock

def mask_account_id(acc_id: Optional[str]) -> str:
    """Masks account ID per National ITMX & PDPA standards (e.g. ACC_0100 -> ACC_***0)."""
    if not acc_id:
        return "****"
    if len(acc_id) < 5:
        return f"{acc_id[:1]}***"
    return f"{acc_id[:4]}***{acc_id[-1]}"

def audit_log(event_type: str, actor: str, details: Dict[str, Any]):
    if actor in DEMO_ACCOUNTS:
        state = LIVE_ACCOUNT_STATES[actor]
        events = state.setdefault("events", [])
        events.insert(0, {"id": secrets.token_hex(8), "event_type": event_type, "timestamp": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(), "details": details})
        del events[50:]
    record = {
        "audit_timestamp": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
        "service": "k-nexus-web",
        "event_type": event_type,
        "actor_masked": mask_account_id(actor),
        "details": details
    }
    print(f"[AUDIT-SIEM] {json.dumps(record, ensure_ascii=False)}")

def generate_signed_micro_auth_token(source_acc: str, target_acc: str, amount: float, purpose="micro_auth") -> str:
    """Generates an HMAC-SHA256 tamper-proof clearance token with 120s TTL."""
    payload = {
        "src": source_acc,
        "dst": target_acc,
        "amt": round(amount, 2),
        "purpose": purpose,
        "iat": int(time.time()),
        "exp": int(time.time()) + 120,
        "nonce": PENDING_STEP_UP[step_up_key(source_acc, target_acc, amount)]["nonce"],
        "session_binding": hashlib.sha256(current_session().sid.encode()).hexdigest()
    }
    payload_str = json.dumps(payload, separators=(',', ':'))
    b64_payload = base64.urlsafe_b64encode(payload_str.encode()).decode()
    signature = hmac.new(HMAC_SECRET.encode(), b64_payload.encode(), hashlib.sha256).hexdigest()
    return f"TG.{b64_payload}.{signature}"

def verify_signed_micro_auth_token(token: str, source_acc: str, target_acc: str, amount: float, purpose="micro_auth") -> bool:
    """Verifies HMAC signature, expiration TTL, and account/amount binding."""
    if not token or not token.startswith("TG."):
        return False
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return False
        _, b64_payload, sig = parts
        expected_sig = hmac.new(HMAC_SECRET.encode(), b64_payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return False
        payload = json.loads(base64.urlsafe_b64decode(b64_payload.encode()).decode())
        if payload.get("purpose") != purpose:
            return False
        if time.time() > payload.get("exp", 0):
            return False
        pending = PENDING_STEP_UP.get(step_up_key(source_acc, target_acc, amount), {})
        if payload.get("session_binding") != hashlib.sha256(current_session().sid.encode()).hexdigest() or payload.get("nonce") != pending.get("nonce"):
            return False
        if payload.get("src") != source_acc or payload.get("dst") != target_acc:
            return False
        if abs(payload.get("amt", 0.0) - amount) > 0.01:
            return False
        return True
    except Exception:
        return False



REACT_DIST_DIR = os.path.join(FRONTEND_DIR, "dist")

# Mount React Built Assets
if os.path.exists(os.path.join(REACT_DIST_DIR, "assets")):
    app.mount("/assets", StaticFiles(directory=os.path.join(REACT_DIST_DIR, "assets")), name="assets")

# ==============================================================================
# FRONTEND SPA & HTML ROUTES (React Router 6 Multi-Page Navigation)
# ==============================================================================
def get_spa_or_landing_response():
    react_index = os.path.join(REACT_DIST_DIR, "index.html")
    if os.path.exists(react_index):
        return FileResponse(react_index)
    landing_path = os.path.join(FRONTEND_DIR, "landing.html")
    if os.path.exists(landing_path):
        return FileResponse(landing_path)
    return JSONResponse(status_code=503, content={"status": "Frontend not built. Run npm install and npm run build."})

@app.get("/", response_class=FileResponse)
@app.get("/home", response_class=FileResponse)
@app.get("/landing", response_class=FileResponse)
@app.get("/flowsense", response_class=FileResponse)
@app.get("/trustgraph", response_class=FileResponse)
@app.get("/wealthpilot", response_class=FileResponse)
@app.get("/sentinel", response_class=FileResponse)
@app.get("/architecture", response_class=FileResponse)
@app.get("/personas", response_class=FileResponse)
@app.get("/app", response_class=FileResponse)
@app.get("/dashboard", response_class=FileResponse)
@app.get("/simulation", response_class=FileResponse)
@app.get("/simulator", response_class=FileResponse)
def serve_spa():
    return get_spa_or_landing_response()

@app.get("/favicon.svg", include_in_schema=False)
@app.get("/favicon.ico", include_in_schema=False)
def serve_favicon():
    favicon_dist = os.path.join(REACT_DIST_DIR, "favicon.ico")
    if os.path.exists(favicon_dist):
        return FileResponse(favicon_dist)
    favicon_svg = os.path.join(REACT_DIST_DIR, "favicon.svg")
    if os.path.exists(favicon_svg):
        return FileResponse(favicon_svg, media_type="image/svg+xml")
    favicon_svg = os.path.join(FRONTEND_DIR, "img", "favicon.svg")
    if os.path.exists(favicon_svg):
        return FileResponse(favicon_svg, media_type="image/svg+xml")
    return {"status": "Favicon not found"}


@app.get('/k-nexus-logo.svg', include_in_schema=False)
def serve_public_logo():
    return FileResponse(os.path.join(REACT_DIST_DIR, 'k-nexus-logo.svg'), media_type='image/svg+xml')


# ==============================================================================
# 1. MODEL SESSIONS & FEATURE STORES (IN-MEMORY TIER 1)
# ==============================================================================
# The old files stay intact for rollback. New TrustGraph is a pinned atomic pair.
from src.model_package import load_package, load_legacy
from src.liquidity_forecast import forecast as rule_forecast
from pathlib import Path as FilePath
from src.baseline_policy import seed_assumptions, select_spending, VERSION as BASELINE_VERSION
SERVING_CONFIG = json.loads((FilePath(BASE_DIR) / "models/serving.json").read_text(encoding="utf-8"))
BASELINE_CONFIG = json.loads((FilePath(BASE_DIR) / 'config/baseline-personas.v1.json').read_text(encoding='utf-8'))
BASELINE_MODE = os.environ.get('FLOWSENSE_BASELINE_MODE', 'OFF' if PRODUCTION else 'BASELINE')
if BASELINE_MODE not in ('BASELINE', 'OFF'):
    raise RuntimeError('Unknown baseline mode')
PACKAGE_DIR = FilePath(BASE_DIR) / "models/packages" / SERVING_CONFIG["package_version"]
if SERVING_CONFIG.get("flowsense_enabled"):
    raise RuntimeError("FlowSense activation requires calendar revalidation and an application release")
if SERVING_CONFIG.get("trustgraph_enabled"):
    PACKAGE_MANIFEST, PACKAGE_SESSIONS, PACKAGE_EMBEDDINGS = load_package(PACKAGE_DIR, SERVING_CONFIG["manifest_sha256"], enabled_models=('trustgraph',), integrity_scope='runtime')
    sentinel_sess = PACKAGE_SESSIONS["trustgraph"]
    ACTIVE_TRUSTGRAPH_VERSION = PACKAGE_MANIFEST["package_version"]
else:
    sentinel_sess, PACKAGE_EMBEDDINGS = load_legacy(FilePath(BASE_DIR)/"models/legacy", SERVING_CONFIG["legacy_hashes"])
    ACTIVE_TRUSTGRAPH_VERSION = "legacy-pre-2026.10.27.1"
sentinel_in_name = sentinel_sess.get_inputs()[0].name
sentinel_out_prob = sentinel_sess.get_outputs()[1].name

def load_data_csv(primary_file: str, fallback_file: str = None) -> pd.DataFrame:
    p_primary = os.path.join(BASE_DIR, "data", primary_file)
    if os.path.exists(p_primary):
        return pd.read_csv(p_primary)
    if fallback_file:
        p_fallback = os.path.join(BASE_DIR, "data", fallback_file)
        if os.path.exists(p_fallback):
            return pd.read_csv(p_fallback)
    raise FileNotFoundError(f"Neither {p_primary} nor {fallback_file} could be found.")

print("[Init] Caching In-Memory Feature Store (Redis Simulation)...")
FEATURE_STORE_CACHE = PACKAGE_EMBEDDINGS

df_users_raw = load_data_csv("03_trustgraph_users_and_mule_labels.csv", "03_sentinel_users_and_mule_labels.csv").set_index("account_id")
USERS_METADATA_CACHE: Dict[str, Dict[str, Any]] = df_users_raw.to_dict(orient="index")

# Behavioral Profiles
df_profiles = load_data_csv("01_flowsense_user_profiles.csv", "user_behavioral_profiles.csv").set_index("account_id")
BEHAVIORAL_PROFILES_CACHE: Dict[str, Dict[str, Any]] = df_profiles.to_dict(orient="index")

# Transactions for SecOps & Stream simulation

# Dynamic In-Memory Vault state store (simulating live banking core account balance)
INITIAL_ACCOUNT_STATES: Dict[str, Dict[str, float]] = {}
for acc_id in DEMO_ACCOUNTS:
    prof = BEHAVIORAL_PROFILES_CACHE[acc_id]
    INITIAL_ACCOUNT_STATES[acc_id] = {
        "main_balance": float(prof["monthly_salary"] * 0.65),
        "vault_balance": float(prof["initial_vault_savings"]),
        "total_swept": 0.0,
        "savings_enabled": False,
        "daily_spent_today": 0.0,
        "last_sweep_ts": time.time()
    }

SEED_ACCOUNTS.update(INITIAL_ACCOUNT_STATES)
def initialize_session_bills(accounts):
    for account_id, state in accounts.items():
        now = demo_now(state)
        state.update(seed_assumptions(account_id, now, BASELINE_CONFIG))
        state['baseline_mode'] = BASELINE_MODE
        commitments(BEHAVIORAL_PROFILES_CACHE[account_id], now, state)

from src import demo_security as security_state
security_state.ACCOUNT_INITIALIZER = initialize_session_bills
LIVE_ACCOUNT_STATES = SessionMapping("accounts")
START_TIME = time.time()

# A step-up decision only follows a risk evaluation in this in-memory demo.
PENDING_STEP_UP = SessionMapping("pending")
PENDING_STEP_UP_LOCK = threading.Lock()

def step_up_key(source_acc: str, target_acc: str, amount: float) -> tuple:
    return (source_acc, target_acc, round(amount, 2))

TRANSFER_COOLDOWN_SECONDS = 15 * 60


def cooldown_status(pending):
    now = time.time()
    return {"cooldown_required": pending.get("cooldown_duration_sec", 0) > 0,
            "cooldown_duration_sec": pending.get("cooldown_duration_sec", 0),
            "cooldown_ends_at": pending.get("cooldown_ends_at", now),
            "cooldown_remaining_sec": max(0, math.ceil(pending.get("cooldown_ends_at", now) - now)),
            "server_now": now, "review_expires_at": pending["expires"]}


def remember_step_up(source_acc: str, target_acc: str, amount: float, risky=False):
    with PENDING_STEP_UP_LOCK:
        now = time.time()
        review_key = step_up_key(source_acc, target_acc, amount)
        previous = PENDING_STEP_UP.get(review_key)
        if previous and (previous["expires"] <= now or previous.get("is_risky") != risky):
            previous = None
        for key in list(PENDING_STEP_UP):
            if PENDING_STEP_UP[key]["expires"] <= now or key[0] == source_acc:
                del PENDING_STEP_UP[key]
        while len(PENDING_STEP_UP) >= 32:
            del PENDING_STEP_UP[next(iter(PENDING_STEP_UP))]
        state = LIVE_ACCOUNT_STATES[source_acc]
        duration = 0
        ready_at = now
        if previous:
            # Rechecking the same active transaction retains its own policy/deadline.
            # Cancellation deletes this record, so a new request uses current settings.
            ready_at = previous["cooldown_ends_at"]
            duration = previous["cooldown_duration_sec"]
        elif risky and state.get("transfer_cooldown_enabled", True):
            duration = TRANSFER_COOLDOWN_SECONDS
            ready_at = now + duration
        PENDING_STEP_UP[review_key] = {
            "expires": max(previous["expires"] if previous else 0, ready_at + (600 if risky else 120)),
            "nonce": secrets.token_hex(16), "is_risky": risky,
            "cooldown_duration_sec": duration, "cooldown_ends_at": ready_at,
            "source_account_id": source_acc, "target_account_id": target_acc, "amount": amount,
            "created_at": now}


def retain_transfer_review(result, payload):
    pending = PENDING_STEP_UP[step_up_key(payload.source_account_id, payload.target_account_id, payload.amount)]
    state = LIVE_ACCOUNT_STATES[payload.source_account_id]
    prof = BEHAVIORAL_PROFILES_CACHE[payload.source_account_id]
    result.update(planning_details(payload, state, prof))
    pending["plan_fingerprint"] = plan_fingerprint(state, prof)
    pending["matched_bill_id"] = payload.matched_bill_id
    pending["transfer_purpose"] = payload.transfer_purpose
    pending["requires_auth"] = result["status"] == "MICRO_AUTH_REQUIRED"
    pending["evaluation"] = result
    response = {**result, **cooldown_status(pending)}
    if not pending["requires_auth"]:
        response["review_token"] = generate_signed_micro_auth_token(payload.source_account_id, payload.target_account_id, payload.amount, "review")
    return response


def planning_details(payload, state, prof):
    try:
        impact = transfer_impact(state, prof, payload.amount, payload.matched_bill_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error))
    today = demo_now(state).strftime("%Y-%m-%d")
    previous = state.get("transfer_totals", {}).get(f"{today}:{payload.target_account_id}", {})
    return {"liquidity_impact": impact, "transfer_purpose": payload.transfer_purpose,
            "matched_bill_id": payload.matched_bill_id,
            "verification_guidance": verification_guidance(payload.transfer_purpose),
            "transfer_sequence": {"count_today": previous.get("count", 0),
                                  "sent_today": previous.get("amount", 0),
                                  "total_if_confirmed": round(previous.get("amount", 0)+payload.amount, 2)}}


def require_cooldown_complete(source_acc, target_acc, amount):
    pending = PENDING_STEP_UP.get(step_up_key(source_acc, target_acc, amount), {})
    remaining = max(0, math.ceil(pending.get("cooldown_ends_at", 0) - time.time()))
    if remaining:
        raise HTTPException(status_code=409, detail=f"รายการนี้อยู่ระหว่างพักก่อนโอน เหลืออีก {remaining} วินาที กรุณาตรวจสอบผู้รับก่อนยืนยัน")

def has_pending_step_up(source_acc: str, target_acc: str, amount: float) -> bool:
    with PENDING_STEP_UP_LOCK:
        return PENDING_STEP_UP.get(step_up_key(source_acc, target_acc, amount), {}).get("expires", 0) > time.time()

def clear_step_up(source_acc: str, target_acc: str, amount: float):
    with PENDING_STEP_UP_LOCK:
        PENDING_STEP_UP.pop(step_up_key(source_acc, target_acc, amount), None)


def clear_account_reviews(source_acc):
    with PENDING_STEP_UP_LOCK:
        for key in list(PENDING_STEP_UP):
            if key[0] == source_acc:
                del PENDING_STEP_UP[key]

def consume_step_up(source_acc: str, target_acc: str, amount: float) -> bool:
    with PENDING_STEP_UP_LOCK:
        key = step_up_key(source_acc, target_acc, amount)
        if PENDING_STEP_UP.get(key, {}).get("expires", 0) <= time.time():
            return False
        del PENDING_STEP_UP[key]
        return True

# ==============================================================================
# 2. PYDANTIC SCHEMAS (STRICT BANKING INPUT VALIDATION)
# ==============================================================================
class StrictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    @field_validator("account_id", "source_account_id", check_fields=False)
    @classmethod
    def supported_source(cls, value):
        if value not in DEMO_ACCOUNTS:
            raise ValueError("Unknown demo account")
        return value

    @field_validator("target_account_id", check_fields=False)
    @classmethod
    def supported_target(cls, value):
        if value not in DEMO_RECIPIENTS:
            raise ValueError("Unknown demo recipient")
        return value

    @field_validator("amount", "custom_sweep_amount", check_fields=False)
    @classmethod
    def currency_precision(cls, value):
        if value is not None and round(value, 2) != value:
            raise ValueError("Use at most two decimal places")
        return value

    @model_validator(mode="after")
    def different_accounts(self):
        if getattr(self, "source_account_id", None) is not None and self.source_account_id == self.target_account_id:
            raise ValueError("Cannot transfer to the source account")
        return self

class TransferEvaluationRequest(StrictRequest):
    source_account_id: str
    target_account_id: str
    amount: float = Field(..., gt=0, le=100_000)
    is_first_time_transfer: int = Field(1, ge=0, le=1)
    device_switch_last_24h: int = Field(0, ge=0, le=1)
    session_duration_sec: int = Field(12, ge=1, le=86400)
    ratio_to_daily_avg: float = Field(12.5, gt=0, le=1000)
    auth_factor_used: Literal["pin", "face_scan", "none"] = "pin"
    scenario_mode: Literal["auto", "suspicious", "blocked"] = "auto"
    matched_bill_id: Optional[str] = Field(None, max_length=40)
    transfer_purpose: Literal["general", "job", "unlock", "changed_account"] = "general"

class MicroAuthRequest(StrictRequest):
    source_account_id: str
    target_account_id: str
    amount: float = Field(..., gt=0, le=100_000)

class TransferConfirmRequest(StrictRequest):
    source_account_id: str
    target_account_id: str
    amount: float = Field(..., gt=0, le=100_000)
    decision: Literal["PROCEED", "CANCEL"]
    auth_token: Optional[str] = Field(None, max_length=1024)
    review_token: Optional[str] = Field(None, max_length=1024)

class MicroSweepRequest(StrictRequest):
    account_id: str
    custom_sweep_amount: Optional[float] = Field(None, gt=0, le=100_000)

class LiquidityScenarioRequest(StrictRequest):
    account_id: str
    scenario: Literal["healthy", "normal_dip", "commitment_risk", "high_value"]

class SavingsPreferenceRequest(StrictRequest):
    account_id: str
    enabled: bool

class ReservePreferenceRequest(StrictRequest):
    account_id: str
    amount: float = Field(..., ge=500, le=10_000_000)

class TransferPreferenceRequest(StrictRequest):
    account_id: str
    enabled: bool

class VaultWithdrawalRequest(StrictRequest):
    account_id: str
    amount: float = Field(..., gt=0, le=10_000_000)

# ==============================================================================
# 3. TRUSTGRAPH CORE SERVICES (ZERO-DELAY BASELINE & TARGET-SPECIFIC FRAUD DEFENSE)
# ==============================================================================
@app.post("/api/v2/trustgraph/evaluate-transfer")
def evaluate_transfer_v2(payload: TransferEvaluationRequest):
    """Preview only. Every debit requires a separate, bound final confirmation."""
    if payload.source_account_id not in LIVE_ACCOUNT_STATES:
        raise HTTPException(status_code=404, detail="Unknown demo source")
    if LIVE_ACCOUNT_STATES[payload.source_account_id]["main_balance"] < payload.amount:
        raise HTTPException(status_code=400, detail="ยอดเงินในบัญชีหลักไม่เพียงพอ")
    details = planning_details(payload, LIVE_ACCOUNT_STATES[payload.source_account_id], BEHAVIORAL_PROFILES_CACHE[payload.source_account_id])
    t_start = time.perf_counter()

    # Unknown accounts are rejected by StrictRequest. Known accounts without
    # graph context get precisely 16 zeros, plus a response-only context flag.
    missing_context = payload.target_account_id not in FEATURE_STORE_CACHE
    target_emb = FEATURE_STORE_CACHE.get(payload.target_account_id, np.zeros(16, dtype=np.float32))
    target_meta = USERS_METADATA_CACHE.get(payload.target_account_id, {})

    # 2. Prepare Vector: [amount, is_first_time, device_switch, duration, ratio, auth_face, auth_none, auth_pin, 16 embeddings]
    auth_face = 1.0 if payload.auth_factor_used == "face_scan" else 0.0
    auth_none = 1.0 if payload.auth_factor_used == "none" else 0.0
    auth_pin = 1.0 if payload.auth_factor_used == "pin" else 0.0

    telemetry = np.array([
        payload.amount,
        float(payload.is_first_time_transfer),
        float(payload.device_switch_last_24h),
        float(payload.session_duration_sec),
        payload.ratio_to_daily_avg,
        auth_face,
        auth_none,
        auth_pin
    ], dtype=np.float32)

    feature_vec = np.concatenate([telemetry, target_emb]).reshape(1, -1)

    # 3. ONNX Fast Inference (<80ms Target SLA)
    raw_probs = sentinel_sess.run([sentinel_out_prob], {sentinel_in_name: feature_vec})[0]
    raw_model_score = float(raw_probs[0, 1] if SERVING_CONFIG['trustgraph_enabled'] else raw_probs[0][1])
    current_risk = raw_model_score
    if target_meta.get("is_mule", 0) == 1:
        current_risk = max(current_risk, 0.45)

    details.update(raw_model_score=raw_model_score, policy_score=current_risk,
        synthetic_score_floor=0.45 if target_meta.get("is_mule", 0) == 1 else None,
        synthetic_blacklist=payload.target_account_id == "ACC_0000",
        missing_graph_context=missing_context, model_package_version=ACTIVE_TRUSTGRAPH_VERSION,
        model_threshold_experimental=0.5, policy_review_threshold=0.45,
        explanation_type="CONTEXTUAL_AND_POLICY_NOT_MODEL_ATTRIBUTION",
        explanation_note="ข้อมูลประกอบและ policy จำลอง ไม่ใช่ attribution ของโมเดล; ไม่มี graph context ไม่ได้แปลว่าปลอดภัย")

    # 4. Beneficiary Contextual Metadata
    account_age_days = target_meta.get("account_age_days", 90)
    is_mule_ground_truth = target_meta.get("is_mule", 0)
    kyc_level = target_meta.get("kyc_level", 2)
    inflow_velocity = target_meta.get("avg_inflow_velocity_sec", 3600.0)

    latency_ms = (time.perf_counter() - t_start) * 1000

    # --------------------------------------------------------------------------
    # HIGH-VALUE DEMO GATE (>= 50,000 THB)
    # --------------------------------------------------------------------------
    if payload.target_account_id == "ACC_0000":
        clear_account_reviews(payload.source_account_id)
        audit_log("TRANSFER_BLOCKED", payload.source_account_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount, "latency_ms": round(latency_ms, 2)})
        return {
            "status": "BLOCKED_MULE_INTERDICTION",
            **details,
            "risk_tier": "CONFIRMED_MULE_RING",
            "current_risk_score": round(current_risk, 4),
            "risk_score": round(current_risk, 4),
            "zero_delay_baseline": False,
            "step_up_required": False,
            "action": "BLOCK",
            "hard_blocked": True,
            "final_decision_left_to_user": False,
            "direct_risk_reasoning": "บัญชีปลายทางอยู่ใน synthetic blacklist ของเดโม จึงบล็อกตาม policy จำลอง",
            "counterfactual_message": "บัญชีปลายทางอยู่ใน synthetic blacklist ของเดโม จึงบล็อกตาม policy จำลอง",
            "reason_summary": "ป้ายระงับรายการในข้อมูลสมมติ เป็น policy ไม่ใช่ข้อสรุปจากโมเดล",
            "direct_risk_reasons_list": [
                "ป้ายระงับรายการในข้อมูลสมมติ เป็น policy ไม่ใช่ข้อสรุปจากโมเดล",
                "บัญชีนี้มีป้ายกำกับระงับการโอนในชุดข้อมูลสมมติ"
            ],
            "primary_reason_th": "บัญชีปลายทางมีป้ายระงับในข้อมูลจำลอง จึงหยุดรายการนี้",
            "actionable_warning": "ระงับรายการตาม synthetic blacklist ของเดโม",
            "target_meta": {
                "account_id": payload.target_account_id,
                "account_age_days": account_age_days,
                "kyc_level": kyc_level,
                "velocity_sec": inflow_velocity
            },
            "latency_ms": round(latency_ms, 2)
        }

    if payload.amount >= 50000.0 and current_risk < 0.45:
        audit_log("TRANSFER_CHECK_REQUIRED", payload.source_account_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount, "latency_ms": round(latency_ms, 2)})
        remember_step_up(payload.source_account_id, payload.target_account_id, payload.amount)
        result = {
            "status": "MICRO_AUTH_REQUIRED",
            "risk_tier": "HIGH_VALUE_DEMO_CHECK",
            "current_risk_score": round(current_risk, 4),
            "risk_score": round(current_risk, 4),
            "zero_delay_baseline": False,
            "step_up_required": True,
            "friction_type": "5_SECOND_LIVENESS",
            "auth_duration_sec": 5,
            "bot_mandated": False,
            "eliminates_arbitrary_waiting": True,
            "direct_risk_reasoning": "รายการโอนมูลค่าสูงในสถานการณ์จำลองนี้ต้องตรวจเพิ่มก่อนยืนยัน",
            "counterfactual_message": "รายการโอนมูลค่าสูงในสถานการณ์จำลองนี้ต้องตรวจเพิ่มก่อนยืนยัน",
            "reason_summary": "ยอดโอนถึงเกณฑ์ตรวจเพิ่มของต้นแบบ",
            "direct_risk_reasons_list": ["ยอดโอนถึงเกณฑ์ตรวจเพิ่มของต้นแบบ"],
            "primary_reason_th": "รายการมูลค่าสูงในต้นแบบนี้ต้องผ่านการยืนยันตัวตนจำลองก่อนโอน",
            "actionable_warning": "⚠️ รายการมูลค่าสูง: กรุณาตรวจและยืนยันตัวตนจำลองก่อนโอน",
            "user_confirmation_prompt": "กรุณายืนยันตัวตนจำลอง แล้วตัดสินใจว่าจะโอนต่อหรือยกเลิก",
            "final_decision_left_to_user": True,
            "target_meta": {
                "account_id": payload.target_account_id,
                "account_age_days": account_age_days,
                "kyc_level": kyc_level,
                "velocity_sec": inflow_velocity
            },
            "latency_ms": round(latency_ms, 2)
        }
        result.update(details)
        return retain_transfer_review(result, payload)

    # --------------------------------------------------------------------------
    # HARD INTERDICTION: CONFIRMED MULE RING (Royal Decree B.E. 2566)
    # Applied strictly to confirmed blacklisted criminal accounts (e.g. ACC_0000 or scenario_mode == "blocked")
    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------
    # ROUTINE TRANSFERS: Preview first, without simulated auth or a timed pause
    # --------------------------------------------------------------------------
    if current_risk < 0.45:
        remember_step_up(payload.source_account_id, payload.target_account_id, payload.amount)
        result = {
            "status": "TRANSFER_REVIEW", "risk_tier": "LOW_RISK",
            "risk_score": round(current_risk, 4), "current_risk_score": round(current_risk, 4),
            "step_up_required": False, "zero_delay_baseline": False,
            "primary_reason_th": "ยังไม่พบสัญญาณผิดปกติจากข้อมูลจำลองที่มี กรุณาดูผลต่อแผนเงินก่อนยืนยัน",
            "direct_risk_reasons_list": [], "latency_ms": round(latency_ms, 2),
        }
        result.update(details)
        return retain_transfer_review(result, payload)

    # --------------------------------------------------------------------------
    # Risky transfers use the optional server-timed review period before Micro-Auth.
    # Triggers 5-second face liveness check & Direct Risk Reasoning
    # Leaves final transfer decision to user.
    # --------------------------------------------------------------------------
    direct_reasons = []
    if account_age_days <= 45:
        direct_reasons.append(f"บัญชีปลายทางเปิดใหม่เพียง {account_age_days} วัน")
    if inflow_velocity < 180:
        direct_reasons.append(f"หลังรับเงิน บัญชีผู้รับโอนออกต่อโดยเฉลี่ยใน {int(inflow_velocity)} วินาที")
    if payload.session_duration_sec < 15:
        direct_reasons.append(f"เริ่มทำรายการอย่างรวดเร็วภายใน {payload.session_duration_sec} วินาที")
    if payload.ratio_to_daily_avg > 5.0:
        direct_reasons.append(f"ยอดโอนสูงกว่าค่าเฉลี่ยต่อวัน {payload.ratio_to_daily_avg:.1f} เท่า")

    if not direct_reasons:
        direct_reasons.append("คะแนนหลังใช้ policy ถึงเกณฑ์ตรวจเพิ่มของเดโม ไม่ใช่ attribution ของกราฟ")

    primary_reason = direct_reasons[0]
    reason_summary = " | ".join(direct_reasons)

    audit_log("TRANSFER_CHECK_REQUIRED", payload.source_account_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount, "latency_ms": round(latency_ms, 2)})
    remember_step_up(payload.source_account_id, payload.target_account_id, payload.amount, risky=True)

    result = {
        "status": "MICRO_AUTH_REQUIRED",
        "risk_tier": "CRITICAL_ANOMALY",
        "current_risk_score": round(current_risk, 4),
        "risk_score": round(current_risk, 4),
        "zero_delay_baseline": False,
        "step_up_required": True,
        "friction_type": "5_SECOND_LIVENESS",
        "auth_duration_sec": 5,
        "eliminates_arbitrary_waiting": False,
        "direct_risk_reasoning": "ข้อมูลประกอบและ policy จำลอง ไม่ใช่ model attribution",
        "counterfactual_message": "ไม่มีการคำนวณ counterfactual หรือ attribution ในรุ่นนี้",
        "reason_summary": reason_summary,
        "direct_risk_reasons_list": direct_reasons,
        "primary_reason_th": primary_reason,
        "actionable_warning": f"⚠️ ตรวจพบความผิดปกติวิกฤต: {reason_summary}",
        "user_confirmation_prompt": "จำลองยืนยัน 5 วินาที ไม่มีการตรวจตัวตนหรือเปิดกล้อง แล้วตัดสินใจยืนยันหรือยกเลิกเอง",
        "final_decision_left_to_user": True,
        "target_meta": {
            "account_id": payload.target_account_id,
            "account_age_days": account_age_days,
            "kyc_level": kyc_level,
            "velocity_sec": inflow_velocity
        },
        "latency_ms": round(latency_ms, 2)
    }
    result.update(details)
    return retain_transfer_review(result, payload)

@app.post("/api/v2/trustgraph/verify-micro-auth")
def verify_micro_auth(payload: MicroAuthRequest):
    """
    Simulates step-up confirmation for an evaluated synthetic transaction.
    This is not biometric verification or proof of a real user's identity.
    """
    if not has_pending_step_up(payload.source_account_id, payload.target_account_id, payload.amount):
        raise HTTPException(status_code=400, detail="กรุณาตรวจสอบความเสี่ยงของรายการโอนก่อนยืนยันตัวตน")
    pending = PENDING_STEP_UP[step_up_key(payload.source_account_id, payload.target_account_id, payload.amount)]
    if not pending.get("requires_auth", True):
        raise HTTPException(status_code=400, detail="รายการนี้ยืนยันจากหน้าสรุปได้โดยไม่ต้องยืนยันตัวตนจำลอง")
    require_cooldown_complete(payload.source_account_id, payload.target_account_id, payload.amount)
    pending["expires"] = max(pending["expires"], int(time.time()) + 120)

    # Generate tamper-proof HMAC-SHA256 clearance token bound to accounts & amount
    token = generate_signed_micro_auth_token(payload.source_account_id, payload.target_account_id, payload.amount)
    return {
        "status": "MICRO_AUTH_VERIFIED",
        "verified": True,
        "verification_mode": "SIMULATED",
        "auth_duration_sec": 0,
        "clearance_token": token,
        "clearance_expires_at": int(time.time()) + 120,
        "cooldown": cooldown_status(PENDING_STEP_UP[step_up_key(payload.source_account_id, payload.target_account_id, payload.amount)]),
        "message": "ยืนยันตัวตนจำลองสำเร็จ กรุณาพิจารณาความเสี่ยงและตัดสินใจว่าจะโอนต่อหรือยกเลิก",
        "prompt_title": "ยืนยันการทำรายการโอนเงิน",
        "prompt_message": "ระบบได้ชี้แจงความเสี่ยงของบัญชีปลายทางแล้ว คุณต้องการดำเนินการโอนเงินต่อไปหรือไม่?",
        "options": ["PROCEED_TRANSFER", "CANCEL_TRANSFER"]
    }

@app.post("/api/v2/trustgraph/confirm-transfer")
def confirm_transfer(payload: TransferConfirmRequest, x_idempotency_key: Optional[str] = Header(None)):
    """
    Execute a reviewed transaction only with the appropriate bound token.
    Risky transactions additionally enforce the server cooldown and simulated auth.
    Recheck the financial snapshot before atomically settling money and any bill.
    """

    src_id = payload.source_account_id
    if src_id not in LIVE_ACCOUNT_STATES:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    decision = payload.decision

    if decision == "CANCEL":
        clear_step_up(src_id, payload.target_account_id, payload.amount)
        state = LIVE_ACCOUNT_STATES[src_id]
        res = {
            "status": "TRANSFER_CANCELLED",
            "decision": "CANCEL",
            "cooldown_cleared": True,
            "message": "ยกเลิกรายการและเวลาพักของรายการนี้แล้ว ยังไม่มีการหักเงินจากบัญชี",
            "current_balance": round(state["main_balance"], 2)
        }
        audit_log("TRANSFER_CANCELLED_BY_USER", src_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount})

        return res

    with get_account_lock(src_id):
        pending = PENDING_STEP_UP.get(step_up_key(src_id, payload.target_account_id, payload.amount), {})
        requires_auth = pending.get("requires_auth", True)
        token = payload.auth_token if requires_auth else payload.review_token
        purpose = "micro_auth" if requires_auth else "review"
        valid_token = verify_signed_micro_auth_token(token, src_id, payload.target_account_id, payload.amount, purpose)
        if not valid_token or not has_pending_step_up(src_id, payload.target_account_id, payload.amount):
            raise HTTPException(status_code=401, detail="กรุณาตรวจรายการและยืนยันตามขั้นตอนก่อนโอนต่อ")
        require_cooldown_complete(src_id, payload.target_account_id, payload.amount)
        state = LIVE_ACCOUNT_STATES[src_id]
        prof = BEHAVIORAL_PROFILES_CACHE[src_id]
        demo_now(state)
        if pending.get("plan_fingerprint") != plan_fingerprint(state, prof):
            return JSONResponse({"code": "PLAN_CHANGED", "detail": "ยอดเงินหรือแผนเปลี่ยนแล้ว กรุณาตรวจผลกระทบล่าสุดก่อนยืนยันอีกครั้ง ยังไม่มีการหักเงิน"}, status_code=409)
        if state["main_balance"] < payload.amount:
            raise HTTPException(status_code=400, detail=f"ยอดเงินในบัญชีหลักไม่เพียงพอ (มี ฿ {state['main_balance']:,.2f})")
        try:
            bill = bill_for_transfer(state, prof, pending.get("matched_bill_id"), payload.amount)
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error))
        if not consume_step_up(src_id, payload.target_account_id, payload.amount):
            raise HTTPException(status_code=401, detail="รายการหมดอายุ กรุณาตรวจรายการใหม่")
        apply_planned_debit(state, payload.amount, bill)
        today = demo_now(state).strftime("%Y-%m-%d")
        totals = state.setdefault("transfer_totals", {})
        for key in list(totals):
            if not key.startswith(today+":"):
                del totals[key]
        total = totals.setdefault(f"{today}:{payload.target_account_id}", {"count": 0, "amount": 0})
        total["count"] += 1
        total["amount"] = round(total["amount"]+payload.amount, 2)
        remaining = round(state["main_balance"], 2)

    res = {
        "status": "TRANSFER_EXECUTED",
        "receipt_id": "DEMO-" + secrets.token_hex(6).upper(),
        "executed_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
        "decision": "PROCEED",
        "amount": payload.amount,
        "source_account_id": src_id,
        "target_account_id": payload.target_account_id,
        "remaining_balance": remaining,
        "matched_bill": bill,
        "data_mode": "synthetic_demo",
        "message": f"บันทึกการโอนจำลอง ฿ {payload.amount:,.2f} สำเร็จ ไม่มีการโอนเงินจริงหรือยืนยันว่าผู้รับได้รับเงิน"
    }
    audit_log("TRANSFER_EXECUTED", src_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount, "remaining": remaining, "matched_bill_id": bill["id"] if bill else None})

    return res

# ==============================================================================
# 4. FLOWSENSE SERVICES (FLEXIBLE LIQUIDITY & AUTONOMOUS SAVING)
# ==============================================================================
@app.post("/api/v2/trustgraph/transfer-preference")
def set_transfer_preference(payload: TransferPreferenceRequest):
    LIVE_ACCOUNT_STATES[payload.account_id]["transfer_cooldown_enabled"] = payload.enabled
    audit_log("TRANSFER_PREFERENCE_UPDATED", payload.account_id, {"enabled": payload.enabled})
    return {"enabled": payload.enabled, "cooldown_seconds": TRANSFER_COOLDOWN_SECONDS,
            "applies_to": "NEW_RISKY_TRANSFERS", "existing_cooldowns_unchanged": True}


@app.get("/api/v2/trustgraph/pending-transfer/{account_id}")
def pending_transfer(account_id: str):
    if account_id not in DEMO_ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown demo account")
    rows = [row for row in PENDING_STEP_UP.values() if row.get("source_account_id") == account_id
            and row["expires"] > time.time() and row.get("evaluation")]
    if not rows:
        return {"pending": None}
    pending = max(rows, key=lambda row: row["created_at"])
    response = {**pending["evaluation"], **cooldown_status(pending),
                        "source_account_id": account_id, "target_account_id": pending["target_account_id"],
                        "amount": pending["amount"],
                        "plan_changed": pending.get("plan_fingerprint") != plan_fingerprint(LIVE_ACCOUNT_STATES[account_id], BEHAVIORAL_PROFILES_CACHE[account_id])}
    if not pending.get("requires_auth", True):
        response["review_token"] = generate_signed_micro_auth_token(account_id, pending["target_account_id"], pending["amount"], "review")
    return {"pending": response}


@app.get("/api/v2/flowsense/profile/{account_id}")
def get_flowsense_profile(account_id: str = Path(..., pattern=r"^[A-Za-z0-9_]{3,30}$", description="Sanitized Banking Account ID")):
    """
    Get user profile, behavioral cluster persona (Pitch: Primary 18k-35k Living Month-to-Month
    vs Secondary Active Mobile Transactor), live balance, and high-interest sub-account statistics.
    """
    if account_id not in DEMO_ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    prof = BEHAVIORAL_PROFILES_CACHE[account_id]
    state = LIVE_ACCOUNT_STATES[account_id]

    now = demo_now(state)
    return {
        "account_id": account_id,
        "baseline_mode": state.get('baseline_mode', BASELINE_MODE),
        "input_as_of": now.isoformat(),
        "spending_basis": select_spending(state, now),
        "posted_today_provenance": state.get('seeded_posted_today'),
        "masked_account_id": mask_account_id(account_id),
        "cf_user_id": prof["cf_user_id"],
        "monthly_salary": prof["monthly_salary"],
        "main_balance": round(state["main_balance"], 2),
        "vault_balance": round(state["vault_balance"], 2),
        "total_swept": round(state["total_swept"], 2),
        "daily_spent_today": round(state["daily_spent_today"], 2),
        "savings_enabled": state.get("savings_enabled", False),
        "transfer_cooldown_enabled": state.get("transfer_cooldown_enabled", True),
        "transfer_cooldown_minutes": TRANSFER_COOLDOWN_SECONDS // 60,
        "savings_capacity": get_flowsense_horizon_status(account_id)["savings_estimate"],
        "events": state.get("events", []),
        "persona": {
            "cluster_id": int(prof["cluster_id"]),
            "name": prof["persona_name"],
            "name_th": prof.get("persona_th", "กลุ่มเป้าหมาย First Jobber"),
            "description": prof.get("persona_desc", "First Jobber บริหารสภาพคล่องด้วย FlowSense และ Protected Vault"),
            "recommended_sweep_pct": prof["recommended_sweep_pct"],
            "scam_vulnerability": prof["scam_vulnerability"],
            "vault_friction_level": "STANDARD_WITHDRAWAL"
        }
    }

@app.get("/api/v2/flowsense/horizon-status/{account_id}")
def get_flowsense_horizon_status(account_id: str = Path(..., pattern=r"^[A-Za-z0-9_]{3,30}$", description="Sanitized Banking Account ID")):
    """
    Module A: FlowSense — Status Horizon Bar & Commitment Warnings:
    - Status Horizon Bar: A single clean indicator on the account home screen projecting month-end liquidity
      based on recurring commitments, removing the need for daily manual budgets.
    - Commitment Warnings: Fires alerts ONLY when an upcoming fixed debit (e.g., credit card bill or rent)
      is directly at risk based on current burn rate. Suppresses alerts during normal dips!
    """
    if account_id not in DEMO_ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    points = forecast_cashflow_30d(account_id)["timeline"]
    projection = {point["date"]: point["projected_balance"] for point in points if not point["is_past"]}
    result = calculate_horizon(BEHAVIORAL_PROFILES_CACHE[account_id], LIVE_ACCOUNT_STATES[account_id], projection)
    return {"account_id": account_id, "masked_account_id": mask_account_id(account_id), **result}

@app.get("/api/v2/flowsense/forecast-30d/{account_id}")
def forecast_cashflow_30d(account_id: str = Path(..., pattern=r"^[A-Za-z0-9_]{3,30}$", description="Sanitized Banking Account ID")):
    """Rule-based scenario until the new model's calendar is revalidated."""
    if account_id not in DEMO_ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown demo account")
    return {"account_id": account_id, **rule_forecast(BEHAVIORAL_PROFILES_CACHE[account_id], LIVE_ACCOUNT_STATES[account_id])}


@app.post("/api/v2/flowsense/micro-sweep")
def trigger_micro_sweep(payload: MicroSweepRequest, x_idempotency_key: Optional[str] = Header(None)):
    """
    Explicitly requested, opt-in savings with a conservative future-liquidity guard.
    """

    acc_id = payload.account_id
    if acc_id not in LIVE_ACCOUNT_STATES:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    with get_account_lock(acc_id):
        state = LIVE_ACCOUNT_STATES[acc_id]
        if not state.get("savings_enabled", False):
            raise HTTPException(status_code=400, detail="กรุณาเปิดการแยกเงินออมก่อน")

        liquidity = get_flowsense_horizon_status(acc_id)
        if liquidity['max_sweep_amount'] is None:
            raise HTTPException(status_code=409, detail='ข้อมูลไม่พอสำหรับประมาณการความสามารถในการออม: ' + liquidity['spending_basis']['reason'])
        sweep_amount = payload.custom_sweep_amount
        if sweep_amount is None:
            sweep_amount = liquidity["recommended_sweep_amount"]
        if sweep_amount <= 0 or sweep_amount > liquidity["max_sweep_amount"]:
            raise HTTPException(status_code=400, detail=f"แยกออมได้ไม่เกิน ฿{liquidity['max_sweep_amount']:,.2f} ต่อครั้ง หลังกันค่าใช้ชีวิต บิล และเงินสำรอง")
        state["main_balance"] = round(state["main_balance"] - sweep_amount, 2)
        state["vault_balance"] = round(state["vault_balance"] + sweep_amount, 2)
        state["total_swept"] = round(state["total_swept"] + sweep_amount, 2)
        state["last_sweep_ts"] = time.time()

        res_main = round(state["main_balance"], 2)
        res_vault = round(state["vault_balance"], 2)
        res_total = round(state["total_swept"], 2)

    res = {
        "status": "SWEEP_SUCCESS",
        "account_id": acc_id,
        "swept_amount": sweep_amount,
        "new_main_balance": res_main,
        "new_subaccount_balance": res_vault,
        "new_vault_balance": res_vault,
        "total_accumulated_swept": res_total,
        "safe_to_save_before_sweep": liquidity["savings_capacity"],
        "message": f"แยกเงินออม ฿{sweep_amount:,.2f} แล้ว คุณถอนเงินออมตามจำนวนที่ต้องการได้ตามปกติ"
    }
    audit_log("MICRO_SWEEP_EXECUTED", acc_id, {"swept": sweep_amount, "new_main": res_main, "new_vault": res_vault})

    return res

@app.post("/api/v2/flowsense/vault/withdraw")
@app.post("/api/v2/flowsense/recall")
def withdraw_savings(payload: VaultWithdrawalRequest, x_idempotency_key: Optional[str] = Header(None)):
    """Ordinary withdrawal of an explicit amount; savings opt-in is not required."""

    acc_id = payload.account_id
    if acc_id not in LIVE_ACCOUNT_STATES:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    with get_account_lock(acc_id):
        state = LIVE_ACCOUNT_STATES[acc_id]
        recall_amount = payload.amount

        if recall_amount > state["vault_balance"]:
            raise HTTPException(status_code=400, detail=f"ยอดเงินในบัญชีย่อยไม่เพียงพอ (มี ฿ {state['vault_balance']:,.2f})")

        state["vault_balance"] = round(state["vault_balance"] - recall_amount, 2)
        state["main_balance"] = round(state["main_balance"] + recall_amount, 2)
        state["total_swept"] = max(0.0, round(state.get("total_swept", 0.0) - recall_amount, 2))

        res_main = round(state["main_balance"], 2)
        res_vault = round(state["vault_balance"], 2)
        res_total = round(state["total_swept"], 2)

    res = {
        "status": "WITHDRAWAL_SUCCESS",
        "account_id": acc_id,
        "withdrawn_amount": round(recall_amount, 2),
        "new_main_balance": res_main,
        "new_subaccount_balance": res_vault,
        "new_vault_balance": res_vault,
        "total_accumulated_swept": res_total,
        "message": f"ถอนเงินออม ฿{recall_amount:,.2f} เข้าบัญชีหลักเรียบร้อยแล้ว"
    }
    audit_log("SAVINGS_WITHDRAWAL", acc_id, {"withdrawn": recall_amount, "new_main": res_main, "new_vault": res_vault})

    return res

@app.post("/api/v2/flowsense/reset-state/{account_id}")
def reset_account_state(account_id: str = Path(..., pattern=r"^[A-Za-z0-9_]{3,30}$", description="Sanitized Banking Account ID")):
    """
    Reset live banking account balances & sub-account state back to initial profile defaults.
    """
    if account_id not in DEMO_ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    prof = BEHAVIORAL_PROFILES_CACHE[account_id]
    LIVE_ACCOUNT_STATES[account_id] = {
        "main_balance": float(prof["monthly_salary"] * 0.65),
        "vault_balance": float(prof["initial_vault_savings"]),
        "total_swept": 0.0,
        "savings_enabled": False,
        "daily_spent_today": 0.0,
        "last_sweep_ts": time.time()
    }
    initialize_session_bills({account_id: LIVE_ACCOUNT_STATES[account_id]})
    for key in list(PENDING_STEP_UP):
        if key[0] == account_id:
            del PENDING_STEP_UP[key]
    audit_log("ACCOUNT_STATE_RESET", account_id, {"action": "reset_to_profile_defaults"})
    return {
        "status": "RESET_SUCCESS",
        "account_id": account_id,
        "main_balance": LIVE_ACCOUNT_STATES[account_id]["main_balance"],
        "vault_balance": LIVE_ACCOUNT_STATES[account_id]["vault_balance"],
        "message": f"รีเซ็ตยอดเงินและข้อมูลบัญชี {account_id} คืนค่าเริ่มต้นเรียบร้อยแล้ว"
    }

# ==============================================================================
# 5. SECOPS & EXECUTIVE INTELLIGENCE SERVICES
# ==============================================================================
@app.get("/api/v2/health")
def health_check():
    return {"status": "HEALTHY", "mode": "synthetic_demo", "version": "4.0.0",
            "trustgraph_version": ACTIVE_TRUSTGRAPH_VERSION,
            "flowsense_model_enabled": False, "forecast_mode": "LIVE_INTRADAY_BASELINE",
            "baseline_mode": BASELINE_MODE, "baseline_policy_version": BASELINE_VERSION,
            "loaded_models": list(PACKAGE_SESSIONS) if SERVING_CONFIG['trustgraph_enabled'] else ['trustgraph_legacy']}


@app.get('/release.json', include_in_schema=False)
def release_identity():
    path = FilePath(REACT_DIST_DIR) / 'release.json'
    if not path.is_file():
        raise HTTPException(status_code=503, detail='Release identity is unavailable')
    build = json.loads(path.read_text(encoding='utf-8'))
    # Render injects the final deployed revision at runtime, independent of build hashes.
    commit = os.environ.get('RENDER_GIT_COMMIT', '')
    return JSONResponse({**build,
        'deployed_commit': commit if len(commit) == 40 and all(c in '0123456789abcdef' for c in commit) else None,
        'baseline_mode': BASELINE_MODE, 'flowsense_model_enabled': False,
        'trustgraph_version': ACTIVE_TRUSTGRAPH_VERSION,
        'loaded_models': list(PACKAGE_SESSIONS) if SERVING_CONFIG['trustgraph_enabled'] else ['trustgraph_legacy'],
        'package_manifest_sha256': SERVING_CONFIG['manifest_sha256']},
        headers={'Cache-Control': 'no-store'})


@app.post("/api/v2/flowsense/scenario")
def set_liquidity_scenario(payload: LiquidityScenarioRequest):
    saved_reserve = {key: LIVE_ACCOUNT_STATES[payload.account_id][key]
                     for key in ("reserve_amount", "reserve_confirmed") if key in LIVE_ACCOUNT_STATES[payload.account_id]}
    reset_account_state(payload.account_id)
    state = LIVE_ACCOUNT_STATES[payload.account_id]
    state.update(saved_reserve)
    prof = BEHAVIORAL_PROFILES_CACHE[payload.account_id]
    salary = float(prof["monthly_salary"])
    state["scenario"] = payload.scenario
    draft = calculate_horizon(prof, state)
    obligations = draft["total_recurring_commitments"]
    burn = draft["savings_estimate"]["projected_living_cost"]
    if payload.scenario == "high_value":
        state["main_balance"] = 60000.0
    elif payload.scenario == "healthy" and burn is not None:
        estimate = draft["savings_estimate"]
        state["main_balance"] = round(max(salary * .9, estimate["fixed_commitments"] + estimate["projected_living_cost"] + estimate["emergency_buffer"] + 2000), 2)
    elif payload.scenario == "normal_dip" and burn is not None:
        # Presets adjust demo spending, not the visitor's genuine financial data.
        state["main_balance"] = round(salary * .49, 2)
        state["daily_spent_today"] = 0
        if calculate_horizon(prof, state)["commitment_at_risk"]:
            # Profiles with large obligations need extra headroom to remain safe.
            state["main_balance"] = round(obligations + burn + 1000, 2)
    else:
        state["main_balance"] = round(max(500, obligations * .45), 2)
    if payload.scenario in {"healthy", "normal_dip"} and burn is not None:
        # Keep safe presets safe for the current calendar and actual model forecast.
        forecast = forecast_cashflow_30d(payload.account_id)
        minimum = min(point["projected_balance"] for point in forecast["timeline"]
                      if not point["is_past"] and point["date"] < forecast["payday_date"])
        reserve = draft["emergency_buffer"] + 2000 if payload.scenario == "healthy" else 1000
        state["main_balance"] = round(state["main_balance"] + max(0, reserve - minimum), 2)
    audit_log("SCENARIO_CHANGED", payload.account_id, {"scenario": payload.scenario})
    return get_flowsense_horizon_status(payload.account_id)


@app.post("/api/v2/flowsense/savings-preference")
def set_savings_preference(payload: SavingsPreferenceRequest):
    with get_account_lock(payload.account_id):
        LIVE_ACCOUNT_STATES[payload.account_id]["savings_enabled"] = payload.enabled
    audit_log("SAVINGS_PREFERENCE_UPDATED", payload.account_id, {"enabled": payload.enabled})
    return {"account_id": payload.account_id, "savings_enabled": payload.enabled}


@app.post("/api/v2/flowsense/reserve-preview")
def preview_reserve(payload: ReservePreferenceRequest):
    """Read-only what-if using the same forecast and allocation rules as a saved plan."""
    with get_account_lock(payload.account_id):
        state = LIVE_ACCOUNT_STATES[payload.account_id]
        prof = BEHAVIORAL_PROFILES_CACHE[payload.account_id]
        points = forecast_cashflow_30d(payload.account_id)["timeline"]
        projection = {p["date"]: p["projected_balance"] for p in points if not p["is_past"]}
        before = calculate_horizon(prof, state, projection)
        draft = {**state, "reserve_amount": payload.amount}
        after = calculate_horizon(prof, draft, projection)
        fields = ("daily_safe_limit", "remaining_today", "savings_capacity", "budget_reserve_shortfall", "emergency_buffer")
        return {"account_id": payload.account_id, "amount": payload.amount,
                "before": {key: before[key] for key in fields},
                "after": {key: after[key] for key in fields}}


@app.post("/api/v2/flowsense/reserve-preference")
def set_reserve_preference(payload: ReservePreferenceRequest):
    with get_account_lock(payload.account_id):
        state = LIVE_ACCOUNT_STATES[payload.account_id]
        state["reserve_amount"] = payload.amount
        state["reserve_confirmed"] = True
    audit_log("RESERVE_PREFERENCE_UPDATED", payload.account_id, {"amount": payload.amount})
    return reserve_settings(state, BEHAVIORAL_PROFILES_CACHE[payload.account_id])


@app.get("/api/v2/demo/insights")
@lru_cache(maxsize=1)
def demo_insights():
    # Bounded graph sample from the original synthetic transactions. No live bank connection.
    frame = pd.read_csv(os.path.join(BASE_DIR, "data", "04_trustgraph_fraud_transactions.csv"))
    sample = frame[frame["is_scam"] == 1].head(18)
    ids = list(dict.fromkeys(sample["source_id"].tolist() + sample["target_id"].tolist()))
    aliases = {acc: f"N{index+1}" for index, acc in enumerate(ids)}
    return {"data_mode": "synthetic_sample", "nodes": [{"id": aliases[acc], "label": f"บัญชี {index+1:02d}", "is_mule": bool(USERS_METADATA_CACHE.get(acc, {}).get("is_mule", 0)), "age_days": int(USERS_METADATA_CACHE.get(acc, {}).get("account_age_days", 90))} for index, acc in enumerate(ids)], "edges": [{"source": aliases[row.source_id], "target": aliases[row.target_id], "amount": float(row.amount)} for row in sample.itertuples()], "sample_transactions": len(sample)}
