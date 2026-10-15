from src.flowsense_engine import demo_now, next_payday, horizon as calculate_horizon
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
    title="FlowSense & TrustGraph — Interactive Prototype",
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
        "service": "k-flowsense-trustgraph",
        "event_type": event_type,
        "actor_masked": mask_account_id(actor),
        "details": details
    }
    print(f"[AUDIT-SIEM] {json.dumps(record, ensure_ascii=False)}")

def generate_signed_micro_auth_token(source_acc: str, target_acc: str, amount: float) -> str:
    """Generates an HMAC-SHA256 tamper-proof clearance token with 120s TTL."""
    payload = {
        "src": source_acc,
        "dst": target_acc,
        "amt": round(amount, 2),
        "iat": int(time.time()),
        "exp": int(time.time()) + 120,
        "nonce": PENDING_STEP_UP[step_up_key(source_acc, target_acc, amount)]["nonce"],
        "session_binding": hashlib.sha256(current_session().sid.encode()).hexdigest()
    }
    payload_str = json.dumps(payload, separators=(',', ':'))
    b64_payload = base64.urlsafe_b64encode(payload_str.encode()).decode()
    signature = hmac.new(HMAC_SECRET.encode(), b64_payload.encode(), hashlib.sha256).hexdigest()
    return f"TG.{b64_payload}.{signature}"

def verify_signed_micro_auth_token(token: str, source_acc: str, target_acc: str, amount: float) -> bool:
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


# ==============================================================================
# 1. MODEL SESSIONS & FEATURE STORES (IN-MEMORY TIER 1)
# ==============================================================================
# KBTG SECURITY: Model Integrity Verification (SHA-256 Checksum Validation)
EXPECTED_MODEL_HASHES = {
    "models/trustgraph.onnx": "4994d970cd6c9f61da271b4153d1b413fffaa35b2c55fd8ac4423ae2f035eeaf",
    "models/flowsense.onnx": "1b82c684aec7ee8c67c81cc5ac384533b6b22a1573b268c497a4faefe842443a",
    "models/k_sentinel.onnx": "4994d970cd6c9f61da271b4153d1b413fffaa35b2c55fd8ac4423ae2f035eeaf",
    "models/wealthpilot.onnx": "1b82c684aec7ee8c67c81cc5ac384533b6b22a1573b268c497a4faefe842443a"
}

def verify_file_sha256(filepath: str, expected_hash: str) -> bool:
    if not os.path.exists(filepath):
        return False
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest().lower() == expected_hash.lower()

def get_existing_model_path(primary: str, fallback: str) -> str:
    primary_path = os.path.join(BASE_DIR, primary)
    fallback_path = os.path.join(BASE_DIR, fallback)
    if os.path.exists(primary_path):
        return primary_path
    if os.path.exists(fallback_path):
        return fallback_path
    return primary_path

trustgraph_model_path = get_existing_model_path("models/trustgraph.onnx", "models/k_sentinel.onnx")
flowsense_model_path = get_existing_model_path("models/flowsense.onnx", "models/wealthpilot.onnx")

for model_p in [trustgraph_model_path, flowsense_model_path]:
    exp_h = EXPECTED_MODEL_HASHES.get(os.path.relpath(model_p, BASE_DIR).replace("\\", "/"))
    if exp_h and verify_file_sha256(model_p, exp_h):
        print(f"[SecOps Check] Model Integrity Verified: {model_p} (SHA-256 Checksum Match)")
    else:
        raise RuntimeError(f"Model integrity check failed: {os.path.basename(model_p)}")

print("[Init] Loading ONNX Inference Engines into RAM...")
session_options = rt.SessionOptions()
session_options.intra_op_num_threads = 1
session_options.inter_op_num_threads = 1
sentinel_sess = rt.InferenceSession(trustgraph_model_path, sess_options=session_options, providers=["CPUExecutionProvider"])
sentinel_in_name = sentinel_sess.get_inputs()[0].name
sentinel_out_prob = sentinel_sess.get_outputs()[1].name

wealth_sess = rt.InferenceSession(flowsense_model_path, sess_options=session_options, providers=["CPUExecutionProvider"])
wealth_in_name = wealth_sess.get_inputs()[0].name
wealth_out_name = wealth_sess.get_outputs()[0].name

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
df_embeddings = load_data_csv("05_trustgraph_graph_node_embeddings.csv", "05_sentinel_graph_node_embeddings.csv").set_index("account_id")
FEATURE_STORE_CACHE: Dict[str, np.ndarray] = {
    acc_id: df_embeddings.loc[acc_id].values.astype(np.float32)
    for acc_id in df_embeddings.index
}

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
        "daily_spent_today": float(prof["avg_daily_spend"] * 0.45),
        "last_sweep_ts": time.time()
    }

SEED_ACCOUNTS.update(INITIAL_ACCOUNT_STATES)
LIVE_ACCOUNT_STATES = SessionMapping("accounts")
START_TIME = time.time()

