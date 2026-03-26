"""
Face Recognition Service
ใช้ library face_recognition (dlib ResNet) สำหรับ
1 สกัด 128D facial embedding จากภาพ
2 เปรียบเทียบ embedding 2 ตัวด้วย Euclidean distance
"""

import base64
import numpy as np
import cv2
import face_recognition
import os
from dotenv import load_dotenv

load_dotenv()

# Threshold สำหรับตัดสินว่าใบหน้าตรงกัน
# ค่ายิ่งต่ำ = เข้มงวดมาก, ค่าสูง = ผ่อนปรน
# 0.45 เป็นค่าที่สมดุลระหว่างความแม่นยำและความสะดวก
FACE_DISTANCE_THRESHOLD = float(
    os.getenv("FACE_DISTANCE_THRESHOLD", "0.45")
)


def _decode_base64_to_rgb(base64_string: str) -> np.ndarray:
    """
    แปลง base64 string เป็น RGB numpy array
    face_recognition ต้องการ RGB format (ไม่ใช่ BGR ของ OpenCV)
    """
    if "," in base64_string:
        base64_string = base64_string.split(",", 1)[1]

    img_bytes = base64.b64decode(base64_string)
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    bgr_frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if bgr_frame is None:
        return None

    # แปลง BGR → RGB (face_recognition ใช้ RGB)
    rgb_frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    return rgb_frame


def extract_embedding(base64_frame: str) -> dict:
    """
    สกัด 128-dimensional facial embedding จากภาพ
    กระบวนการ
    1 Detect ตำแหน่งใบหน้าในภาพ (face_locations)
    2 สกัด 128D vector จากใบหน้าที่พบ (face_encodings)
       - ใช้ dlib's ResNet model ที่ train มาจากชุดข้อมูลหลายล้านภาพ
       - ได้ vector 128 ตัวเลขทศนิยม ที่แทนลักษณะเฉพาะของใบหน้า

    Returns:
        {
            "success": True/False,
            "embedding": [float × 128] หรือ None,
            "message": str
        }
    """
    frame = _decode_base64_to_rgb(base64_frame)
    if frame is None:
        return {
            "success": False,
            "embedding": None,
            "message": "ไม่สามารถอ่านภาพได้",
        }

    # หาตำแหน่งใบหน้าในภาพ
    face_locations = face_recognition.face_locations(frame)

    if len(face_locations) == 0:
        return {
            "success": False,
            "embedding": None,
            "message": "ไม่พบใบหน้าในภาพ",
        }

    if len(face_locations) > 1:
        return {
            "success": False,
            "embedding": None,
            "message": f"พบใบหน้า {len(face_locations)} ใบหน้า — กรุณาให้มีแค่ 1 คนในภาพ",
        }

    # สกัด 128D embedding จากใบหน้าที่พบ
    encodings = face_recognition.face_encodings(frame, face_locations)

    if len(encodings) == 0:
        return {
            "success": False,
            "embedding": None,
            "message": "ไม่สามารถสกัดลักษณะใบหน้าได้",
        }

    # แปลง numpy array เป็น list เพื่อเก็บเป็น JSON
    embedding = encodings[0].tolist()

    return {
        "success": True,
        "embedding": embedding,
        "message": "สกัด facial embedding สำเร็จ",
    }


def compare_faces(
    stored_embedding: list,
    live_embedding: list,
    threshold: float = None,
) -> dict:
    """
    เปรียบเทียบ facial embedding 2 ตัวด้วย Euclidean distance

    รองรับ 2 แบบ
    1 stored_embedding เป็น list 128 ตัว (แบบเก่า)
    2 stored_embedding เป็น list ของ list (แบบใหม่ เก็บหลายมุม)
    Args:
        stored_embedding: embedding ที่เก็บไว้ตอนลงทะเบียน
        live_embedding:   embedding จากภาพ live [128 floats]
        threshold:        ค่า cutoff (default จาก .env)
    """
    if threshold is None:
        threshold = FACE_DISTANCE_THRESHOLD

    live = np.array(live_embedding)

    # ตรวจสอบว่าเป็น list 1D หรือ 2D
    if len(stored_embedding) > 0 and isinstance(stored_embedding[0], list):
        # มีหลายมุม  หา distance ที่น้อยที่สุด (มุมที่เหมือนที่สุด)
        distances = []
        for emb in stored_embedding:
            dist = float(np.linalg.norm(np.array(emb) - live))
            distances.append(dist)
        distance = min(distances)
    else:
        # มีมุมเดียว
        stored = np.array(stored_embedding)
        distance = float(np.linalg.norm(stored - live))

    # แปลง distance เป็น confidence percentage
    # distance 0.0 = 100% match, distance ≥ 1.0 = 0% match
    confidence = max(0.0, min(100.0, (1.0 - distance) * 100))

    match = distance < threshold

    return {
        "match": match,
        "distance": round(distance, 4),
        "threshold": threshold,
        "confidence": round(confidence, 2),
        "message": (
            f"ใบหน้าตรงกัน ✓ (distance={distance:.4f}, confidence={confidence:.1f}%)"
            if match
            else f"ใบหน้าไม่ตรงกัน ✗ (distance={distance:.4f}, confidence={confidence:.1f}%)"
        ),
    }
