# Multi-Factor Digital ID System

ระบบยืนยันตัวตนแบบหลายปัจจัย (Multi-Factor Authentication) ที่มีความปลอดภัยสูง โดยผสานการตรวจสอบรหัสผ่าน, ข้อมูลชีวมิติ (ใบหน้า), และพฤติกรรมการตอบสนอง (Cognitive Behavioral) เข้าด้วยกัน เพื่อป้องกันการปลอมแปลง

## ฟีเจอร์หลัก (Key Features)

การยืนยันตัวตนจะถูกแบ่งชั้นความปลอดภัยออกเป็นปัจจัยต่างๆ ดังนี้:

1. **Knowledge Factor (Password)**
   - ระบบ Login ด้วย Username และ Password พื้นฐานที่เข้ารหัสด้วย bcrypt

2. **Inherence Factor (Face Biometrics & Liveness)**
   - **Liveness Detection:** ป้องกันการนำภาพถ่ายหรือวิดีโอมาหลอกระบบ โดยสุ่มคำสั่งให้ผู้ใช้กะพริบตา (Blink) หรือหันหน้า (Head Turn) แบบอัตโนมัติ
   - **Multi-Pose Face Recognition:** ตรวจสอบและเปรียบเทียบโครงสร้างใบหน้า 5 มุม (หน้าตรง, หันซ้าย, หันขวา, เงยหน้า, ก้มหน้า) ด้วยโมเดล Machine Learning แบบ 128D Embeddings อัตโนมัติ

3. **Behavioral Factor (Cognitive Reaction Time)**
   - **Hybrid Behavioral Challenge:** ผสมผสานการตรวจสอบความเร็วในการตอบสนอง (Reaction Time) จาก 2 รูปแบบ
     - _Math Challenge:_ การแก้โจทย์คณิตศาสตร์และคำถามตรรกะพื้นฐาน
     - _Visual Challenge:_ เกมจับผิดภาพหา Emoji ที่ผู้ใช้ลงทะเบียนความสนใจ (Interests) ไว้จากตาราง 3x3 Grid
   - ระบบจะใช้ **Welford's Algorithm** เก็บค่าเฉลี่ย (Mean) และส่วนเบี่ยงเบนมาตรฐาน (SD) แยกแต่ละหมวดหมู่ เพื่อนำมาคำนวณ **Z-score** ตรวจสอบว่าพฤติกรรมการคลิกเป็นตัวผู้ใช้จริงหรือไม่ และบล็อกบอทหรือการสุ่มคลิกอัตโนมัติ (Reaction time < 200ms)

## โครงสร้างโปรเจค (System Architecture & Directory Structure)

```text
c:\dev\DigitalID\
├── backend/
│   ├── main.py                           # FastAPI Entry Point (CORS + Router)
│   ├── requirements.txt                  # Python Dependencies
│   ├── .env / .env.example               # Environment Variables & Database Config
│   └── app/
│       ├── database.py                   # SQLAlchemy Engine Setup
│       ├── models.py                     # User, FacialProfile, BehavioralProfile
│       ├── schemas.py                    # Pydantic Schemas (Request/Response)
│       ├── security.py                   # JWT & bcrypt Encryption
│       ├── services/
│       │   ├── liveness.py               # MediaPipe Liveness Detection (Blink/Turn)
│       │   ├── face_recognition_service.py # 128D Face Embeddings Generation
│       │   └── behavioral.py             # Z-score, Welford's Algorithm (Math & Visual)
│       └── routes/
│           └── auth.py                   # 6 Core Authentication Endpoints
└── frontend/
    └── src/
        ├── index.css                     # Dark Mode & Glassmorphism Design System
        ├── main.jsx                      # React Config
        ├── App.jsx                       # React Router Setup
        ├── services/api.js               # Axios API Interface (Connects to FastAPI)
        └── pages/
            ├── RegisterPage.jsx          # หน้าจอลงทะเบียน (3 ขั้นตอน)
            ├── LoginPage.jsx             # หน้าจอเข้าสู่ระบบ (4 ขั้นตอน)
            └── DashboardPage.jsx         # ยินดีต้อนรับ (ข้อมูล User หลัง Login สำเร็จ)
```

โปรเจคถูกแบ่งออกเป็น 2 ส่วนหลัก:

### 1. Backend (FastAPI)

- **Framework:** FastAPI
- **Database:** PostgreSQL (ผ่าน SQLAlchemy ORM)
- **Computer Vision & AI:** `opencv-python`, `mediapipe` (สำหรับ Liveness Hand/Face tracking), `face_recognition` (สำหรับ dlib face embeddings)
- **Security:** JWT (JSON Web Tokens), bcrypt