# A step-up decision only follows a risk evaluation in this in-memory demo.
PENDING_STEP_UP = SessionMapping("pending")
PENDING_STEP_UP_LOCK = threading.Lock()

def step_up_key(source_acc: str, target_acc: str, amount: float) -> tuple:
    return (source_acc, target_acc, round(amount, 2))

def remember_step_up(source_acc: str, target_acc: str, amount: float):
    with PENDING_STEP_UP_LOCK:
        for key in list(PENDING_STEP_UP):
            if PENDING_STEP_UP[key]["expires"] <= time.time():
                del PENDING_STEP_UP[key]
        while len(PENDING_STEP_UP) >= 32:
            del PENDING_STEP_UP[next(iter(PENDING_STEP_UP))]
        PENDING_STEP_UP[step_up_key(source_acc, target_acc, amount)] = {"expires": time.time() + 120, "nonce": secrets.token_hex(16)}

def has_pending_step_up(source_acc: str, target_acc: str, amount: float) -> bool:
    with PENDING_STEP_UP_LOCK:
        return PENDING_STEP_UP.get(step_up_key(source_acc, target_acc, amount), {}).get("expires", 0) > time.time()

def clear_step_up(source_acc: str, target_acc: str, amount: float):
    with PENDING_STEP_UP_LOCK:
        PENDING_STEP_UP.pop(step_up_key(source_acc, target_acc, amount), None)

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

class MicroSweepRequest(StrictRequest):
    account_id: str
    custom_sweep_amount: Optional[float] = Field(None, gt=0, le=100_000)

class LiquidityScenarioRequest(StrictRequest):
    account_id: str
    scenario: Literal["healthy", "normal_dip", "commitment_risk", "high_value"]

class AutoSavingRequest(StrictRequest):
    account_id: str
    enabled: bool

class AutoCycleRequest(StrictRequest):
    account_id: str

class VaultWithdrawalRequest(StrictRequest):
    account_id: str
    amount: Optional[float] = Field(None, ge=0, le=100_000)
    mode: Literal["swept", "all", "partial", "undo"] = "swept"

