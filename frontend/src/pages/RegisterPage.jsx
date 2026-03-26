import { useState, useRef, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Webcam from 'react-webcam';
import { registerUser, registerFace, registerBehavioral } from '../services/api';

/**
 * RegisterPage  หน้าลงทะเบียน 3 ขั้นตอน
 * 1 กรอกข้อมูล (username, email, password)
 * 2 ถ่ายภาพใบหน้า 5 มุม (หน้าตรง, หันซ้าย, หันขวา, เงยหน้า, ก้มหน้า)
 * 3 ตอบคำถาม cognitive challenge (สร้าง behavioral baseline)
 */

// 5 ท่าถ่ายภาพหน้า
const FACE_POSES = [
  { id: 'front', label: 'หน้าตรง', icon: '😐', instruction: 'มองตรงไปที่กล้อง' },
  { id: 'left', label: 'หันซ้าย', icon: '👈', instruction: 'หันหน้าไปทางซ้ายเล็กน้อย' },
  { id: 'right', label: 'หันขวา', icon: '👉', instruction: 'หันหน้าไปทางขวาเล็กน้อย' },
  { id: 'up', label: 'เงยหน้า', icon: '👆', instruction: 'เงยหน้าขึ้นเล็กน้อย' },
  { id: 'down', label: 'ก้มหน้า', icon: '👇', instruction: 'ก้มหน้าลงเล็กน้อย' },
];

// คำถาม Enrollment
const ENROLLMENT_QUESTIONS = [
  { id: 'math_1', question: '7 + 8 = ?', choices: ['13', '14', '15', '16'] },
  { id: 'math_3', question: '12 × 3 = ?', choices: ['33', '36', '39', '42'] },
  { id: 'math_5', question: '25 - 17 = ?', choices: ['6', '7', '8', '9'] },
];

export default function RegisterPage() {
  const navigate = useNavigate();
  const webcamRef = useRef(null);

  // State
  const [step, setStep] = useState(1); // 1=form, 2=face, 3=behavioral
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);

  // Step 1 Form
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    full_name: '',
  });

  // Step 2 Face — Multi-Pose capture
  const [currentPose, setCurrentPose] = useState(0);
  const [capturedFrames, setCapturedFrames] = useState([]); // [{pose, image}]
  const [previewImage, setPreviewImage] = useState(null);

  // Step 3 Behavioral
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [questionStartTime, setQuestionStartTime] = useState(null);

  // Handlers

  const handleInputChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  // Step 1 ส่งฟอร์มลงทะเบียน
  const handleRegister = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    try {
      await registerUser(formData);
      setMessage({ type: 'success', text: 'ลงทะเบียนสำเร็จ! ถ่ายภาพใบหน้า 5 มุมต่อ' });
      setStep(2);
      setCurrentPose(0);
      setCapturedFrames([]);
      setPreviewImage(null);
    } catch (err) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'เกิดข้อผิดพลาด',
      });
    } finally {
      setLoading(false);
    }
  };

  // Step 2 ถ่ายภาพแต่ละท่า
  const captureCurrentPose = useCallback(() => {
    const imageSrc = webcamRef.current?.getScreenshot();
    if (imageSrc) {
      setPreviewImage(imageSrc);
    }
  }, []);

  const confirmPose = () => {
    if (!previewImage) return;

    const pose = FACE_POSES[currentPose];
    const newFrames = [...capturedFrames, { pose: pose.id, image: previewImage }];
    setCapturedFrames(newFrames);
    setPreviewImage(null);

    if (currentPose < FACE_POSES.length - 1) {
      // ยังไม่ครบ  ไปท่าถัดไป
      setCurrentPose(currentPose + 1);
      setMessage({
        type: 'success',
        text: `✓ ${pose.label} บันทึกแล้ว (${newFrames.length}/${FACE_POSES.length})`,
      });
    } else {
      // ครบ 5 ท่าแล้ว  ส่งไป backend
      setMessage({ type: 'info', text: 'กำลังประมวลผลใบหน้า...' });
      submitAllFaces(newFrames);
    }
  };

  const retakeCurrentPose = () => {
    setPreviewImage(null);
  };

  const submitAllFaces = async (frames) => {
    setLoading(true);
    try {
      const base64Frames = frames.map((f) => f.image);
      const poseLabels = frames.map((f) => f.pose);

      await registerFace(formData.username, base64Frames, poseLabels);

      setMessage({ type: 'success', text: `บันทึกใบหน้า ${frames.length} มุมสำเร็จ! ตอบคำถามต่อ` });
      setStep(3);
      setCurrentQ(0);
      setAnswers([]);
      setQuestionStartTime(performance.now());
    } catch (err) {
      setMessage({
        type: 'error',
        text: err.response?.data?.detail || 'ไม่สามารถบันทึกใบหน้าได้',
      });
    } finally {
      setLoading(false);
    }
  };

  // Step 3 ตอบคำถาม cognitive challenge
  const handleAnswer = async (choiceIndex) => {
    const reactionTime = performance.now() - questionStartTime;
    const newAnswer = {
      question_id: ENROLLMENT_QUESTIONS[currentQ].id,
      selected_index: choiceIndex,
      reaction_time_ms: Math.round(reactionTime * 100) / 100,
    };
    const updatedAnswers = [...answers, newAnswer];
    setAnswers(updatedAnswers);

    if (currentQ < ENROLLMENT_QUESTIONS.length - 1) {
      setCurrentQ(currentQ + 1);
      setQuestionStartTime(performance.now());
    } else {
      setLoading(true);
      try {
        await registerBehavioral(formData.username, updatedAnswers);
        setMessage({
          type: 'success',
          text: `🎉 ลงทะเบียนเสร็จสิ้น! ระยะเวลาตอบของคุณถูกตั้งเป็นค่าเริ่มต้นแล้ว`,
        });
        setTimeout(() => navigate('/login'), 2000);
      } catch (err) {
        setMessage({
          type: 'error',
          text: err.response?.data?.detail || 'Behavioral registration failed',
        });
      } finally {
        setLoading(false);
      }
    }
  };

  // Render

  return (
    <div className="page-container">
      <div className="glass-card">
        {/* Header */}
        <div className="card-header">
          <h1>🔐 ลงทะเบียน</h1>
          <p>สร้างบัญชี Multi-Factor Digital ID</p>
        </div>

        {/* Progress */}
        <div className="progress-steps">
          {['ข้อมูล', 'ใบหน้า', 'พฤติกรรม'].map((label, i) => (
            <div className="step-item" key={i}>
              <div
                className={`step-circle ${step > i + 1 ? 'completed' : step === i + 1 ? 'active' : ''}`}
              >
                {step > i + 1 ? '✓' : i + 1}
              </div>
              {i < 2 && <div className={`step-connector ${step > i + 1 ? 'active' : ''}`} />}
            </div>
          ))}
        </div>

        {/* Messages */}
        {message && (
          <div className={`status-message ${message.type}`}>{message.text}</div>
        )}

        {/* Step 1 Form */}
        {step === 1 && (
          <form onSubmit={handleRegister}>
            <div className="form-group">
              <label>ชื่อผู้ใช้ (Username)</label>
              <input name="username" value={formData.username} onChange={handleInputChange} placeholder="john_doe" required minLength={3} />
            </div>
            <div className="form-group">
              <label>อีเมล</label>
              <input name="email" type="email" value={formData.email} onChange={handleInputChange} placeholder="john@example.com" required />
            </div>
            <div className="form-group">
              <label>รหัสผ่าน (อย่างน้อย 8 ตัว)</label>
              <input name="password" type="password" value={formData.password} onChange={handleInputChange} placeholder="••••••••" required minLength={8} />
            </div>
            <div className="form-group">
              <label>ชื่อ-นามสกุล (ไม่บังคับ)</label>
              <input name="full_name" value={formData.full_name} onChange={handleInputChange} placeholder="John Doe" />
            </div>
            <button className="btn btn-primary btn-full btn-lg" type="submit" disabled={loading}>
              {loading ? <span className="spinner" /> : 'ถัดไป →'}
            </button>
          </form>
        )}

        {/* Step 2 Multi-Pose Face Capture */}
        {step === 2 && (
          <div>
            {/* Pose Progress */}
            <div style={{ display: 'flex', justifyContent: 'center', gap: '6px', marginBottom: '16px' }}>
              {FACE_POSES.map((pose, i) => (
                <div
                  key={pose.id}
                  style={{
                    width: '40px',
                    height: '40px',
                    borderRadius: '50%',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: '1.2rem',
                    border: `2px solid ${i < capturedFrames.length ? 'var(--accent-success)' : i === currentPose ? 'var(--accent-primary)' : 'var(--border-glass)'}`,
                    background: i < capturedFrames.length ? 'rgba(16, 185, 129, 0.2)' : i === currentPose ? 'rgba(139, 92, 246, 0.2)' : 'transparent',
                    transition: 'all 0.3s ease',
                  }}
                  title={pose.label}
                >
                  {i < capturedFrames.length ? '✓' : pose.icon}
                </div>
              ))}
            </div>

            {/* Current Pose Instruction */}
            {currentPose < FACE_POSES.length && (
              <div className="status-message info" style={{ textAlign: 'center', fontSize: '1rem', fontWeight: 600 }}>
                {FACE_POSES[currentPose].icon} ท่าที่ {currentPose + 1}/{FACE_POSES.length}: {FACE_POSES[currentPose].instruction}
              </div>
            )}

            {/* Webcam / Preview */}
            <div className="webcam-container">
              {!previewImage ? (
                <>
                  <Webcam
                    ref={webcamRef}
                    audio={false}
                    screenshotFormat="image/jpeg"
                    mirrored
                    videoConstraints={{ facingMode: 'user', width: 480, height: 360 }}
                  />
                  <div className="webcam-overlay">
                    <div className="webcam-reticle" />
                  </div>
                  <div className="webcam-instruction">
                    {FACE_POSES[currentPose]?.instruction || 'เตรียมพร้อม'}
                  </div>
                </>
              ) : (
                <img src={previewImage} alt="captured" style={{ width: '100%', borderRadius: '12px' }} />
              )}
            </div>

            {/* Capture / Confirm Buttons */}
            {!previewImage ? (
              <button className="btn btn-primary btn-full btn-lg" onClick={captureCurrentPose}>
                📸 ถ่ายภาพ — {FACE_POSES[currentPose]?.label}
              </button>
            ) : (
              <div style={{ display: 'flex', gap: '12px' }}>
                <button className="btn btn-outline" onClick={retakeCurrentPose} style={{ flex: 1 }}>
                  ถ่ายใหม่
                </button>
                <button
                  className="btn btn-primary"
                  onClick={confirmPose}
                  disabled={loading}
                  style={{ flex: 2 }}
                >
                  {loading ? (
                    <span className="spinner" />
                  ) : currentPose < FACE_POSES.length - 1 ? (
                    `ยืนยัน → ท่าถัดไป (${currentPose + 2}/${FACE_POSES.length})`
                  ) : (
                    '✓ ยืนยัน & ส่งทั้งหมด'
                  )}
                </button>
              </div>
            )}

            {/* Captured Thumbnails */}
            {capturedFrames.length > 0 && (
              <div style={{ display: 'flex', gap: '8px', marginTop: '16px', justifyContent: 'center' }}>
                {capturedFrames.map((f, i) => (
                  <div key={i} style={{ textAlign: 'center' }}>
                    <img
                      src={f.image}
                      alt={f.pose}
                      style={{
                        width: '60px',
                        height: '45px',
                        objectFit: 'cover',
                        borderRadius: '6px',
                        border: '2px solid var(--accent-success)',
                      }}
                    />
                    <div style={{ fontSize: '0.65rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                      {FACE_POSES[i]?.label}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Step 3 Cognitive Challenge */}
        {step === 3 && currentQ < ENROLLMENT_QUESTIONS.length && (
          <div>
            <div className="challenge-card">
              <div className="question-number">
                คำถามที่ {currentQ + 1} / {ENROLLMENT_QUESTIONS.length}
              </div>
              <div className="question-text">{ENROLLMENT_QUESTIONS[currentQ].question}</div>
              <div className="choices-grid">
                {ENROLLMENT_QUESTIONS[currentQ].choices.map((choice, i) => (
                  <button key={i} className="choice-btn" onClick={() => handleAnswer(i)}>
                    {choice}
                  </button>
                ))}
              </div>
            </div>
            <div className="status-message info">⏱ ระบบจับเวลาตอบอัตโนมัติ — ตอบตามปกติ</div>
          </div>
        )}

        {/* Link */}
        <div className="text-center mt-24">
          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            มีบัญชีแล้ว?{' '}
            <Link to="/login" className="link-text">เข้าสู่ระบบ</Link>
          </span>
        </div>
      </div>
    </div>
  );
}
