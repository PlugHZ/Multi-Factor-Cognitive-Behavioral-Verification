"""
Password Hashing & JWT Token Utilities

เครื่องมือด้านความปลอดภัย เข้ารหัสรหัสผ่าน (bcrypt) และจัดการ JWT token

Functions:
    hash_password(plain)           สร้าง bcrypt hash
    verify_password(plain, hash)   ตรวจสอบรหัสผ่าน
    create_access_token(data)      สร้าง JWT token
    verify_token(token)            ถอดรหัส JWT token
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from dotenv import load_dotenv
from jose import JWTError, jwt

load_dotenv()

# Password Hashing — ใช้ bcrypt โดยตรง
# bcrypt จะสร้าง random salt อัตโนมัติทุกครั้งที่ hash
# ดังนั้น hash ของรหัสเดียวกันจะไม่ซ้ำกัน (ป้องกัน rainbow table attack)


def hash_password(plain_password: str) -> str:
    """
    เข้ารหัสรหัสผ่านด้วย bcrypt
    """
    password_bytes = plain_password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    ตรวจสอบว่ารหัสผ่าน plaintext ตรงกับ hash หรือไม่
    Args:
        plain_password:  รหัสผ่านที่ user ป้อน
        hashed_password: hash ที่เก็บใน DB

    Returns:
        True ถ้าตรงกัน, False ถ้าไม่ตรง
    """
    password_bytes = plain_password.encode("utf-8")
    hashed_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(password_bytes, hashed_bytes)


# JWT Token  ใช้สำหรับ session management ระหว่าง auth steps
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("❌ ไม่พบ SECRET_KEY ในไฟล์ .env! กรุณาเพิ่มก่อนเริ่มระบบ")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))

def create_access_token(
    data: dict, expires_delta: Optional[timedelta] = None
) -> str:
    """
    สร้าง JWT token
    Args
        data:          ข้อมูลที่จะใส่ใน token (เช่น {"sub": "username", "auth_step": 1})
        expires_delta: ระยะเวลาหมดอายุ (ถ้าไม่ระบุ ใช้ค่า default จาก .env)

    Returns
        JWT token string
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    """
    ถอดรหัสและตรวจสอบ JWT token
    Args
        token: JWT token string

    Returns
        decoded payload (dict) ถ้า token ถูกต้อง
        None ถ้า token ไม่ถูกต้องหรือหมดอายุ
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