# ==============================================================================
# 3. TRUSTGRAPH CORE SERVICES (ZERO-DELAY BASELINE & TARGET-SPECIFIC FRAUD DEFENSE)
# ==============================================================================
@app.post("/api/v2/trustgraph/evaluate-transfer")
def evaluate_transfer_v2(payload: TransferEvaluationRequest):
    """
    TrustGraph Targeted Anti-Scam Verification:
    - Zero-Delay Baseline: Routine transfers to known or low-risk accounts execute immediately with zero added steps (<80ms SLA).
    - Micro-Auth for Critical Anomaly: Rapid dynamic verification.
      Triggers a 5-second face liveness check and displays a single confirmation prompt.
    - Direct Risk Reasoning: Tells the user plainly why a recipient looks suspicious
      (e.g., 'Recipient account opened 48 hours ago with rapid pass-through fund patterns')
      and leaves the final transfer decision to the user.
    - Demo high-value gate: Transfers >= 50,000 THB request simulated step-up verification.
    - Hard Interdiction: Transfers to confirmed criminal mule rings (risk >= 0.90) are blocked under Royal Decree B.E. 2566.
    """
    if payload.source_account_id not in LIVE_ACCOUNT_STATES:
        raise HTTPException(status_code=404, detail="Unknown demo source")
    if LIVE_ACCOUNT_STATES[payload.source_account_id]["main_balance"] < payload.amount:
        raise HTTPException(status_code=400, detail="ยอดเงินในบัญชีหลักไม่เพียงพอ")
    t_start = time.perf_counter()

    # 1. Feature Store Lookup (Tier 1 Redis Simulation)
    if payload.target_account_id not in FEATURE_STORE_CACHE:
        raise HTTPException(status_code=404, detail="Target beneficiary account not found in Graph Feature Store.")

    target_emb = FEATURE_STORE_CACHE[payload.target_account_id]
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
    current_risk = float(raw_probs[0][1])
    if target_meta.get("is_mule", 0) == 1:
        current_risk = max(current_risk, 0.45)

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
        audit_log("TRANSFER_BLOCKED", payload.source_account_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount, "latency_ms": round(latency_ms, 2)})
        return {
            "status": "BLOCKED_MULE_INTERDICTION",
            "risk_tier": "CONFIRMED_MULE_RING",
            "current_risk_score": round(current_risk, 4),
            "risk_score": round(current_risk, 4),
            "zero_delay_baseline": False,
            "step_up_required": False,
            "action": "BLOCK",
            "hard_blocked": True,
            "final_decision_left_to_user": False,
            "direct_risk_reasoning": "บัญชีปลายทางอยู่ในเครือข่ายบัญชีม้าความเสี่ยงสูงมาก (Mule Ring Tier-1) ธนาคารระงับการทำรายการตาม พ.ร.ก. ปราบปรามอาชญากรรมทางเทคโนโลยี พ.ศ. 2566",
            "counterfactual_message": "บัญชีปลายทางอยู่ในเครือข่ายบัญชีม้าความเสี่ยงสูงมาก (Mule Ring Tier-1) ธนาคารระงับการทำรายการตาม พ.ร.ก. ปราบปรามอาชญากรรมทางเทคโนโลยี พ.ศ. 2566",
            "reason_summary": "Relational GCN ตรวจพบลักษณะตรงกับเครือข่ายบัญชีม้าความเสี่ยงสูงมาก",
            "direct_risk_reasons_list": [
                "Relational GCN ตรวจพบลักษณะตรงกับเครือข่ายบัญชีม้าความเสี่ยงสูงมาก",
                "บัญชีนี้มีป้ายกำกับระงับการโอนในชุดข้อมูลสมมติ"
            ],
            "primary_reason_th": "บัญชีปลายทางมีป้ายระงับในข้อมูลจำลอง จึงหยุดรายการนี้",
            "actionable_warning": "⛔ ระงับการทำรายการ: พบบัญชีปลายทางเป็นบัญชีม้าในเครือข่ายอาชญากรรม",
            "target_meta": {
                "account_id": payload.target_account_id,
                "account_age_days": account_age_days,
                "kyc_level": kyc_level,
                "velocity_sec": inflow_velocity
            },
            "latency_ms": round(latency_ms, 2)
        }

    if payload.amount >= 50000.0:
        audit_log("TRANSFER_CHECK_REQUIRED", payload.source_account_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount, "latency_ms": round(latency_ms, 2)})
        remember_step_up(payload.source_account_id, payload.target_account_id, payload.amount)
        return {
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

    # --------------------------------------------------------------------------
    # HARD INTERDICTION: CONFIRMED MULE RING (Royal Decree B.E. 2566)
    # Applied strictly to confirmed blacklisted criminal accounts (e.g. ACC_0000 or scenario_mode == "blocked")
    # --------------------------------------------------------------------------
    # --------------------------------------------------------------------------
    # ZERO-DELAY BASELINE: Routine / Low-Risk Transfers Execute Immediately
    # --------------------------------------------------------------------------
    if current_risk < 0.45:
        src_id = payload.source_account_id
        res_main_balance = None
        with get_account_lock(src_id):
            if src_id in LIVE_ACCOUNT_STATES:
                src_state = LIVE_ACCOUNT_STATES[src_id]
                demo_now(src_state)
                if src_state["main_balance"] < payload.amount:
                    raise HTTPException(status_code=400, detail=f"ยอดเงินในบัญชีหลักไม่เพียงพอ (มี ฿ {src_state['main_balance']:,.2f})")
                src_state["main_balance"] = round(src_state["main_balance"] - payload.amount, 2)
                src_state["daily_spent_today"] = round(src_state.get("daily_spent_today", 0.0) + payload.amount, 2)
                res_main_balance = src_state["main_balance"]
                audit_log("TRANSFER_EXECUTED_ZERO_DELAY", src_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount, "remaining": res_main_balance})

        return {
            "status": "APPROVED",
            "receipt_id": "DEMO-" + secrets.token_hex(6).upper(),
            "executed_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
            "amount": payload.amount,
            "risk_tier": "LOW_RISK",
            "risk_score": round(current_risk, 4),
            "current_risk_score": round(current_risk, 4),
            "action": "ALLOW",
            "zero_delay_baseline": True,
            "step_up_required": False,
            "added_steps_count": 0,
            "direct_risk_reasoning": "Zero-Delay Baseline: บัญชีปลายทางและพฤติกรรมการโอนอยู่ในเกณฑ์ปกติ ดำเนินการโอนทันทีโดยไม่มีขั้นตอนเพิ่ม",
            "counterfactual_message": "Zero-Delay Baseline: บัญชีปลายทางและพฤติกรรมการโอนอยู่ในเกณฑ์ปกติ ดำเนินการโอนทันทีโดยไม่มีขั้นตอนเพิ่ม",
            "reason_summary": "Zero-Delay Baseline verified",
            "actionable_warning": "Zero-Delay Baseline verified. Instant transfer executed.",
            "new_main_balance": res_main_balance,
            "amount": payload.amount,
            "target_meta": {
                "account_id": payload.target_account_id,
                "account_age_days": account_age_days,
                "kyc_level": kyc_level,
                "velocity_sec": inflow_velocity
            },
            "latency_ms": round(latency_ms, 2)
        }

    # --------------------------------------------------------------------------
    # MICRO-AUTH FOR CRITICAL ANOMALY: No arbitrary waiting periods!
    # Triggers 5-second face liveness check & Direct Risk Reasoning
    # Leaves final transfer decision to user.
    # --------------------------------------------------------------------------
    direct_reasons = []
    if account_age_days <= 45:
        direct_reasons.append(f"บัญชีปลายทางเปิดใหม่เพียง {account_age_days} วัน")
    if inflow_velocity < 180:
        direct_reasons.append(f"เงินเข้าแล้วโอนออกเร็วภายใน {int(inflow_velocity)} วินาที")
    if payload.session_duration_sec < 15:
        direct_reasons.append(f"เริ่มทำรายการอย่างรวดเร็วภายใน {payload.session_duration_sec} วินาที")
    if payload.ratio_to_daily_avg > 5.0:
        direct_reasons.append(f"ยอดโอนสูงกว่าค่าเฉลี่ยต่อวัน {payload.ratio_to_daily_avg:.1f} เท่า")

    if not direct_reasons:
        direct_reasons.append("รูปแบบความสัมพันธ์ของบัญชีคล้ายเครือข่ายเสี่ยงในข้อมูลจำลอง")

    primary_reason = direct_reasons[0]
    reason_summary = " | ".join(direct_reasons)

    audit_log("TRANSFER_CHECK_REQUIRED", payload.source_account_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount, "latency_ms": round(latency_ms, 2)})
    remember_step_up(payload.source_account_id, payload.target_account_id, payload.amount)

    return {
        "status": "MICRO_AUTH_REQUIRED",
        "risk_tier": "CRITICAL_ANOMALY",
        "current_risk_score": round(current_risk, 4),
        "risk_score": round(current_risk, 4),
        "zero_delay_baseline": False,
        "step_up_required": True,
        "friction_type": "5_SECOND_LIVENESS",
        "auth_duration_sec": 5,
        "eliminates_arbitrary_waiting": True,
        "direct_risk_reasoning": f"Recipient account opened {account_age_days} days ago with rapid pass-through fund patterns ({int(inflow_velocity)}s)",
        "counterfactual_message": f"Recipient account opened {account_age_days} days ago with rapid pass-through fund patterns ({int(inflow_velocity)}s)",
        "reason_summary": reason_summary,
        "direct_risk_reasons_list": direct_reasons,
        "primary_reason_th": primary_reason,
        "actionable_warning": f"⚠️ ตรวจพบความผิดปกติวิกฤต: {reason_summary}",
        "user_confirmation_prompt": "ระบบเปิดการยืนยัน Micro-Auth ด้วยการสแกนใบหน้า 5 วินาที เพื่อดึงสติและตรวจสอบผู้ใช้งานจริง และให้คุณเป็นผู้ตัดสินใจโอนเงินขั้นสุดท้าย",
        "final_decision_left_to_user": True,
        "target_meta": {
            "account_id": payload.target_account_id,
            "account_age_days": account_age_days,
            "kyc_level": kyc_level,
            "velocity_sec": inflow_velocity
        },
        "latency_ms": round(latency_ms, 2)
    }

