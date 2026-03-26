"""
Authentication API Routes
API สำหรับระบบยืนยันตัวตนแบบหลายปัจจัย
Flow (4 ขั้นตอน)
    1. POST /api/auth/login      → ตรวจ password → session_token (step=1)
    2. POST /api/auth/liveness   → ตรวจ liveness → session_token (step=2)
    3. POST /api/auth/face       → ตรวจ face     → session_token (step=3)
    4. POST /api/auth/behavioral → ตรวจ Z-score  → access_token (step=4, จบ)
Registration
    POST /api/register → สร้าง user + face embedding + behavioral baseline
"""

import os
import random
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, FacialProfile, BehavioralProfile
from app.security import (
    hash_password,
    verify_password,
    create_access_token,
    verify_token,
)
from app.schemas import (
    UserRegisterRequest,
    UserResponse,
    LoginRequest,
    TokenResponse,
    AuthStepResponse,
    LivenessRequest,
    FaceVerifyRequest,
    FaceRegisterData,
    BehavioralRequest,
    RegisterBehavioralRequest,
    ChallengeListResponse,
    ChallengeQuestion,
)
from app.services.liveness import verify_challenge, validate_pose
from app.services.face_recognition_service import extract_embedding, compare_faces
from app.services.behavioral import (
    get_random_challenges,
    check_answers,
    verify_hybrid_behavior,
    update_hybrid_stats,
)


# Router
router = APIRouter(prefix="/api", tags=["Authentication"])



# ตรวจสอบ session token และ auth step
def _validate_session_token(token: str, required_step: int) -> dict:
    """
    ตรวจสอบว่า session token ถูกต้องและอยู่ในขั้นตอนที่ถูกต้อง
    Args
        token JWT session token
        required_step ขั้นตอนที่ต้องผ่านมาก่อน (เช่น 1 = ต้องผ่าน password แล้ว)
    Returns
        decoded payload
    Raises
        HTTPException 401 ถ้า token ไม่ถูกต้อง
        HTTPException 403 ถ้ายังไม่ผ่านขั้นตอนก่อนหน้า
    """
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session token ไม่ถูกต้องหรือหมดอายุ",
        )

    current_step = payload.get("auth_step", 0)
    if current_step < required_step:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"ต้องผ่านขั้นตอนที่ {required_step} ก่อน (ตอนนี้อยู่ขั้น {current_step})",
        )

    return payload



# REGISTERลงทะเบียนผู้ใช้ใหม่

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="ลงทะเบียนผู้ใช้ใหม่",
)
def register_user(
    request: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """
    สร้างบัญชีผู้ใช้ใหม่
    ขั้นตอน
    ตรวจสอบว่า username/email ยังไม่ซ้ำ
    Hash รหัสผ่านด้วย bcrypt (hash+salt)
    สร้าง User record
    สร้าง BehavioralProfile เปล่า (จะเติมข้อมูลตอน enrollment)
    """
    # ตรวจ username ซ้ำ
    existing = db.query(User).filter(User.username == request.username).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username นี้ถูกใช้แล้ว",
        )

    # ตรวจ email ซ้ำ
    existing = db.query(User).filter(User.email == request.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email นี้ถูกใช้แล้ว",
        )

    # สร้าง user
    user = User(
        username=request.username,
        email=request.email,
        hashed_password=hash_password(request.password),
        full_name=request.full_name,
        interests=request.interests,
    )
    db.add(user)
    db.flush()  # ให้ได้ user.id ก่อน commit

    # สร้าง behavioral profile เปล่า
    behavioral = BehavioralProfile(user_id=user.id)
    db.add(behavioral)

    db.commit()
    db.refresh(user)

    return user


