"""
Active Liveness Detection Service

ใช้ MediaPipe Face Mesh ตรวจสอบว่า user เป็นคนจริง
โดยท้าทายให้กะพริบตาหรือหันหน้า
วิธีการทำงาน
1 กะพริบตา (Blink):
   - คำนวณ Eye Aspect Ratio (EAR) จาก 6 จุดรอบดวงตา
   - EAR ปกติ ≈ 0.25-0.30, กะพริบ ≈ < 0.21

2 หันหน้า (Head Turn):
   - เปรียบเทียบ x-coordinate ของจมูกกับจุดกลางใบหน้า
   - ใช้อัตราส่วน nose_x / face_width เพื่อตรวจจับทิศทาง
"""

import base64
import numpy as np
import cv2
import mediapipe as mp

# MediaPipe Face Mesh — 468 จุด landmark บนใบหน้า
mp_face_mesh = mp.solutions.face_mesh

# Landmark indices สำหรับตาซ้ายและตาขวา (6 จุดต่อตา)
LEFT_EYE = [362, 385, 387, 263, 373, 380]   # ตาซ้าย (จากมุมมองของกล้อง)
RIGHT_EYE = [33, 160, 158, 133, 153, 144]   # ตาขวา

# Landmark indices สำหรับตรวจหันหน้า
NOSE_TIP = 1         # ปลายจมูก
LEFT_CHEEK = 234     # แก้มซ้าย
RIGHT_CHEEK = 454    # แก้มขวา

# Thresholds
EAR_THRESHOLD = 0.21       # ต่ำกว่านี้ = กะพริบ
HEAD_TURN_THRESHOLD = 0.60  # ห่างจากกลางมากกว่านี้ = หันหน้า


def _decode_base64_frame(base64_string: str) -> np.ndarray:
    """
    แปลง base64 string เป็น OpenCV image (numpy array)
    Args
        base64_string: ภาพจาก webcam ที่ encode เป็น base64

    Returns
        numpy array (BGR format) ที่ OpenCV ใช้ได้
    """
    # ตัด header ออก (เช่น "data:image/jpeg;base64,")
    if "," in base64_string:
        base64_string = base64_string.split(",", 1)[1]

    img_bytes = base64.b64decode(base64_string)
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    return frame


def _calculate_ear(landmarks, eye_indices, img_w, img_h) -> float:
    """
    คำนวณ Eye Aspect Ratio (EAR)
    สูตร EAR
        EAR = (||p2-p6|| + ||p3-p5||) / (2 × ||p1-p4||)

    โดย p1-p6 คือ 6 จุดรอบดวงตา
        p1 ── p2
        |      |     p1,p4 = หัวตา,หางตา (แนวนอน)
        p6 ── p5     p2,p3,p5,p6 = ขอบบน/ล่าง (แนวตั้ง)
        |      |
        p4 ── p3

    - ตาเปิด: EAR ≈ 0.25 - 0.30
    - ตาปิด: EAR ≈ 0.05 - 0.15
    - กะพริบ: EAR ลดลงชั่วคราว < 0.21
    """
    points = []
    for idx in eye_indices:
        lm = landmarks[idx]
        points.append([lm.x * img_w, lm.y * img_h])
    points = np.array(points, dtype=np.float64)

    # ระยะแนวตั้ง (2 คู่)
    vertical_1 = np.linalg.norm(points[1] - points[5])  # ||p2-p6||
    vertical_2 = np.linalg.norm(points[2] - points[4])  # ||p3-p5||

    # ระยะแนวนอน (1 คู่)
    horizontal = np.linalg.norm(points[0] - points[3])   # ||p1-p4||

    if horizontal == 0:
        return 0.0

    ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
    return ear


def detect_blink(base64_frame: str) -> dict:
    """
    ตรวจจับการกะพริบตา
    Returns:
        {
            "detected": True/False,
            "ear_left": float,
            "ear_right": float,
            "ear_avg": float,
            "message": str
        }
    """
    frame = _decode_base64_frame(base64_frame)
    if frame is None:
        return {"detected": False, "message": "ไม่สามารถอ่านภาพได้"}

    h, w = frame.shape[:2]
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    ) as face_mesh:
        results = face_mesh.process(rgb_frame)

        if not results.multi_face_landmarks:
            return {"detected": False, "message": "ไม่พบใบหน้าในภาพ"}

        landmarks = results.multi_face_landmarks[0].landmark

        ear_left = _calculate_ear(landmarks, LEFT_EYE, w, h)
        ear_right = _calculate_ear(landmarks, RIGHT_EYE, w, h)
        ear_avg = (ear_left + ear_right) / 2.0

        detected = ear_avg < EAR_THRESHOLD

        return {
            "detected": detected,
            "ear_left": round(ear_left, 4),
            "ear_right": round(ear_right, 4),
            "ear_avg": round(ear_avg, 4),
            "message": "ตรวจพบการกะพริบตา ✓" if detected else "ไม่พบการกะพริบตา",
        }