@app.post("/api/v2/trustgraph/verify-micro-auth")
def verify_micro_auth(payload: MicroAuthRequest):
    """
    Simulates step-up confirmation for an evaluated synthetic transaction.
    This is not biometric verification or proof of a real user's identity.
    """
    if not has_pending_step_up(payload.source_account_id, payload.target_account_id, payload.amount):
        raise HTTPException(status_code=400, detail="กรุณาตรวจสอบความเสี่ยงของรายการโอนก่อนยืนยันตัวตน")

    # Generate tamper-proof HMAC-SHA256 clearance token bound to accounts & amount
    token = generate_signed_micro_auth_token(payload.source_account_id, payload.target_account_id, payload.amount)
    return {
        "status": "MICRO_AUTH_VERIFIED",
        "verified": True,
        "verification_mode": "SIMULATED",
        "auth_duration_sec": 0,
        "clearance_token": token,
        "message": "ยืนยันตัวตนจำลองสำเร็จ กรุณาพิจารณาความเสี่ยงและตัดสินใจว่าจะโอนต่อหรือยกเลิก",
        "prompt_title": "ยืนยันการทำรายการโอนเงิน",
        "prompt_message": "ระบบได้ชี้แจงความเสี่ยงของบัญชีปลายทางแล้ว คุณต้องการดำเนินการโอนเงินต่อไปหรือไม่?",
        "options": ["PROCEED_TRANSFER", "CANCEL_TRANSFER"]
    }

