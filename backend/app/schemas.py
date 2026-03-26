"""
Pydantic Models (Request/Response Schemas)
โครงสร้างข้อมูลสำหรับ API request และ response
ใช้ Pydantic v2 สำหรับ validation อัตโนมัติ
"""

from typing import List, Optional
from pydantic import BaseModel, EmailStr, Field



# User Registration (ลงทะเบียน)
class UserRegisterRequest(BaseModel):
    """ข้อมูลที่ต้องส่งมาตอนลงทะเบียน"""

    username: str = Field(
        ..., min_length=3, max_length=50,
        description="ชื่อผู้ใช้ (3-50 ตัวอักษร)",
        examples=["john_doe"],
    )
    email: EmailStr = Field(
        ...,
        description="อีเมล",
        examples=["john@example.com"],
    )
    password: str = Field(
        ..., min_length=8,
        description="รหัสผ่าน (อย่างน้อย 8 ตัวอักษร)",
        examples=["MyStr0ngP@ss"],
    )
    full_name: Optional[str] = Field(
        None, max_length=100,
        description="ชื่อ-นามสกุล (ไม่บังคับ)",
        examples=["John Doe"],
    )
    interests: Optional[List[str]] = Field(
        None,
        description="รายการหมวดหมู่/Emoji ที่ชื่นชอบ สำหรับใช้ใน Visual Challenge",
        examples=[["🐶", "🍕", "🚗"]],
    )


class UserResponse(BaseModel):
    """ข้อมูล user ที่ส่งกลับ (ไม่รวมรหัสผ่าน)"""

    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    interests: Optional[List[str]] = None
    is_active: bool

    class Config:
        from_attributes = True  # อ่านค่าจาก SQLAlchemy model ได้



# Authentication (เข้าสู่ระบบ)
class LoginRequest(BaseModel):
    """ข้อมูล login ขั้นตอนที่ 1 (รหัสผ่าน)"""

    username: str = Field(..., description="ชื่อผู้ใช้")
    password: str = Field(..., description="รหัสผ่าน")


class TokenResponse(BaseModel):
    """Token ที่ส่งกลับหลัง login สำเร็จ"""

    access_token: str
    token_type: str = "bearer"
    auth_step: int = Field(
        ..., description="ขั้นตอน auth ที่ผ่านแล้ว (1=password, 2=liveness, 3=face, 4=behavioral)"
    )
    message: str = ""


# Auth Step Response (ผลลัพธ์แต่ละขั้นตอน)
class AuthStepResponse(BaseModel):
    """ผลลัพธ์ของแต่ละขั้นตอนการยืนยันตัวตน"""

    success: bool
    message: str
    next_step: Optional[str] = Field(
        None,
        description="ขั้นตอนถัดไปที่ต้องทำ (None = จบแล้ว)",
    )
    session_token: Optional[str] = Field(
        None,
        description="JWT session token สำหรับขั้นตอนถัดไป",
    )


# Liveness Detection (ตรวจสอบคนจริง)
class LivenessRequest(BaseModel):
    """ข้อมูลสำหรับตรวจ liveness (กะพริบตา/หันหน้า)"""

    session_token: str = Field(..., description="JWT token จากขั้นตอนก่อนหน้า")
    frame: str = Field(
        ...,
        description="ภาพจาก webcam เป็น base64 string",
    )
    challenge_type: str = Field(
        ...,
        description="ชนิด challenge: 'blink' หรือ 'turn_head'",
        examples=["blink"],
    )


# Face Recognition (จดจำใบหน้า)
class FaceVerifyRequest(BaseModel):
    """ข้อมูลสำหรับเปรียบเทียบใบหน้า (รองรับ multi-pose)"""

    session_token: str = Field(..., description="JWT token จากขั้นตอนก่อนหน้า")
    frame: str = Field(
        ...,
        description="ภาพจาก webcam เป็น base64 string",
    )
    pose: str = Field(
        default="front",
        description="ท่าที่กำลังตรวจ: front, left, right, up, down",
    )
    completed_poses: List[str] = Field(
        default=[],
        description="รายการท่าที่ผ่านแล้ว",
    )


class FaceRegisterData(BaseModel):
    """ข้อมูลใบหน้าหลายมุมสำหรับลงทะเบียน"""

    frames: List[str] = Field(
        ..., min_length=1,
        description="รายการภาพ base64 จาก webcam (หลายมุม: หน้าตรง, หันซ้าย, หันขวา, เงยหน้า, ก้มหน้า)",
    )
    poses: List[str] = Field(
        default=[],
        description="label ของแต่ละ pose เช่น ['front', 'left', 'right', 'up', 'down']",
    )


# Cognitive Behavioral Challenge (ท้าทายพฤติกรรม)
class ChallengeQuestion(BaseModel):
    """คำถาม cognitive challenge 1 ข้อ"""

    id: str  # e.g., "math_1", "visual_2"
    type: str = Field("math", description="'math' หรือ 'visual'")
    question: str
    choices: List[str]
    correct_index: int = Field(
        ..., description="index ของคำตอบที่ถูกต้อง (0-based)"
    )


class ChallengeAnswer(BaseModel):
    """คำตอบของ user 1 ข้อ พร้อม reaction time"""

    question_id: str
    type: str = Field("math", description="'math' หรือ 'visual'")
    selected_index: int = Field(..., description="index ที่ user เลือก")
    reaction_time_ms: float = Field(
        ..., gt=0,
        description="เวลาตอบ (มิลลิวินาที) จาก performance.now()",
    )


class BehavioralRequest(BaseModel):
    """ข้อมูลสำหรับตรวจสอบพฤติกรรม (ขั้นตอนสุดท้าย)"""

    session_token: str = Field(..., description="JWT token จากขั้นตอนก่อนหน้า")
    answers: List[ChallengeAnswer] = Field(
        ..., min_length=3, max_length=3,
        description="คำตอบ 3 ข้อพร้อม reaction time",
    )


class RegisterBehavioralRequest(BaseModel):
    """ข้อมูลสำหรับสร้าง baseline พฤติกรรมตอนลงทะเบียน"""

    username: str = Field(..., description="username ที่เพิ่งลงทะเบียน")
    answers: List[ChallengeAnswer] = Field(
        ..., min_length=3, max_length=3,
        description="คำตอบ 3 ข้อพร้อม reaction time",
    )


class ChallengeListResponse(BaseModel):
    """รายการคำถาม cognitive challenge ที่สุ่มมา"""

    questions: List[ChallengeQuestion]
    session_token: str = Field(..., description="JWT token สำหรับส่งคำตอบ")