# REGISTER FACE ลงทะเบียนใบหน้าหลายมุม 
@router.post(
    "/register/face",
    summary="ลงทะเบียนใบหน้าหลายมุม (หน้าตรง, หันซ้าย, หันขวา, เงยหน้า, ก้มหน้า)",
)
def register_face(
    face_data: FaceRegisterData,
    username: str,
    db: Session = Depends(get_db),
):
    """
    บันทึก facial embedding จากภาพหลายมุม
    ขั้นตอน
    หา user จาก username
    สกัด 128D embedding จากทุกภาพ
    คำนวณ embedding เฉลี่ย (average) จากทุกมุม
    Normalize ให้เป็น unit vector
    บันทึกลง FacialProfile

    การเฉลี่ย embedding ช่วยให้
     ลดผลกระทบจากมุมที่ไม่ดี
     ได้ embedding ที่เป็นตัวแทนใบหน้าได้ดีกว่ามุมเดียว
     เพิ่มความแม่นยำตอน login
    """
    import numpy as np

    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบ user")

    # สกัด embedding จากทุก frame
    embeddings = []
    failed_poses = []
    pose_labels = face_data.poses if face_data.poses else [f"pose_{i}" for i in range(len(face_data.frames))]

    for i, frame in enumerate(face_data.frames):
        result = extract_embedding(frame)
        pose_name = pose_labels[i] if i < len(pose_labels) else f"pose_{i}"

        if result["success"]:
            embeddings.append(result["embedding"])
        else:
            failed_poses.append(f"{pose_name}: {result['message']}")

    if len(embeddings) == 0:
        raise HTTPException(
            status_code=400,
            detail=f"ไม่สามารถสกัดใบหน้าได้จากทุกภาพ: {'; '.join(failed_poses)}",
        )

    # บันทึก embeddings ทั้งหมดเป็น list ของ list
    # เก็บทุกมุมแยกกัน เพื่อให้ตอนตรวจสอบสามารถหาจากมุมที่ตรงที่สุดได้
    stored_embeddings = [emb for emb in embeddings]

    # ลบ profile เก่า ถ้ามี แล้วสร้างใหม่
    existing = db.query(FacialProfile).filter(FacialProfile.user_id == user.id).first()
    if existing:
        db.delete(existing)

    profile = FacialProfile(
        user_id=user.id,
        embedding=stored_embeddings,  # บันทึกเป็น Array ของ Array
    )
    db.add(profile)
    db.commit()

    return {
        "success": True,
        "message": f"บันทึก facial embedding สำเร็จ ({len(embeddings)}/{len(face_data.frames)} มุมสำเร็จ)",
        "username": username,
        "successful_poses": len(embeddings),
        "total_poses": len(face_data.frames),
        "failed_poses": failed_poses,
    }


@router.get(
    "/register/challenges",
    summary="ดึงคำถาม cognitive challenge สำหรับสร้าง baseline",
)
def get_register_challenges(username: str, db: Session = Depends(get_db)):
    """ดึงคำถามแบบผสม (math/visual) เพื่อสร้าง baseline ให้ผู้ใช้ใหม่"""
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบ user")
        
    interests = user.interests if user.interests else []
    full_questions, safe_questions = get_random_challenges(interests, n=3)
    
    return {"questions": safe_questions}



# REGISTER BEHAVIORAL  ลงทะเบียน baseline พฤติกรรม
@router.post(
    "/register/behavioral",
    summary="ลงทะเบียน behavioral baseline (ส่ง reaction times)",
)
def register_behavioral(
    request: RegisterBehavioralRequest,
    db: Session = Depends(get_db),
):
    """
    สร้าง behavioral baseline จาก enrollment session
    """
    user = db.query(User).filter(User.username == request.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="ไม่พบ user")

    # ตรวจคำตอบ
    answer_result = check_answers(
        [a.model_dump() for a in request.answers]
    )
    
    # บังคับว่าต้องตอบถูกอย่างน้อย 2 ใน 3 ข้อ
    if answer_result["correct_count"] < 2:
        raise HTTPException(
            status_code=400,
            detail=f"ตอบผิดเกินกำหนด (ถูก {answer_result['correct_count']} จาก {answer_result['total']}) กรุณาตั้งใจตอบคำถาม",
        )

    # อัปเดต behavioral profile
    profile = db.query(BehavioralProfile).filter(
        BehavioralProfile.user_id == user.id
    ).first()

    if profile:
        profile.stats = update_hybrid_stats(profile.stats, answer_result)
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(profile, "stats")
    else:
        profile = BehavioralProfile(
            user_id=user.id,
            stats=update_hybrid_stats({}, answer_result)
        )
        db.add(profile)

    db.commit()

    return {
        "success": True,
        "message": "บันทึก behavioral baseline สำเร็จ",
        "stats": profile.stats,
    }