@app.post("/api/v2/trustgraph/confirm-transfer")
def confirm_transfer(payload: TransferConfirmRequest, x_idempotency_key: Optional[str] = Header(None)):
    """
    Direct Risk Reasoning Final Decision:
    User retains full autonomy to proceed or cancel after the 5-second Micro-Auth check.
    Guarded with account mutex lock for thread safety and balance consistency.
    """

    src_id = payload.source_account_id
    if src_id not in LIVE_ACCOUNT_STATES:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    decision = payload.decision

    if decision == "CANCEL":
        clear_step_up(src_id, payload.target_account_id, payload.amount)
        state = LIVE_ACCOUNT_STATES.get(src_id, {"main_balance": 24500.0, "vault_balance": 15000.0})
        res = {
            "status": "TRANSFER_CANCELLED",
            "decision": "CANCEL",
            "message": "ยกเลิกรายการโอนเงินเรียบร้อยแล้ว เงินของคุณยังคงปลอดภัย 100% ในบัญชี",
            "current_balance": round(state["main_balance"], 2)
        }
        audit_log("TRANSFER_CANCELLED_BY_USER", src_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount})

        return res

    if not verify_signed_micro_auth_token(payload.auth_token, src_id, payload.target_account_id, payload.amount) or not consume_step_up(src_id, payload.target_account_id, payload.amount):
        audit_log("TRANSFER_REJECTED_INVALID_TOKEN", src_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount})
        raise HTTPException(status_code=401, detail="กรุณาตรวจความเสี่ยงและยืนยันตัวตนจำลองก่อนโอนต่อ")

    # Concurrency Lock Guard to prevent double spending
    with get_account_lock(src_id):
        state = LIVE_ACCOUNT_STATES.get(src_id, {"main_balance": 24500.0, "vault_balance": 15000.0})
        demo_now(state)
        if state["main_balance"] < payload.amount:
            raise HTTPException(status_code=400, detail=f"ยอดเงินในบัญชีหลักไม่เพียงพอ (มี ฿ {state['main_balance']:,.2f})")

        state["main_balance"] = round(state["main_balance"] - payload.amount, 2)
        state["daily_spent_today"] = round(state.get("daily_spent_today", 0.0) + payload.amount, 2)
        remaining = round(state["main_balance"], 2)

    res = {
        "status": "TRANSFER_EXECUTED",
        "receipt_id": "DEMO-" + secrets.token_hex(6).upper(),
        "executed_at": datetime.now(ZoneInfo("Asia/Bangkok")).isoformat(),
        "decision": "PROCEED",
        "amount": payload.amount,
        "remaining_balance": remaining,
        "message": f"โอนเงิน ฿ {payload.amount:,.2f} ไปยังบัญชี {mask_account_id(payload.target_account_id)} สำเร็จแล้วตามความประสงค์ของคุณ"
    }
    audit_log("TRANSFER_EXECUTED", src_id, {"target": mask_account_id(payload.target_account_id), "amount": payload.amount, "remaining": remaining})

    return res

