# FlowSense × TrustGraph — interactive web prototype

แอปทดลองสำหรับผู้ใช้ทั่วไปที่นำแนวคิด FlowSense (คาดการณ์สภาพคล่องและเงินออมยืดหยุ่น) กับ TrustGraph (ประเมินความเสี่ยงก่อนโอน) มาวางเป็นฟีเจอร์ที่อาจอยู่ในประสบการณ์แบบ K+ / MAKE by KBank

**นี่เป็นต้นแบบอิสระ** ใช้บัญชีและธุรกรรมจำลองทั้งหมด ไม่มีการเชื่อมต่อธนาคาร ไม่มีการโอนเงินจริง และการยืนยันตัวตนในหน้าเว็บเป็นการจำลอง ไม่ได้ใช้กล้องหรือสแกนใบหน้าจริง

## เริ่มใช้งาน

ต้องมี Node.js 22.12+ และ Python 3.13

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.lock
npm ci
npm run build
python run.py
```

เปิด <http://127.0.0.1:8000/> ในเบราว์เซอร์ (health check: <http://127.0.0.1:8000/api/v2/health>) ไม่เปิด API docs สาธารณะ

ระหว่างพัฒนา รัน `python run.py` แล้วรัน `npm run dev` ในอีก terminal และเปิด <http://127.0.0.1:5173/> Vite จะส่ง `/api` ไปยัง Python server

## สิ่งที่ทดลองได้

- เลือกโปรไฟล์จำลอง 3 แบบ แล้วดูยอดเงิน สภาพคล่อง ภาระที่ต้องจ่าย และกราฟคาดการณ์
- ย้ายเงินเข้ากระเป๋าออม ดึงกลับ และรีเซ็ตข้อมูลจำลอง
- ลอง Micro-Sweep ตามจำนวนที่ FlowSense แนะนำจากโปรไฟล์และยอดเงินปัจจุบัน
- ทดลองโอนเข้าบัญชีปกติ บัญชีที่ต้องตรวจเพิ่ม และบัญชีที่ระบบระงับ
- เห็นเหตุผลก่อนตัดสินใจ พร้อมขั้นตอนยืนยันตัวตนแบบจำลองเมื่อระบบต้องตรวจเพิ่ม

ข้อมูลยอดเงินแยกตาม session ของแต่ละเบราว์เซอร์ ผู้ทดลองไม่เปลี่ยนยอดของกันและกัน Session มีอายุหนึ่งชั่วโมงและเก็บในหน่วยความจำ จึงเริ่มใหม่เมื่อหมดอายุหรือรีสตาร์ต server รายการล่าสุดในหน้าเว็บเริ่มใหม่เมื่อโหลดหน้าเว็บ

หน้าตาใช้ Ref ของผู้ใช้เป็นแนวทาง: เมนูสีเขียวเข้ม การ์ดบัญชีพื้นสว่าง ปุ่มทำรายการแบบแอปธนาคาร และหน้าโอนที่แบ่งบัญชีผู้โอน บัญชีปลายทาง และจำนวนเงิน มีหน้าบัญชีสำหรับดูภาระและคาดการณ์ ส่วน FlowSense และ TrustGraph เป็นการ์ดหลักที่เปิดทดลองจากหน้าหลักได้ทันที

## ที่มาของไฟล์

คัดลอกและปรับ `src/app_v2.py`, โมเดล `models/*.onnx`, `requirements.txt` และ CSV ที่ API ใช้จริง (`01`, `03`, `04`, `05`) จากโปรเจกต์ `k-flowsense-trustgraph` ในเครื่องเดียวกัน UI ใน `src/ui/` เป็นหน้าใหม่ที่ออกแบบสำหรับผู้ใช้ปลายทาง ส่วนข้อมูลใน `data/` เป็น **synthetic data** ตามเอกสารของโปรเจกต์ต้นทาง

ไม่ได้คัดลอกหน้า landing/architecture, pipeline ฝึกโมเดล, ไฟล์ LightGBM ต้นฉบับ, dataset กระแสเงินสด `02` หรือไฟล์ startup/deployment เดิม เพราะไม่จำเป็นต่อการทำงานของ API และต้นแบบนี้

## ข้อจำกัดของต้นแบบ

โมเดลและตรรกะจากโปรเจกต์เดิมใช้ประกอบการทดลอง UX เท่านั้น ตัวเลขคาดการณ์ ความเสี่ยง และสถานะบัญชีไม่ได้ใช้ตัดสินใจทางการเงินจริง การเชื่อม K+ / MAKE จริงต้องมีระบบบัญชี การยืนยันตัวตน และการประเมินด้านความปลอดภัยจากธนาคารก่อน

## Security และ Render

ตรวจและปรับ API ให้แยก session, ป้องกัน CSRF และ token replay, จำกัด body/rate/จำนวน session, ป้องกันรายการซ้ำด้วย idempotency และตรวจ SHA-256 ของโมเดลตอนเริ่มระบบ ดูรายละเอียดใน [security review](docs/security-review.md)

เตรียม Dockerfile และ [Render Blueprint](render.yaml) สำหรับบริการแบบหนึ่ง instance/หนึ่ง worker พร้อม generated secret และ health check อ่านขั้นตอนที่ [Render deployment](docs/render.md) Blueprint ระบุแผน Starter ซึ่งมีค่าใช้จ่ายเมื่อคุณสร้างบริการใน Render

```powershell
pip install -r requirements-dev.txt
python -m unittest discover -s tests -p 'test_*.py' -v
pip-audit -r requirements.lock --disable-pip --no-deps
npm audit
npm run build
```

CI จะตรวจ dependency, HTTP security tests และ build/ทดสอบ container ก่อน auto-deploy การเก็บ session ข้าม deploy หรือเพิ่มจำนวน instance ต้องย้ายสถานะไปยัง storage ที่ใช้ร่วมกันก่อน
