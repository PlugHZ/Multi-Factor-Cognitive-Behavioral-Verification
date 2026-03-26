"""
Cognitive Behavioral Verification Service
จัดการคำถาม cognitive challenge และตรวจสอบ reaction time
รองรับ Hybrid Type: 'math' และ 'visual' (Emoji Search)
"""

import os
import random
import numpy as np
from typing import List, Tuple, Dict
from dotenv import load_dotenv

load_dotenv()

ZSCORE_THRESHOLD = float(os.getenv("ZSCORE_THRESHOLD", "2.0"))


# คลังคำถาม
MATH_BANK = [
    {"id": "math_1", "question": "7 + 8 = ?", "choices": ["13", "14", "15", "16"], "correct_index": 2},
    {"id": "math_2", "question": "สีตรงข้ามของ 'แดง' คือสีอะไร?", "choices": ["น้ำเงิน", "เขียว", "เหลือง", "ม่วง"], "correct_index": 1},
    {"id": "math_3", "question": "12 × 3 = ?", "choices": ["33", "36", "39", "42"], "correct_index": 1},
    {"id": "math_4", "question": "ตัวอักษรถัดไปจาก A, C, E คือ?", "choices": ["F", "G", "H", "I"], "correct_index": 1},
    {"id": "math_5", "question": "25 - 17 = ?", "choices": ["6", "7", "8", "9"], "correct_index": 2},
    {"id": "math_6", "question": "คำไหนต่างจากพวก? แมว, สุนัข, ปลา, โต๊ะ", "choices": ["แมว", "สุนัข", "ปลา", "โต๊ะ"], "correct_index": 3},
    {"id": "math_7", "question": "9 × 9 = ?", "choices": ["72", "79", "81", "89"], "correct_index": 2},
    {"id": "math_8", "question": "100 ÷ 4 = ?", "choices": ["20", "25", "30", "40"], "correct_index": 1},
]

# คลัง Emoji 30 ตัว (ใช้เป็นหมวดหมู่ได้)
EMOJI_BANK = [
    "🐶", "🐱", "🐰", "🦊", "🐻", "🐼", "🐨", "🐯",
    "🍔", "🍕", "🌭", "🍟", "🌮", "🍣", "🍩", "🍦",
    "⚽", "🏀", "🏈", "🎾", "🏐", "🎱", "🏓", "🏸",
    "🚗", "🚕", "🚙", "🚌", "🚓", "🚑", "🚒", "🚐"
]

def generate_visual_challenge(user_interests: List[str]) -> dict:
    """สร้างคำถามแบบค้นหาภาพจากความสนใจของผู้ใช้ (ไม่บอกเป้าหมาย)"""
    #  สุ่มเป้าหมาย 1 อันจาก interests
    if not user_interests:
        user_interests = random.sample(EMOJI_BANK, 3)
        
    target_emoji = random.choice(user_interests)
    
    #  หาภาพหลอก (ต้องไม่ซ้ำกับ interests ทุกตัว เพื่อให้มีแค่ 1 ตัวที่ถูก)
    distractors = [e for e in EMOJI_BANK if e not in user_interests]
    chosen_distractors = random.sample(distractors, 8)  # grid 3x3 = 9 ช่อง
    
    #  นำมารวมกันแล้วสับเปลี่ยน
    all_choices = chosen_distractors + [target_emoji]
    random.shuffle(all_choices)
    
    correct_index = all_choices.index(target_emoji)
    
    # ซ่อนคำตอบไว้ใน ID (Stateless)
    salt = str(random.randint(1000, 9999))
    question_id = f"visual_{correct_index}_{salt}"
    
    return {
        "id": question_id,
        "type": "visual",
        "question": "ค้นหาสิ่งที่คุณเลือกไว้ตอนสมัคร",
        "choices": all_choices,
        "correct_index": correct_index
    }

def get_random_challenges(user_interests: List[str] = None, n: int = 3) -> Tuple[list, list]:
    """สุ่มคำถามผสม math และ visual"""
    questions = []
    
    for _ in range(n):
        # สุ่มว่าข้อนี้จะเป็นแบบไหน (50/50 ถ้ามี interests, ถ้าไม่มีเอาแต่ math ไปก่อน)
        if user_interests and random.random() > 0.4:
            q = generate_visual_challenge(user_interests)
        else:
            q = random.choice(MATH_BANK)
            while q in questions:
                q = random.choice(MATH_BANK)
            q = dict(q)
            q["type"] = "math"
            
        questions.append(q)

    # สร้าง copy ที่ปลอดภัย (เอา correct_index ออก)
    safe_questions = []
    for q in questions:
        safe_questions.append({
            "id": q["id"],
            "type": q["type"],
            "question": q["question"],
            "choices": q["choices"]
        })

    return questions, safe_questions