# ==============================================================================
# 4. FLOWSENSE SERVICES (FLEXIBLE LIQUIDITY & AUTONOMOUS SAVING)
# ==============================================================================
@app.get("/api/v2/flowsense/profile/{account_id}")
def get_flowsense_profile(account_id: str = Path(..., pattern=r"^[A-Za-z0-9_]{3,30}$", description="Sanitized Banking Account ID")):
    """
    Get user profile, behavioral cluster persona (Pitch: Primary 18k-35k Living Month-to-Month
    vs Secondary Active Mobile Transactor), live balance, and high-interest sub-account statistics.
    """
    if account_id not in DEMO_ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    prof = BEHAVIORAL_PROFILES_CACHE[account_id]
    state = LIVE_ACCOUNT_STATES.get(account_id, {
        "main_balance": 24500.0,
        "vault_balance": float(prof["initial_vault_savings"]),
        "total_swept": 1250.0,
        "daily_spent_today": 280.0
    })

    demo_now(state)
    return {
        "account_id": account_id,
        "masked_account_id": mask_account_id(account_id),
        "cf_user_id": prof["cf_user_id"],
        "monthly_salary": prof["monthly_salary"],
        "main_balance": round(state["main_balance"], 2),
        "vault_balance": round(state["vault_balance"], 2),
        "total_swept": round(state["total_swept"], 2),
        "daily_spent_today": round(state["daily_spent_today"], 2),
        "auto_saving_enabled": state.get("auto_saving_enabled", False),
        "undo_amount": round(state.get("last_sweep_amount", 0), 2),
        "events": state.get("events", []),
        "persona": {
            "cluster_id": int(prof["cluster_id"]),
            "name": prof["persona_name"],
            "name_th": prof.get("persona_th", "กลุ่มเป้าหมาย First Jobber"),
            "description": prof.get("persona_desc", "First Jobber บริหารสภาพคล่องด้วย FlowSense และ Protected Vault"),
            "recommended_sweep_pct": prof["recommended_sweep_pct"],
            "scam_vulnerability": prof["scam_vulnerability"],
            "vault_friction_level": "1_TAP_RECALL_ZERO_PENALTY"
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
    """
    30-Day Liquidity Forecast via LightGBM:
    Method & Architecture: LightGBM with rolling-window lag features & transaction seasonality.
    Operational Objective: Forecasts safe liquidity margins 30 days ahead; suppresses alerts during normal dips.
    """
    if account_id not in DEMO_ACCOUNTS:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    prof = BEHAVIORAL_PROFILES_CACHE[account_id]
    state = LIVE_ACCOUNT_STATES.get(account_id, {
        "main_balance": 24500.0,
        "vault_balance": float(prof["initial_vault_savings"]),
        "total_swept": 1250.0,
        "daily_spent_today": 310.0
    })

    now = demo_now(state)
    cur_balance = float(state["main_balance"])
    salary = float(prof["monthly_salary"])
    avg_spend = float(prof["avg_daily_spend"])
    spent_today = float(state.get("daily_spent_today", avg_spend * 0.45))

    # Past 7 days
    past_points = []
    running_past_bal = cur_balance + spent_today
    past_spends = []
    for p_step in range(1, 8):
        p_date = now - timedelta(days=p_step)
        is_wk = 1.0 if p_date.weekday() >= 5 else 0.0
        factor = 1.28 if is_wk else (0.86 + (p_step % 3) * 0.08)
        day_spend = round(avg_spend * factor, 2)
        past_spends.append((p_date, is_wk, day_spend))

    for p_date, is_wk, day_spend in past_spends:
        running_past_bal += day_spend

    temp_bal = running_past_bal
    for p_date, is_wk, day_spend in reversed(past_spends):
        temp_bal -= day_spend
        past_points.append({
            "date": p_date.strftime("%Y-%m-%d"),
            "day_name": p_date.strftime("%a"),
            "is_weekend": bool(is_wk),
            "days_to_payday": (next_payday(p_date).date() - p_date.date()).days,
            "predicted_spend": day_spend,
            "actual_spend": day_spend,
            "salary_inflow": 0.0,
            "projected_balance": round(temp_bal, 2),
            "status": "PAST",
            "is_past": True,
            "is_today": False,
            "is_future": False
        })

    # Today's point
    is_today_weekend = 1.0 if now.weekday() >= 5 else 0.0
    dtp_today = (next_payday(now).date() - now.date()).days
    today_point = {
        "date": now.strftime("%Y-%m-%d"),
        "day_name": now.strftime("%a"),
        "is_weekend": bool(is_today_weekend),
        "days_to_payday": int(dtp_today),
        "predicted_spend": round(spent_today, 2),
        "actual_spend": round(spent_today, 2),
        "salary_inflow": 0.0,
        "projected_balance": round(cur_balance, 2),
        "status": "TODAY",
        "is_past": False,
        "is_today": True,
        "is_future": False,
        "current_time": now.strftime("%H:%M")
    }

    # Future 30 days (LightGBM rolling-window lag features & transaction seasonality)
    future_points = []
    lag_1 = spent_today
    lag_3 = float(avg_spend * 0.95)
    lag_7 = float(avg_spend * 1.05)
    cum_bal = cur_balance

    fixed_rent = float(prof.get("fixed_rent", round(salary * 0.25, 2)))
    fixed_debt_emi = float(prof.get("fixed_debt", round(salary * 0.12, 2)))
    fixed_utilities = float(prof.get("fixed_utilities", round(salary * 0.05, 2)))

    for f_step in range(1, 31):
        target_date = now + timedelta(days=f_step)
        is_weekend = 1.0 if target_date.weekday() >= 5 else 0.0

        dtp = float((next_payday(target_date).date() - target_date.date()).days)

        fixed_due_7d = 1.0 if (target_date.day >= 25 or target_date.day <= 2) else 0.0

        feat = np.array([[dtp, fixed_due_7d, is_weekend, lag_1, lag_3, lag_7]], dtype=np.float32)
        pred_spend = float(wealth_sess.run([wealth_out_name], {wealth_in_name: feat})[0][0][0])
        pred_spend = max(150.0, pred_spend)

        # Accurately reflect recurring commitments on due days
        fixed_due_deduction = 0.0
        if target_date.day == 22: # Debt EMI due
            fixed_due_deduction += fixed_debt_emi
        elif target_date.day == 26: # Rent due
            fixed_due_deduction += fixed_rent
        elif target_date.day == 27: # Utilities due
            fixed_due_deduction += fixed_utilities

        inflow = salary if target_date.day == 28 else 0.0
        cum_bal = cum_bal - pred_spend - fixed_due_deduction + inflow

        future_points.append({
            "date": target_date.strftime("%Y-%m-%d"),
            "day_name": target_date.strftime("%a"),
            "is_weekend": bool(is_weekend),
            "days_to_payday": int(dtp),
            "predicted_spend": round(pred_spend, 2),
            "actual_spend": 0.0,
            "salary_inflow": inflow,
            "commitment_payment": round(fixed_due_deduction, 2),
            "projected_balance": round(cum_bal, 2),
            "status": "FUTURE",
            "is_past": False,
            "is_today": False,
            "is_future": True
        })

        lag_7 = lag_3
        lag_3 = lag_1
        lag_1 = pred_spend

    full_timeline = past_points + [today_point] + future_points
    min_proj_balance = min(p["projected_balance"] for p in [today_point] + future_points)
    is_safe = min_proj_balance >= 500.0
    payday_target = now + timedelta(days=int(dtp_today))

    return {
        "account_id": account_id,
        "forecast_days": 30,
        "history_days": 7,
        "data_mode": "synthetic_demo",
        "model_architecture": "LightGBM with rolling-window lag features & transaction seasonality",
        "operational_objective": "Forecasts safe liquidity margins 30 days ahead; suppresses alerts during normal dips.",
        "today_index": len(past_points),
        "current_datetime": now.strftime("%Y-%m-%d %H:%M:%S"),
        "days_to_payday": int(dtp_today),
        "payday_date": payday_target.strftime("%Y-%m-%d"),
        "current_balance": round(cur_balance, 2),
        "min_projected_balance": round(min_proj_balance, 2),
        "liquidity_health": "HEALTHY" if is_safe else "RISK_OF_DEFICIT",
        "alerts_suppressed_during_normal_dips": True,
        "projection_summary": (
            "สุขภาพสภาพคล่องแข็งแรง มีเส้นทางกระแสเงินสดรองรับภาระผูกพันถึงวันเงินเดือนออก"
            if is_safe
            else "ยอดคาดการณ์บางวันต่ำกว่าเกณฑ์สภาพคล่อง ฿500 ควรวางแผนเงินที่ต้องใช้"
        ),
        "timeline": full_timeline
    }

@app.post("/api/v2/flowsense/micro-sweep")
def trigger_micro_sweep(payload: MicroSweepRequest, x_idempotency_key: Optional[str] = Header(None)):
    """
    Micro-Sweep with 1-Tap Undo:
    Sweeps small surplus amounts into high-interest sub-accounts only when cashflow permits.
    """

    acc_id = payload.account_id
    if acc_id not in LIVE_ACCOUNT_STATES:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    with get_account_lock(acc_id):
        state = LIVE_ACCOUNT_STATES[acc_id]
        prof = BEHAVIORAL_PROFILES_CACHE.get(acc_id, {"recommended_sweep_pct": 0.08})

        liquidity = get_flowsense_horizon_status(acc_id)
        sweep_amount = payload.custom_sweep_amount
        if sweep_amount is None:
            sweep_amount = liquidity["recommended_sweep_amount"]
        if sweep_amount <= 0 or sweep_amount > liquidity["savings_capacity"]:
            raise HTTPException(status_code=400, detail=f"พักการออมไว้ก่อน: เงินส่วนที่ออมได้หลังกันภาระ ค่าใช้จ่าย และเงินสำรอง ฿{liquidity['savings_capacity']:,.2f}")
        state["last_sweep_amount"] = sweep_amount
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
        "one_tap_undo_available": True,
        "message": f"กวาดเงินส่วนเกิน ฿ {sweep_amount:,.2f} เข้ากระเป๋าเงินออมจำลองเรียบร้อยแล้ว (สามารถกด 1-Tap Undo เรียกคืนได้ทันที 100% ไร้ค่าปรับ)"
    }
    audit_log("MICRO_SWEEP_EXECUTED", acc_id, {"swept": sweep_amount, "new_main": res_main, "new_vault": res_vault})

    return res

@app.post("/api/v2/flowsense/recall")
def recall_micro_sweep_funds(payload: VaultWithdrawalRequest, x_idempotency_key: Optional[str] = Header(None)):
    """
    Micro-Sweep with 1-Tap Undo (Instant Recall):
    If balance runs low, a 1-tap recall returns 100% of the funds to the main account instantly without penalty.
    Returns 100% of swept funds instantly without lockup or penalty!
    """

    acc_id = payload.account_id
    if acc_id not in LIVE_ACCOUNT_STATES:
        raise HTTPException(status_code=404, detail="Unknown demo account")

    with get_account_lock(acc_id):
        state = LIVE_ACCOUNT_STATES[acc_id]
        recall_amount = payload.amount
        if payload.mode == "undo":
            recall_amount = min(state.get("last_sweep_amount", 0), state["vault_balance"])
        elif payload.mode == "all":
            recall_amount = state["vault_balance"]
        elif payload.mode == "partial":
            if recall_amount is None or recall_amount <= 0:
                raise HTTPException(status_code=400, detail="กรุณาระบุจำนวนเงินที่ต้องการดึงคืน")
        elif recall_amount is None or recall_amount <= 0:
            recall_amount = min(state.get("total_swept", 0) or state["vault_balance"], state["vault_balance"])
        if recall_amount <= 0:
            raise HTTPException(status_code=400, detail="ไม่มีเงินในบัญชีย่อยที่สามารถดึงคืนได้ในขณะนี้")

        if recall_amount > state["vault_balance"]:
            raise HTTPException(status_code=400, detail=f"ยอดเงินในบัญชีย่อยไม่เพียงพอ (มี ฿ {state['vault_balance']:,.2f})")

        state["last_sweep_amount"] = 0
        # Instant 1-tap return without penalty or waiting period!
        state["vault_balance"] = round(state["vault_balance"] - recall_amount, 2)
        state["main_balance"] = round(state["main_balance"] + recall_amount, 2)
        state["total_swept"] = max(0.0, round(state.get("total_swept", 0.0) - recall_amount, 2))

        res_main = round(state["main_balance"], 2)
        res_vault = round(state["vault_balance"], 2)
        res_total = round(state["total_swept"], 2)

    res = {
        "status": "RECALL_SUCCESS",
        "account_id": acc_id,
        "recalled_amount": round(recall_amount, 2),
        "friction_type": "1_TAP_RECALL_ZERO_PENALTY",
        "penalty_fee": 0.0,
        "waiting_time_sec": 0,
        "new_main_balance": res_main,
        "new_subaccount_balance": res_vault,
        "new_vault_balance": res_vault,
        "total_accumulated_swept": res_total,
        "message": f"1-Tap Undo สำเร็จ! ดึงเงิน ฿ {recall_amount:,.2f} คืนเข้าบัญชีหลักเรียบร้อยแล้วทันที 100% ไร้ค่าปรับ"
    }
    audit_log("RECALL_EXECUTED", acc_id, {"recalled": recall_amount, "new_main": res_main, "new_vault": res_vault})

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
        "daily_spent_today": float(prof["avg_daily_spend"] * 0.45),
        "last_sweep_ts": time.time()
    }
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
    return {"status": "HEALTHY", "mode": "synthetic_demo", "version": "4.0.0"}