# LOGIN ขั้นตอนที่ 1 ตรวจรหัสผ่าน
@router.post(
    "/auth/login",
    response_model=AuthStepResponse,
    summary="ขั้น 1: ตรวจรหัสผ่าน",
)
def login_password(
    request: LoginRequest,
    db: Session = Depends(get_db),
):
    """
    Factor 1: Something You Know (รหัสผ่าน)
    ขั้นตอน
    1 หา user จาก username
    2 ตรวจสอบ password ด้วย bcrypt
    3 ถ้าผ่านสร้าง session_token ที่มี auth_step=1
    """
    user = db.query(User).filter(User.username == request.username).first()

    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Username หรือรหัสผ่านไม่ถูกต้อง",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="บัญชีนี้ถูกล็อค",
        )

    # สร้าง session token (step=1 = ผ่าน password แล้ว)
    # สุ่ม challenge สำหรับ liveness
    challenge = random.choice(["blink", "turn_head"])
    session_token = create_access_token(
        data={
            "sub": user.username,
            "user_id": user.id,
            "auth_step": 1,
            "liveness_challenge": challenge,
        },
        expires_delta=timedelta(minutes=5),  # token สั้น  ใช้แค่ระหว่าง auth
    )

    return AuthStepResponse(
        success=True,
        message=f"รหัสผ่านถูกต้อง ✓ — ขั้นตอนถัดไป: Liveness Detection ({challenge})",
        next_step="liveness",
        session_token=session_token,
    )



# LIVENESS  ขั้นตอนที่ 2 ตรวจคนจริง + ยืนยันว่าเป็นเจ้าของบัญชี
@router.post(
    "/auth/liveness",
    response_model=AuthStepResponse,
    summary="ขั้น 2: ตรวจ Liveness + ยืนยันใบหน้า (ป้องกันคนอื่นกะพริบแทน)",
)
def verify_liveness(
    request: LivenessRequest,
    db: Session = Depends(get_db),
):
    """
    Active Liveness Detection + Face Identity Check
    ตรวจ 2 อย่างพร้อมกัน
    1Liveness กะพริบตา หรือ หันหน้า (ด้วย MediaPipe)
    2Face Identity ใบหน้าตรงกับที่ลงทะเบียนหรือไม่ (ด้วย face_recognition)
    """
    payload = _validate_session_token(request.session_token, required_step=1)
    user_id = payload["user_id"]

    # ตรวจ Liveness 
    liveness_result = verify_challenge(request.frame, request.challenge_type)

    if not liveness_result["detected"]:
        return AuthStepResponse(
            success=False,
            message=f"Liveness ไม่ผ่าน: {liveness_result['message']}",
            next_step="liveness",
            session_token=request.session_token,
        )

    # ตรวจ Face Identity (ใบหน้าตรงกับเจ้าของบัญชีมั้ย) 
    live_result = extract_embedding(request.frame)
    if not live_result["success"]:
        return AuthStepResponse(
            success=False,
            message=f"ตรวจใบหน้าไม่สำเร็จ: {live_result['message']}",
            next_step="liveness",
            session_token=request.session_token,
        )

    facial_profile = db.query(FacialProfile).filter(
        FacialProfile.user_id == user_id
    ).first()

    if not facial_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ไม่พบข้อมูลใบหน้า — กรุณาลงทะเบียนใบหน้าก่อน",
        )

    compare_result = compare_faces(
        stored_embedding=facial_profile.embedding,
        live_embedding=live_result["embedding"],
    )

    if not compare_result["match"]:
        return AuthStepResponse(
            success=False,
            message=f"Liveness ผ่าน แต่ใบหน้าไม่ตรง: {compare_result['message']}",
            next_step="liveness",
            session_token=request.session_token,
        )

    # ผ่านทั้ง Liveness + Face Identity
    session_token = create_access_token(
        data={
            "sub": payload["sub"],
            "user_id": user_id,
            "auth_step": 2,
        },
        expires_delta=timedelta(minutes=5),
    )

    return AuthStepResponse(
        success=True,
        message=f"Liveness + ใบหน้าผ่าน ✓ (confidence={compare_result['confidence']}%) — ขั้นตอนถัดไป: Multi-Pose Face",
        next_step="face",
        session_token=session_token,
    )