def detect_head_turn(base64_frame: str) -> dict:
    """
    ตรวจจับการหันหน้า (ซ้ายหรือขวา)
    ใช้อัตราส่วนตำแหน่ง x ของจมูกเทียบกับแก้มซ้าย-ขวา:
    - nose_ratio ≈ 0.50 = หน้าตรง
    - nose_ratio < 0.40 = หันขวา (จากมุมมอง user)
    - nose_ratio > 0.60 = หันซ้าย (จากมุมมอง user)

    Returns:
        {
            "detected": True/False,
            "direction": "left" / "right" / "center",
            "nose_ratio": float,
            "message": str
        }
    """
    frame = _decode_base64_frame(base64_frame)
    if frame is None:
        return {"detected": False, "direction": "unknown", "message": "ไม่สามารถอ่านภาพได้"}

    h, w = frame.shape[:2]
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    ) as face_mesh:
        results = face_mesh.process(rgb_frame)

        if not results.multi_face_landmarks:
            return {"detected": False, "direction": "unknown", "message": "ไม่พบใบหน้าในภาพ"}

        landmarks = results.multi_face_landmarks[0].landmark

        nose_x = landmarks[NOSE_TIP].x
        left_x = landmarks[LEFT_CHEEK].x
        right_x = landmarks[RIGHT_CHEEK].x

        # คำนวณอัตราส่วน จมูกอยู่ตรงไหนระหว่างแก้มซ้าย-ขวา
        face_width = abs(right_x - left_x)
        if face_width < 0.01:
            return {"detected": False, "direction": "unknown", "message": "ใบหน้าเล็กเกินไป"}

        nose_ratio = (nose_x - left_x) / face_width

        if nose_ratio < (1.0 - HEAD_TURN_THRESHOLD):
            direction = "right"
            detected = True
        elif nose_ratio > HEAD_TURN_THRESHOLD:
            direction = "left"
            detected = True
        else:
            direction = "center"
            detected = False

        return {
            "detected": detected,
            "direction": direction,
            "nose_ratio": round(nose_ratio, 4),
            "message": f"ตรวจพบการหันหน้าไป{direction} ✓" if detected else "หน้ายังตรงอยู่",
        }


def verify_challenge(base64_frame: str, challenge_type: str) -> dict:
    """
    ตรวจสอบ liveness challenge ตามชนิดที่กำหนด
    Args:
        base64_frame:  ภาพจาก webcam (base64)
        challenge_type: "blink" หรือ "turn_head"
    Returns:
        dict ผลการตรวจสอบ
    """
    if challenge_type == "blink":
        return detect_blink(base64_frame)
    elif challenge_type in ("turn_head", "turn_left", "turn_right"):
        return detect_head_turn(base64_frame)
    else:
        return {"detected": False, "message": f"ไม่รู้จัก challenge: {challenge_type}"}



# Head Pose Estimation — ตรวจสอบว่า user ทำท่าตามที่ระบบสั่งจริงหรือไม่
# ใช้ 6 จุด landmark ที่เป็นตัวแทนโครงสร้าง 3D ของใบหน้า
# แล้วใช้ cv2.solvePnP เพื่อประมาณ rotation vector → yaw, pitch, roll

# 3D model points (จากโมเดลใบหน้ามาตรฐาน - ปรับ Y ให้ชี้ลงเพื่อตรงกับพิกัดภาพ)
MODEL_POINTS_3D = np.array([
    [0.0, 0.0, 0.0],          # Nose tip
    [0.0, 330.0, -65.0],      # Chin (อยู่ใต้จมูก -> Y เป็นบวก)
    [-225.0, -170.0, -135.0], # Left eye corner (อยู่เหนือจมูก -> Y เป็นลบ)
    [225.0, -170.0, -135.0],  # Right eye corner
    [-150.0, 150.0, -125.0],  # Left mouth corner
    [150.0, 150.0, -125.0],   # Right mouth corner
], dtype=np.float64)

# MediaPipe landmark indices ที่สอดคล้องกับ 3D model points
POSE_LANDMARK_IDS = [
    1,    # Nose tip
    152,  # Chin
    33,   # Left eye inner corner
    263,  # Right eye inner corner
    61,   # Left mouth corner
    291,  # Right mouth corner
]

# Thresholds สำหรับแต่ละท่า (องศา)
POSE_THRESHOLDS = {
    "front": {"yaw_max": 15, "pitch_max": 15},
    "left":  {"yaw_min": -80, "yaw_max": -10},
    "right": {"yaw_min": 10, "yaw_max": 80},
    "up":    {"pitch_min": 10, "pitch_max": 80},
    "down":  {"pitch_min": -80, "pitch_max": -10},
}