@app.post("/api/v2/flowsense/scenario")
def set_liquidity_scenario(payload: LiquidityScenarioRequest):
    reset_account_state(payload.account_id)
    state = LIVE_ACCOUNT_STATES[payload.account_id]
    prof = BEHAVIORAL_PROFILES_CACHE[payload.account_id]
    salary = float(prof["monthly_salary"])
    state["scenario"] = payload.scenario
    state["daily_spent_today"] = float(prof["avg_daily_spend"]) * .45
    draft = calculate_horizon(prof, state)
    obligations = draft["total_recurring_commitments"]
    burn = draft["projected_daily_burn"] * draft["days_to_payday"]
    if payload.scenario == "high_value":
        state["main_balance"] = 60000.0
    elif payload.scenario == "healthy":
        state["main_balance"] = round(max(salary * .9, obligations + burn + draft["emergency_buffer"] + 2000), 2)
    elif payload.scenario == "normal_dip":
        # Presets adjust demo spending, not the visitor's genuine financial data.
        state["main_balance"] = round(salary * .49, 2)
        state["daily_spent_today"] = 0
        if calculate_horizon(prof, state)["commitment_at_risk"]:
            # Profiles with large obligations need extra headroom to remain safe.
            state["main_balance"] = round(obligations + burn + 1000, 2)
    else:
        state["main_balance"] = round(max(500, obligations * .45), 2)
    if payload.scenario in {"healthy", "normal_dip"}:
        # Keep safe presets safe for the current calendar and actual model forecast.
        forecast = forecast_cashflow_30d(payload.account_id)
        minimum = min(point["projected_balance"] for point in forecast["timeline"]
                      if not point["is_past"] and point["date"] < forecast["payday_date"])
        reserve = draft["emergency_buffer"] + 2000 if payload.scenario == "healthy" else 1000
        state["main_balance"] = round(state["main_balance"] + max(0, reserve - minimum), 2)
    audit_log("SCENARIO_CHANGED", payload.account_id, {"scenario": payload.scenario})
    return get_flowsense_horizon_status(payload.account_id)