# FACE RECOGNITION ขั้นตอนที่ 3 เปรียบเทียบใบหน้าหลายมุม
REQUIRED_POSES = ["front", "left", "right", "up", "down"]
@router.post(
    "/auth/face",
    summary="ขั้น 3: เปรียบเทียบ Face Embedding หลายมุม (front, left, right, up, down)",
)
def verify_face(
    request: FaceVerifyRequest,
    db: Session = Depends(get_db),
):
    """
     Multi-Pose Face Recognition
    ขั้นตอน
    ตรวจ session_token (ต้องผ่าน step 2 แล้ว)
    สกัด embedding จากภาพ live
    เปรียบเทียบกับ embedding ที่เก็บไว้
    ถ้าตรงเพิ่มท่าปัจจุบันเข้า completed_poses
    ถ้าครบ 5 ท่า = ผ่าน ไปstep=3
    Frontend เรียก endpoint นี้ 5 ครั้ง (ท่าละ 1 ครั้ง)
    """
    payload = _validate_session_token(request.session_token, required_step=2)
    user_id = payload["user_id"]

    # ตรวจสอบว่า user ทำท่าตามที่สั่งจริง 
    pose_result = validate_pose(request.frame, request.pose)
    if not pose_result["valid"]:
        return {
            "success": False,
            "pose_passed": False,
            "current_pose": request.pose,
            "completed_poses": request.completed_poses,
            "remaining": len(REQUIRED_POSES) - len(request.completed_poses),
            "message": pose_result["message"],
            "session_token": request.session_token,
        }

    # สกัด embedding + ตรวจ face identity
    live_result = extract_embedding(request.frame)
    if not live_result["success"]:
        return {
            "success": False,
            "pose_passed": False,
            "current_pose": request.pose,
            "completed_poses": request.completed_poses,
            "remaining": len(REQUIRED_POSES) - len(request.completed_poses),
            "message": f"ไม่พบใบหน้า: {live_result['message']}",
            "session_token": request.session_token,
        }

    # ดึง embedding ที่เก็บไว้
    facial_profile = db.query(FacialProfile).filter(
        FacialProfile.user_id == user_id
    ).first()

    if not facial_profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ไม่พบข้อมูลใบหน้า — กรุณาลงทะเบียนใบหน้าก่อน",
        )

    # เปรียบเทียบ
    compare_result = compare_faces(
        stored_embedding=facial_profile.embedding,
        live_embedding=live_result["embedding"],
    )

    if not compare_result["match"]:
        return {
            "success": False,
            "pose_passed": False,
            "current_pose": request.pose,
            "completed_poses": request.completed_poses,
            "remaining": len(REQUIRED_POSES) - len(request.completed_poses),
            "message": f"ใบหน้าไม่ตรง ({request.pose}): {compare_result['message']}",
            "session_token": request.session_token,
        }

    # ท่านี้ผ่าน อัปเดต completed_poses 
    new_completed = list(set(request.completed_poses + [request.pose]))
    remaining_poses = [p for p in REQUIRED_POSES if p not in new_completed]

    if len(remaining_poses) == 0:
        #ผ่านครบ 5 ท่า step=3
        session_token = create_access_token(
            data={
                "sub": payload["sub"],
                "user_id": user_id,
                "auth_step": 3,
            },
            expires_delta=timedelta(minutes=5),
        )

        return {
            "success": True,
            "pose_passed": True,
            "all_passed": True,
            "current_pose": request.pose,
            "completed_poses": new_completed,
            "remaining": 0,
            "message": f"🎉 ใบหน้าผ่านครบ {len(new_completed)} มุม! (confidence={compare_result['confidence']}%)",
            "next_step": "behavioral",
            "session_token": session_token,
        }
    else:
        # ยังไม่ครบ return token เดิมให้ส่งท่าถัดไป
        return {
            "success": False,
            "pose_passed": True,
            "all_passed": False,
            "current_pose": request.pose,
            "completed_poses": new_completed,
            "remaining": len(remaining_poses),
            "next_pose": remaining_poses[0],
            "message": f"✓ {request.pose} ผ่าน ({len(new_completed)}/{len(REQUIRED_POSES)}) — ท่าถัดไป: {remaining_poses[0]}",
            "session_token": request.session_token,
        }