def check_answers(answers: list) -> dict:
    """
    ตรวจคำตอบแบบผสมรองรับการถอดรหัสจาก ID
    """
    math_map = {q["id"]: q for q in MATH_BANK}
    
    correct_count = 0
    math_times = []
    visual_times = []

    for ans in answers:
        q_id = str(ans["question_id"])
        q_type = ans["type"]
        selected = ans["selected_index"]
        rtime = ans["reaction_time_ms"]
        
        is_correct = False
        
        if q_type == "math":
            if q_id in math_map and math_map[q_id]["correct_index"] == selected:
                is_correct = True
            math_times.append(rtime)
            
        elif q_type == "visual":
            # ถอดรหัส ID: visual_{correct_index}_{target}_{salt}
            parts = q_id.split('_')
            if len(parts) >= 2 and parts[1].isdigit():
                actual_correct = int(parts[1])
                if actual_correct == selected:
                    is_correct = True
            visual_times.append(rtime)
            
        if is_correct:
            correct_count += 1

    return {
        "correct_count": correct_count,
        "total": len(answers),
        "math_times": math_times,
        "visual_times": visual_times,
    }


def calculate_zscore(
    session_times: List[float],
    stored_mean: float,
    stored_std: float,
    sample_count: int = 0,
) -> Tuple[float, bool]:
    """คำนวณ Z-score เดี่ยว (อนุโลมเมื่อ sample น้อย)"""
    if not session_times:
        return 0.0, True
        
    session_mean = float(np.median(session_times))  # ใช้ Median ลด Outlier
    
    # ป้องกัน SD ต่ำเกินไปจน fail ง่าย — ยิ่ง sample น้อย ยิ่งต้องอนุโลม
    min_std = 500.0
    effective_std = max(stored_std, min_std)
    
    if effective_std == 0:
        return 0.0, True

    z_score = abs(session_mean - stored_mean) / effective_std
    
    # อนุโลม threshold สำหรับ profile ใหม่ที่ sample น้อย (≤6)
    threshold = ZSCORE_THRESHOLD
    if sample_count <= 6:
        threshold = ZSCORE_THRESHOLD * 2.5  # เช่น 2.0 * 2.5 = 5.0 — ผ่อนปรนมาก
    elif sample_count <= 15:
        threshold = ZSCORE_THRESHOLD * 1.5  # เช่น 2.0 * 1.5 = 3.0
    
    passed = z_score <= threshold
    
    # ปรับปรุง Human Limit (บอท/AFK)
    if session_mean < 200 or session_mean > 15000:
        passed = False
        
    return round(z_score, 4), passed


def verify_hybrid_behavior(
    reaction_times_dict: dict, 
    stored_stats: dict
) -> dict:
    """
    ตรวจสอบแยกประเภท (math, visual) แล้วนำมา Evaluate รวมกัน
    ถ้าหมวดไหนไม่มี baseline (n=0) จะข้ามไม่ตรวจ (ถือว่าผ่านหมวดนั้น)
    """
    m_times = reaction_times_dict.get("math_times", [])
    v_times = reaction_times_dict.get("visual_times", [])
    
    m_stat = stored_stats.get("math", {"mean": 0.0, "std": 0.0, "n": 0})
    v_stat = stored_stats.get("visual", {"mean": 0.0, "std": 0.0, "n": 0})
    
    all_passed = True
    messages = []
    
    if m_times:
        if m_stat["n"] > 0:
            z_m, pass_m = calculate_zscore(m_times, m_stat["mean"], m_stat["std"], m_stat["n"])
            all_passed = all_passed and pass_m
            messages.append(f"Math (Z={z_m:.2f}, n={m_stat['n']}) {'✓' if pass_m else '✗'}")
        else:
            messages.append("Math (no baseline, skip) ✓")
        
    if v_times:
        if v_stat["n"] > 0:
            z_v, pass_v = calculate_zscore(v_times, v_stat["mean"], v_stat["std"], v_stat["n"])
            all_passed = all_passed and pass_v
            messages.append(f"Visual (Z={z_v:.2f}, n={v_stat['n']}) {'✓' if pass_v else '✗'}")
        else:
            messages.append("Visual (no baseline, skip) ✓")
        
    return {
        "passed": all_passed,
        "message": " | ".join(messages) if messages else "ไม่มีข้อมูลให้ตรวจ (ถือว่าผ่าน)"
    }


def update_single_stat(old_stat: dict, new_times: List[float]) -> dict:
    """อัปเดต stat ตัวเดียวด้วย Welford's algorithm"""
    if not new_times:
        return old_stat
        
    mean = old_stat.get("mean", 0.0)
    std = old_stat.get("std", 0.0)
    n = old_stat.get("n", 0)
    
    m2 = (std ** 2) * n if n > 0 else 0.0
    
    for x in new_times:
        n += 1
        delta = x - mean
        mean += delta / n
        m2 += delta * (x - mean)
        
    new_std = float(np.sqrt(m2 / n)) if n > 0 else 0.0
    return {"mean": round(mean, 4), "std": round(new_std, 4), "n": n}


def update_hybrid_stats(old_stats: dict, reaction_times_dict: dict) -> dict:
    """อัปเดต stats ทั้ง math และ visual"""
    new_stats = {}
    
    m_stat = old_stats.get("math", {"mean": 0.0, "std": 0.0, "n": 0})
    new_stats["math"] = update_single_stat(m_stat, reaction_times_dict.get("math_times", []))
    
    v_stat = old_stats.get("visual", {"mean": 0.0, "std": 0.0, "n": 0})
    new_stats["visual"] = update_single_stat(v_stat, reaction_times_dict.get("visual_times", []))
    
    return new_stats