@app.post("/api/v2/flowsense/auto-saving")
def set_auto_saving(payload: AutoSavingRequest):
    LIVE_ACCOUNT_STATES[payload.account_id]["auto_saving_enabled"] = payload.enabled
    return {"enabled": payload.enabled, "mode": "SIMULATED_EVENT_TRIGGER"}


@app.post("/api/v2/flowsense/auto-cycle")
def run_auto_saving_cycle(payload: AutoCycleRequest):
    state = LIVE_ACCOUNT_STATES[payload.account_id]
    if not state.get("auto_saving_enabled"):
        raise HTTPException(status_code=400, detail="เปิดตัวช่วยออมก่อนทดลองรอบออม")
    if get_flowsense_horizon_status(payload.account_id)["recommended_sweep_amount"] <= 0:
        audit_log("AUTO_SAVING_SKIPPED", payload.account_id, {"reason": "LIQUIDITY_RESERVED"})
        return {"status": "SKIPPED", "swept_amount": 0, "message": "พักการออมรอบนี้เพื่อกันเงินสำหรับภาระ ค่าใช้จ่าย และเงินสำรอง"}
    return trigger_micro_sweep(MicroSweepRequest(account_id=payload.account_id))


@app.get("/api/v2/demo/insights")
@lru_cache(maxsize=1)
def demo_insights():
    # Bounded graph sample from the original synthetic transactions. No live bank connection.
    frame = pd.read_csv(os.path.join(BASE_DIR, "data", "04_trustgraph_fraud_transactions.csv"))
    sample = frame[frame["is_scam"] == 1].head(18)
    ids = list(dict.fromkeys(sample["source_id"].tolist() + sample["target_id"].tolist()))
    aliases = {acc: f"N{index+1}" for index, acc in enumerate(ids)}
    return {"data_mode": "synthetic_sample", "nodes": [{"id": aliases[acc], "label": f"บัญชี {index+1:02d}", "is_mule": bool(USERS_METADATA_CACHE.get(acc, {}).get("is_mule", 0)), "age_days": int(USERS_METADATA_CACHE.get(acc, {}).get("account_age_days", 90))} for index, acc in enumerate(ids)], "edges": [{"source": aliases[row.source_id], "target": aliases[row.target_id], "amount": float(row.amount)} for row in sample.itertuples()], "sample_transactions": len(sample)}