### 2. Frontend (React)

- **Framework:** React + Vite
- **Routing:** React Router DOM
- **Camera:** `react-webcam`
- **Styling:** Vanilla CSS (Glassmorphism & Dark Mode UI design)

## วิธีการติดตั้งและรันโปรเจค

### การตั้งค่า Backend

1. เข้าไปที่โฟลเดอร์ `backend`:
   ```bash
   cd backend
   ```
2. สร้างและเปิดใช้งาน Virtual Environment:
   ```bash
   python -m venv venv
   # Windows
   .\venv\Scripts\activate
   # Mac/Linux
   source venv/bin/activate
   ```
3. ติดตั้งเครื่องมือช่วย Build (สำคัญมากสำหรับ Windows):
   ```bash
   pip install cmake wheel
   ```
4. ติดตั้ง Dependencies ทั้งหมด:

   ```bash
   pip install -r requirements.txt
   ```

   > [!TIP]
   > หาก `pip install dlib` ล้มเหลว ให้ลองหาไฟล์ `.whl` ของ dlib ที่ตรงกับเวอร์ชัน Python ของคุณมาติดตั้งแทน (เช่นจาก GitHub ของชุมชน)

5. สร้างและตั้งค่าไฟล์ `.env`:
   คัดลอกไฟล์ต้นแบบ: `cp .env.example .env` (หรือสร้างใหม่) และตั้งค่าดังนี้:
   ```env
   PORT=8000
   DATABASE_URL=sqlite:///./digital_id.db  # หรือ postgresql://...
   SECRET_KEY=your_random_secret_hash
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   FACE_DISTANCE_THRESHOLD=0.40           # ความเข้มงวด (ยิ่งน้อยยิ่งตรวจละเอียด)
   ZSCORE_THRESHOLD=2.0                   # ความเข้มงวดด่านพฤติกรรม
   ```

### 2. การตั้งค่า Frontend (React + Vite)

1. เข้าไปที่โฟลเดอร์ `frontend`:
   ```bash
   cd frontend
   ```
2. ติดตั้ง Dependencies:
   ```bash
   npm install
   ```
3. ตั้งค่า Endpoint ของ API ในไฟล์ `.env` (ถ้ามี หรือใช้ค่า Default):
   ```env
   VITE_API_URL=http://localhost:8000/api
   ```

---

## How to Run (การเดินระบบ)

### รัน Backend

```bash
cd backend
# ตรวจสอบว่าเปิด venv อยู่
python main.py
```

Backend จะรันอยู่ที่: `http://localhost:8000`

### รัน Frontend

```bash
cd frontend
npm run dev
```

Frontend จะรันอยู่ที่: `http://localhost:5173`

> [!NOTE]
> **การทดสอบผ่านมือถือ/วง LAN:**
> หากต้องการทดสอบผ่านมือถือในวง WiFi เดียวกัน ให้รัน Frontend ด้วย `npm run dev -- --host` และรัน Backend ด้วย `python main.py` (ซึ่งตั้งค่า `0.0.0.0` ไว้แล้ว) แล้วเข้าถึงผ่าน IP เครื่องคอมพิวเตอร์ของคุณ

---

## ลำดับการทำงาน (Authentication Flow)

1. **ลงทะเบียน (Register)**:
   - กรอกข้อมูลพื้นฐาน และเลือก **Secret Emojis 3 อัน**
   - หันหน้า 5 มุม (ระบบถ่ายอัตโนมัติ)
   - ตอบคำถาม 3 ข้อเพื่อบันทึกความเร็ว (Baseline)
2. **เข้าสู่ระบบ (Login)**:
   - **Step 1**: Username/Password
   - **Step 2**: Liveness (กะพริบตา/หันหน้า) เพื่อกันการโกงด้วยรูปถ่าย
   - **Step 3**: Face Match (เทียบใบหน้า 5 มุม)
   - **Step 4**: Behavioral (ตอบโจทย์เลข/Emoji ลับ) สุ่มผสมกัน 3 ข้อ

---

## Troubleshooting (การแก้ปัญหาพื้นฐาน)

- **dlib error**: ตรวจสอบว่ามี C++ Build Tools หรือยัง? หรือลองหาไฟล์ `.whl` มาลงแทน
- **Webcam ไม่ทำงาน**: ตรวจสอบ Permission ของ Browser หรือโปรแกรมอื่นที่กำลังใช้กล้องอยู่
- **Database Error**: หากเปลี่ยนโครงสร้างตาราง แนะนำให้ลบไฟล์ `.db` เดิมทิ้งแล้วรันใหม่เพื่อให้ระบบสร้างตารางใหม่ (Create All)