#  GET CHALLENGES  ดึงคำถาม cognitive challenge
@router.get(
    "/auth/challenges",
    summary="ดึง 3 คำถาม cognitive challenge แบบสุ่ม",
)
def get_challenges(
    session_token: str,
    db: Session = Depends(get_db)
):
    """
    สุ่ม 3 คำถามสำหรับ cognitive behavioral challenge
    ส่ง session_token เป็น query parameter
    """
    payload = _validate_session_token(session_token, required_step=3)
    user_id = payload["user_id"]
    
    user = db.query(User).filter(User.id == user_id).first()
    interests = user.interests if user else []

    full_questions, safe_questions = get_random_challenges(interests, n=3)

    return {
        "questions": safe_questions,
        "session_token": session_token,
    }

# BEHAVIORAL ขั้นตอนที่ 4 ตรวจสอบพฤติกรรม 
@router.post(
    "/auth/behavioral",
    response_model=AuthStepResponse,
    summary="ขั้น 4: ตรวจสอบพฤติกรรม (Z-score ของ reaction time)",
)
def verify_behavioral(
    request: BehavioralRequest,
    db: Session = Depends(get_db),
):
    """
   Cognitive Behavioral Verification
    ขั้นตอน
     ตรวจ session_token (ต้องผ่าน step 3 แล้ว)
     ตรวจคำตอบ (ถูก/ผิด)
     คำนวณ Z-score จาก reaction times
     ถ้า Z ≤ threshold → ผ่าน → ส่ง access_token สุดท้าย
     อัปเดต behavioral profile ด้วย Welford's algorithm
    """
    payload = _validate_session_token(request.session_token, required_step=3)
    user_id = payload["user_id"]

    # ตรวจคำตอบ
    answer_result = check_answers(
        [a.model_dump() for a in request.answers]
    )

    # บังคับว่าต้องตอบถูกอย่างน้อย 2 ใน 3 ข้อ
    if answer_result["correct_count"] < 2:
        return AuthStepResponse(
            success=False,
            message=f"Behavioral Verification ไม่ผ่าน: ตอบผิดเกินกำหนด (ถูก {answer_result['correct_count']}/{answer_result['total']}) การคลิกมั่วไม่ได้รับอนุญาต",
            next_step="behavioral",
            session_token=request.session_token,
        )

    # ดึง behavioral profile
    profile = db.query(BehavioralProfile).filter(
        BehavioralProfile.user_id == user_id
    ).first()

    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ไม่พบข้อมูลพฤติกรรม — กรุณาลงทะเบียนใหม่",
        )

    # คำนวณ Z-score แบบผสม
    verification = verify_hybrid_behavior(answer_result, profile.stats)

    if not verification["passed"]:
        return AuthStepResponse(
            success=False,
            message=f"Behavioral Verification ไม่ผ่าน: {verification['message']}",
            next_step="behavioral",
            session_token=request.session_token,
        )

    #  ผ่านทุกขั้นตอนแล้ว 

    # อัปเดต behavioral profile (rolling stats)
    profile.stats = update_hybrid_stats(profile.stats, answer_result)
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(profile, "stats")
    
    db.commit()

    # สร้าง access token จริง (ผ่าน 4 ขั้นตอนครบ)
    access_token = create_access_token(
        data={
            "sub": payload["sub"],
            "user_id": user_id,
            "auth_step": 4,
            "auth_complete": True,
        }
    )

    return AuthStepResponse(
        success=True,
        message=(
            f" ยืนยันตัวตนสำเร็จทั้ง 4 ขั้นตอน! "
            f"คำตอบถูก {answer_result['correct_count']}/{answer_result['total']} ข้อ, "
            f"{verification['message']}"
        ),
        next_step=None,  # จบแล้ว
        session_token=access_token,
    )
