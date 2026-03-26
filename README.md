# Multi-Factor Digital ID System

ระบบยืนยันตัวตนแบบหลายปัจจัย (Multi-Factor Authentication) ที่มีความปลอดภัยสูง โดยผสานการตรวจสอบรหัสผ่าน, ข้อมูลชีวมิติ (ใบหน้า), และพฤติกรรมการตอบสนอง (Cognitive Behavioral) เข้าด้วยกัน เพื่อป้องกันการปลอมแปลงและบอท

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
   # สำหรับ Windows
   .\venv\Scripts\activate
   # สำหรับ Mac/Linux
   source venv/bin/activate
   ```
3. ติดตั้ง Dependencies (รวมถึงไลบรารี face_recognition ที่ต้องการ C++ Build Tools):
   ```bash
   pip install -r requirements.txt
   ```
4. สร้างไฟล์ `.env` พร้อมตั้งค่าตัวแปร:
   ```env
   DATABASE_URL=postgresql://user:password@localhost:5432/dbname
   SECRET_KEY=your_super_secret_key_here
   ```
5. เริ่มการทำงานของเซิร์ฟเวอร์:
   ```bash
   python main.py
   # หรือ uvicorn app.main:app --reload
   ```
   Backend จะรันที่: `http://localhost:8000` (มีเอกสาร API ที่ `/docs`)

### การตั้งค่า Frontend

1. เข้าไปที่โฟลเดอร์ `frontend`:
   ```bash
   cd frontend
   ```
2. ติดตั้ง Dependencies:
   ```bash
   npm install
   ```
3. รัน Development Server:
   ```bash
   npm run dev
   ```
   Frontend จะรันที่: `http://localhost:5173`

## ลำดับการทำงาน (Authentication Flow)

1. **การลงทะเบียน (Registration)**
   - กรอกข้อมูลรหัสผ่าน และเลือก Emoji ที่สนใจ 3 อัน (เป็นความลับ)
   - หันหน้าให้กล้องเพื่อบันทึกโครงสร้างใบหน้า 5 มุม (Auto Capture)
   - ทำแบบทดสอบพื้นฐานเพื่อใช้เป็น Baseline (วัดผล Reaction Time เบื้องต้น)

2. **การเข้าสู่ระบบ (Login)**
   - กรอก Username / Password
   - ทำการกะพริบตา หรือ หันหน้าตามที่ระบบสุ่มสั่ง
   - หันหน้า 5 มุมให้ระบบเปรียบเทียบกับฐานข้อมูล
   - ตอบคำถาม Math หรือ Visual Emoji แบบสุ่ม แข่งกับเวลาของตัวเองในอดีต (Z-score Validation)

---

_Developed with advanced security logic and optimized hybrid verification pipelines._