def estimate_head_pose(base64_frame: str) -> dict:
    """
    ประมาณมุมหันหัว (yaw, pitch, roll) จากภาพ webcam
    วิธีการ:
    1 ตรวจจับ 468 จุดบนใบหน้าด้วย MediaPipe Face Mesh
    2 เลือก 6 จุดสำคัญ (จมูก, คาง, ตา 2 ข้าง, ปาก 2 ข้าง)
    3 ใช้ cv2.solvePnP แปลง 2D points → 3D rotation
    4 แปลง rotation vector เป็นมุม yaw, pitch, roll (องศา)

    Returns:
        {
            "success": True/False,
            "yaw": float,   # + = หันซ้าย, - = หันขวา
            "pitch": float, # + = ก้ม, - = เงย
            "roll": float,  # + = เอียงขวา, - = เอียงซ้าย
            "message": str
        }
    """
    frame = _decode_base64_frame(base64_frame)
    if frame is None:
        return {"success": False, "message": "ไม่สามารถอ่านภาพได้"}

    h, w = frame.shape[:2]
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    with mp_face_mesh.FaceMesh(
        static_image_mode=True,
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
    ) as face_mesh:
        results = face_mesh.process(rgb_frame)

        if not results.multi_face_landmarks:
            return {"success": False, "message": "ไม่พบใบหน้าในภาพ"}

        landmarks = results.multi_face_landmarks[0].landmark

        # สร้าง 2D image points จาก 6 landmarks
        image_points = np.array([
            [landmarks[idx].x * w, landmarks[idx].y * h]
            for idx in POSE_LANDMARK_IDS
        ], dtype=np.float64)

        # Camera matrix (ประมาณจากขนาดภาพ)
        focal_length = w
        center = (w / 2, h / 2)
        camera_matrix = np.array([
            [focal_length, 0, center[0]],
            [0, focal_length, center[1]],
            [0, 0, 1],
        ], dtype=np.float64)

        dist_coeffs = np.zeros((4, 1))  # ไม่มี lens distortion

        # solvePnP  หามุมหัน
        success, rotation_vec, translation_vec = cv2.solvePnP(
            MODEL_POINTS_3D, image_points, camera_matrix, dist_coeffs,
            flags=cv2.SOLVEPNP_ITERATIVE,
        )

        if not success:
            return {"success": False, "message": "ไม่สามารถคำนวณมุมหันได้"}

        # แปลง rotation vector เป็น rotation matrix → Euler angles
        rotation_mat, _ = cv2.Rodrigues(rotation_vec)

        # ใช้ RQDecomp3x3 แปลง rotation matrix เป็น Euler angles (degrees)
        euler_angles, _, _, _, _, _ = cv2.RQDecomp3x3(rotation_mat)

        pitch = float(euler_angles[0])  # เงย(-) / ก้ม(+)
        yaw = float(euler_angles[1])    # ซ้าย(+) / ขวา(-)
        roll = float(euler_angles[2])   # เอียง

        return {
            "success": True,
            "yaw": round(yaw, 1),
            "pitch": round(pitch, 1),
            "roll": round(roll, 1),
            "message": f"yaw={yaw:.1f}°, pitch={pitch:.1f}°",
        }


def validate_pose(base64_frame: str, expected_pose: str) -> dict:
    """
    ตรวจสอบว่า user ทำท่าตามที่ระบบสั่งหรือไม่
    Args
        base64_frame: ภาพจาก webcam (base64)
        expected_pose: "front", "left", "right", "up", "down"
    Returns:
        {
            "valid": True/False,
            "expected_pose": str,
            "yaw": float,
            "pitch": float,
            "message": str
        }
    """
    if expected_pose not in POSE_THRESHOLDS:
        return {"valid": False, "message": f"ไม่รู้จักท่า: {expected_pose}"}

    result = estimate_head_pose(base64_frame)
    if not result["success"]:
        return {
            "valid": False,
            "expected_pose": expected_pose,
            "message": result["message"],
        }

    yaw = result["yaw"]
    pitch = result["pitch"]
    thresholds = POSE_THRESHOLDS[expected_pose]

    pose_names = {
        "front": "หน้าตรง",
        "left": "หันซ้าย",
        "right": "หันขวา",
        "up": "เงยหน้า",
        "down": "ก้มหน้า",
    }

    if expected_pose == "front":
        valid = abs(yaw) <= thresholds["yaw_max"] and abs(pitch) <= thresholds["pitch_max"]
    elif expected_pose in ("left", "right"):
        valid = thresholds["yaw_min"] <= yaw <= thresholds["yaw_max"]
    elif expected_pose in ("up", "down"):
        valid = thresholds["pitch_min"] <= pitch <= thresholds["pitch_max"]
    else:
        valid = False

    return {
        "valid": valid,
        "expected_pose": expected_pose,
        "yaw": yaw,
        "pitch": pitch,
        "message": (
            f"✓ ท่า{pose_names[expected_pose]}ถูกต้อง (yaw={yaw:.1f}°, pitch={pitch:.1f}°)"
            if valid
            else f"ท่าไม่ถูกต้อง — กรุณา{pose_names[expected_pose]} (yaw={yaw:.1f}°, pitch={pitch:.1f}°)"
        ),
    }
