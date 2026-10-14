# K · FlowSense × TrustGraph — Interactive Web Prototype

[![Live Demo](https://img.shields.io/badge/Render-Live_Demo-00C7B7?style=for-the-badge&logo=render&logoColor=white)](https://k-web-application.onrender.com)
[![FastAPI](https://img.shields.io/badge/FastAPI-4.0.0-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![React](https://img.shields.io/badge/React-18.3-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://react.dev)
[![ONNX Runtime](https://img.shields.io/badge/ONNX_Runtime-1.30-005CED?style=for-the-badge&logo=onnx&logoColor=white)](https://onnxruntime.ai)
[![License](https://img.shields.io/badge/Status-Independent_Prototype-green?style=for-the-badge)](#ข้อจำกัดและขอบเขตของต้นแบบ)

เว็บแอปพลิเคชันต้นแบบอิสระสำหรับจำลองประสบการณ์ผู้ใช้ (UX Concept Prototype) โดยผสาน 2 นวัตกรรม AI ทางการเงิน:
1. **FlowSense**: ระบบคาดการณ์สภาพคล่องล่วงหน้า 30 วัน และช่วยออมเงินอัตโนมัติเฉพาะส่วนเกิน (Surplus-only Micro-Sweep)
2. **TrustGraph**: ระบบประเมินความเสี่ยงบัญชีปลายทางและตรวจจับบัญชีม้าก่อนโอน พร้อมระบบยืนยันตัวตนจำลอง (Simulated Micro-Auth Step-Up)

ออกแบบ UI/UX ตามแนวคิดโมบายแบงก์กิ้งชั้นนำ (K+ / MAKE by KBank style) รองรับทั้งหน้าจอมือถือและเดสก์ท็อป

---

## 🌐 เข้าชมเว็บเดโมสด (Live Demo)

- **URL เว็บไซต์:** [https://k-web-application.onrender.com](https://k-web-application.onrender.com)
- **API Health Check:** [https://k-web-application.onrender.com/api/v2/health](https://k-web-application.onrender.com/api/v2/health)

> [!TIP]
> **Zero Cold-Start:** ระบบนี้ตั้งค่า Keep-Awake Ping ไว้ทุก 10 นาทีผ่าน Cron-job ทำให้เซิร์ฟเวอร์ตื่นตลอด 24 ชั่วโมง เปิดใช้งานได้รวดเร็วทันทีโดยไม่ต้องรอ Cold Start

---

## ✨ ฟีเจอร์เด่นในระบบ

### 1. FlowSense (คาดการณ์สภาพคล่องและเงินออมยืดหยุ่น)
- **30-Day Liquidity Forecast:** กราฟจำลองกระแสเงินสดล่วงหน้า 30 วัน วันนี้ และข้อมูลย้อนหลัง 7 วัน ด้วยโมเดล ONNX (`flowsense.onnx`)
- **Status Horizon & Runway Health:** แถบประเมินสุขภาพการเงินและขีดจำกัดการใช้จ่ายรายวันที่ปลอดภัย (Daily Safe Limit)
- **Normal-Dip Suppression:** ระบบอัจฉริยะไม่แจ้งเตือนเมื่อเงินลดลงตามรายจ่ายปกติ แต่จะแจ้งเตือนทันทีเมื่อมีความเสี่ยงที่ภาระประจำ (Commitment at Risk) จะไม่พอจ่าย
- **Surplus-Only Micro-Sweep:** แนะนำการย้ายเงินส่วนเกินเข้ากระเป๋าเงินออม (Vault) โดยไม่กระทบค่าใช้จ่ายจำเป็น
- **1-Tap Undo & Immediate Recall:** ดึงเงินกลับจากกระเป๋าออมเข้าบัญชีหลักได้ทันที หรือกดยกเลิกการออมล่าสุดได้ด้วยปุ่มเดียว

### 2. TrustGraph (วิเคราะห์ความเสี่ยงก่อนโอนเงิน)
- **Real-Time Mule & Fraud Risk Scoring:** ประเมินความเสี่ยงด้วยโมเดล Graph Embedding ONNX (`trustgraph.onnx`) แบบ Sub-second latency
- **Explainable AI Risk Reasoning:** แจ้งเหตุผลและปัจจัยความเสี่ยงเป็นภาษาไทยที่เข้าใจง่าย เช่น บัญชีเพิ่งเปิดใหม่, ยอดโอนผิดปกติจากพฤติกรรมเดิม, หรือพฤติกรรมการโอนเงินแบบต้องสงสัย
- **Simulated Micro-Auth (5s Step-Up):** ระบบจำลองการตรวจจับใบหน้า/Liveness Detection 5 วินาที พร้อมออก Clearance Token แบบมีอายุจำกัด (HMAC-SHA256 TTL 120s)
- **Blocked Mule Interdiction:** ระบบระงับการโอนไปยังบัญชีม้าที่ถูกขึ้นบัญชีดำทันทีโดยไม่ตัดเงิน
- **Downloadable E-Slip:** สามารถดาวน์โหลดสลิปจำลอง (Text Receipt) หลังทำรายการสำเร็จ

### 3. Persona Switching & Data Lab
- เลือกทดสอบโปรไฟล์จำลองได้ 3 แบบตามรูปแบบรายรับ-รายจ่าย:
  - **คุณเมย์ (วัยเริ่มทำงาน):** รายได้ปานกลาง รายจ่ายคงที่
  - **คุณกอล์ฟ (ฟรีแลนซ์/เจ้าของกิจการ):** รายได้ไม่สม่ำเสมอ กระแสเงินสดผันผวน
  - **คุณแอน (พนักงานประจำ/มีภาระครอบครัว):** เงินเดือนสูง มีภาระผ่อนประจำหลายรายการ
- **Data & SecOps Lab:** สำรวจเครือข่ายธุรกรรมจำลอง 18 รายการ, กราฟโหนดสัมพันธ์, และเครื่องคำนวณจำลองผลการออม (CASA Scenario Calculator)

---

## 🛠 สถาปัตยกรรมระบบ (System Architecture)

```
k-web-application/
├── frontend/             # Built Static SPA (React 18 + Vite)
│   └── dist/             # Production HTML/CSS/JS bundles
├── src/
│   ├── app_v2.py         # FastAPI Core Application & API Endpoints
│   ├── demo_security.py  # Session Isolation, CSRF, Idempotency, Security Headers
│   └── ui/               # React UI Components (Dashboard, Transfer, Styles)
├── models/
│   ├── flowsense.onnx    # ONNX Liquidity Projection Model
│   └── trustgraph.onnx   # ONNX Mule & Fraud Risk Model
├── data/                 # Synthetic Banking Profiles & Embeddings CSV
├── tests/
│   └── test_security.py  # Comprehensive HTTP Security & Integrity Tests
├── Dockerfile            # Multi-stage Docker Build (Node 22 + Python 3.13)
├── render.yaml           # Render Web Service Blueprint Specification
└── run.py                # Production ASGI Entrypoint (Uvicorn)
```

- **Frontend:** React 18, Vite 8, Lucide React, Custom Responsive CSS
- **Backend:** Python 3.13, FastAPI, Starlette, Uvicorn (Single instance/worker)
- **AI Engine:** ONNX Runtime 1.30 (`libgomp1`), Pandas 3.0, NumPy 2.5
- **Data Tier:** In-Memory Feature Store & Session-Isolated Synthetic State (Redis Simulation)

---

## 🔒 มาตรการความปลอดภัย (Security by Design)

- **Strict Session Isolation:** ข้อมูลจำลองและยอดเงินแยกขาดตาม Browser Session ของผู้ใช้แต่ละคน (ไม่กระทบกัน)
- **Tamper-Proof Micro-Auth Token:** Clearance Token เซ็นกำกับด้วย HMAC-SHA256 อายุ 120 วินาที ผูกกับ Source Account, Target Account, Amount และ Session ID
- **CSRF & Idempotency Protection:** ป้องกันการโจมตีข้ามไซต์ด้วย `X-CSRF-Token` และป้องกันการกดโอนซ้ำด้วย `X-Idempotency-Key`
- **Model Integrity Verification:** ตรวจสอบค่า SHA-256 Checksum ของไฟล์โมเดล ONNX ทุกครั้งตอนเริ่มต้นเซิร์ฟเวอร์
- **Secure Cookies & Headers:** ใช้คุกกี้ `__Host-flowsense` (Secure, HttpOnly, SameSite=Strict) พร้อม Content-Security-Policy (CSP), HSTS, no-referrer และ nosniff
- **DoS Safeguards:** จำกัด Body Request สูงสุดไม่เกิน 8 KiB และจำกัดอัตราการเรียกใช้งาน (Rate Limiting)

---

## 🚀 การรันในเครื่องสำหรับนักพัฒนา (Local Development)

### สิ่งที่ต้องมีในเครื่อง
- **Node.js:** v22.12 ขึ้นไป
- **Python:** v3.13 ขึ้นไป

### 1. ติดตั้งและเริ่มใช้งาน Backend
```powershell
# สร้างและเข้าใช้งาน Virtual Environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# ติดตั้ง Dependencies
pip install -r requirements.lock
npm ci

# บิลด์ Frontend SPA
npm run build

# สตาร์ตเซิร์ฟเวอร์
python run.py
```
เปิดเบราว์เซอร์ที่ <http://127.0.0.1:8000/> (Health Check: <http://127.0.0.1:8000/api/v2/health>)

### 2. รันโหมด Hot-Reload สำหรับพัฒนา Frontend
ในอีก terminal หนึ่ง ให้เปิดโหมด Vite Dev:
```powershell
npm run dev
```
เปิดเบราว์เซอร์ที่ <http://127.0.0.1:5173/> โดย Vite จะ Proxy ทุก request ที่ขึ้นต้นด้วย `/api` ไปยัง Python Backend อัตโนมัติ

---

## ☁️ การ Deploy ขึ้น Render (Render Deployment Guide)

โปรเจกต์นี้มีไฟล์ [Dockerfile](Dockerfile) และ [render.yaml](render.yaml) พร้อมสำหรับ Render Web Service ทันที:

### 1. ค่า Environment Variables ที่จำเป็น

| Key | Value | คำอธิบาย |
| :--- | :--- | :--- |
| `ENVIRONMENT` | `production` | เปิดใช้งานโหมด Production และ Security Guards |
| `HOST` | `0.0.0.0` | Bind IP สำหรับ Docker Container |
| `FORWARDED_ALLOW_IPS` | `*` | ไว้วางใจ Header จาก Render Reverse Proxy |
| `DEMO_SESSION_SECRET` | *(สุ่ม 32+ ตัวอักษร)* | คีย์สำหรับเข้ารหัส Session (กดปุ่ม Generate ใน Render) |

### 2. ตั้งค่า Health Check Path
- ใน Render ให้ตั้ง **Health Check Path** เป็น:
  ```text
  /api/v2/health
  ```

### 3. ทริคแก้ปัญหา Cold Start (ทำให้เปิดเร็ว 24 ชม. ฟรี 100%)
สำหรับผู้ใช้ Render Free Tier ที่ต้องการให้เว็บเปิดติดทันที ไม่ต้องรอหลับ 50 วินาที:
1. เข้าไปที่ **[cron-job.org](https://cron-job.org)** (สมัครฟรี)
2. สร้าง Cronjob ใหม่:
   - **URL:** `https://<ชื่อเว็บของคุณ>.onrender.com/api/v2/health`
   - **Schedule:** `Every 10 minutes` (ทุก 10 นาที)
3. เซิร์ฟเวอร์จะถูกทักทายสม่ำเสมอและอยู่ในสถานะ Active ตลอดเวลาโดยไม่เปลืองทรัพยากร

---

## 🧪 การทดสอบและตรวจสอบความปลอดภัย (Testing & Audits)

```powershell
# ติดตั้ง Development Dependencies
pip install -r requirements-dev.txt

# รัน Security & Feature Test Suite (13 tests)
python -m unittest discover -s tests -p 'test_*.py' -v

# ตรวจสอบช่องโหว่ความปลอดภัยของ Dependencies
pip-audit -r requirements.lock --disable-pip --no-deps
npm audit --audit-level=low

# ทดสอบบิลด์ Frontend
npm run build
```

---

## ⚠️ ข้อจำกัดและขอบเขตของต้นแบบ (Disclaimer)

1. **นี่เป็นต้นแบบอิสระ (Independent Concept Prototype):** สร้างขึ้นเพื่อการศึกษาวิจัยและทดสอบแนวคิดประสบการณ์ผู้ใช้ (UX Experiment) เท่านั้น
2. **ข้อมูลจำลองทั้งหมด (100% Synthetic Data):** ข้อมูลบัญชี ยอดเงิน ประวัติธุรกรรม และคะแนนความเสี่ยงเป็นข้อมูลสมมติทั้งหมด
3. **ไม่มีการเชื่อมต่อธนาคารจริง:** ไม่มีการเชื่อมต่อฐานข้อมูลธนาคาร ไม่มีการโอนเงินจริง และไม่มีการเปิดกล้องเพื่อสแกนใบหน้าจริง
4. **In-Memory Volatile Session:** บัญชีจำลองมีอายุ 1 ชั่วโมงตาม Session ของเบราว์เซอร์ เมื่อรีสตาร์ตเซิร์ฟเวอร์หรือหมดเวลา ข้อมูลจะกลับคืนสู่ค่าเริ่มต้นตามโปรไฟล์
