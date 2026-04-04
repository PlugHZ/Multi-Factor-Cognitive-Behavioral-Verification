import { useState, useRef, useEffect, useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import Webcam from 'react-webcam';
import {
  loginPassword,
  verifyLiveness,
  verifyFace,
  getChallenges,
  verifyBehavioral,
} from '../services/api';

/**
 * LoginPage  เข้าสู่ระบบ 4 ขั้นตอน
 * Step 1 Password — กรอก username + password
 * Step 2 Liveness + Face Identity — ตรวจคนจริง + ยืนยันว่าเป็นเจ้าของบัญชี (auto)
 * Step 3 Multi-Pose Face — ตรวจใบหน้า 5 มุม: หน้าตรง, ซ้าย, ขวา, เงย, ก้ม (auto)
 * Step 4 Behavioral — ตอบ 3 คำถาม (จับ reaction time)
 */

const STEP_LABELS = ['รหัสผ่าน', 'Liveness', 'ใบหน้า 5 มุม', 'พฤติกรรม'];
const AUTO_CAPTURE_INTERVAL = 1500;

const FACE_POSES = [
  { id: 'front', label: 'หน้าตรง', icon: '😐', instruction: 'มองตรงไปที่กล้อง' },
  { id: 'left', label: 'หันซ้าย', icon: '👈', instruction: 'หันหน้าไปทางซ้ายเล็กน้อย' },
  { id: 'right', label: 'หันขวา', icon: '👉', instruction: 'หันหน้าไปทางขวาเล็กน้อย' },
  { id: 'up', label: 'เงยหน้า', icon: '👆', instruction: 'เงยหน้าขึ้นเล็กน้อย' },
  { id: 'down', label: 'ก้มหน้า', icon: '👇', instruction: 'ก้มหน้าลงเล็กน้อย' },
];

export default function LoginPage() {
  const navigate = useNavigate();
  const webcamRef = useRef(null);
  const intervalRef = useRef(null);
  const checkingRef = useRef(false);

  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState(null);
  const [sessionToken, setSessionToken] = useState(null);

  // Step 1
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [livenessChallenge, setLivenessChallenge] = useState('blink');

  // Step 3 Multi-Pose Face
  const [currentPoseIndex, setCurrentPoseIndex] = useState(0);
  const [completedPoses, setCompletedPoses] = useState([]);

  // Step 4
  const [questions, setQuestions] = useState([]);
  const [currentQ, setCurrentQ] = useState(0);
  const [answers, setAnswers] = useState([]);
  const [questionStartTime, setQuestionStartTime] = useState(null);

  //  Cleanup interval on unmount 
  useEffect(() => {
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, []);

  // Stop any running auto-capture 
  const stopAutoCapture = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    checkingRef.current = false;
  }, []);

  // Step 2 Auto Liveness + Face Identity 
  const startLivenessAutoCapture = useCallback((token, challenge) => {
    stopAutoCapture();

    intervalRef.current = setInterval(async () => {
      if (checkingRef.current) return;
      const imageSrc = webcamRef.current?.getScreenshot();
      if (!imageSrc) return;

      checkingRef.current = true;
      try {
        const res = await verifyLiveness(token, imageSrc, challenge);
        const data = res.data;

        if (data.success) {
          stopAutoCapture();
          setSessionToken(data.session_token);
          setMessage({ type: 'success', text: data.message });
          setCurrentPoseIndex(0);
          setCompletedPoses([]);
          setStep(3);
          // เริ่ม auto face ท่าแรก
          setTimeout(() => startFaceAutoCapture(data.session_token, 0, []), 1000);
          return;
        } else {
          setMessage({ type: 'info', text: data.message });
        }
      } catch (err) {
        console.log('Liveness check:', err.message);
      }
      checkingRef.current = false;
    }, AUTO_CAPTURE_INTERVAL);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stopAutoCapture]);

  // Step 3 Auto Multi-Pose Face 
  const startFaceAutoCapture = useCallback((token, poseIdx, donePoses) => {
    stopAutoCapture();
    const pose = FACE_POSES[poseIdx];
    if (!pose) return;

    intervalRef.current = setInterval(async () => {
      if (checkingRef.current) return;
      const imageSrc = webcamRef.current?.getScreenshot();
      if (!imageSrc) return;

      checkingRef.current = true;
      try {
        const res = await verifyFace(token, imageSrc, pose.id, donePoses);
        const data = res.data;

        if (data.pose_passed) {
          const newCompleted = data.completed_poses || [...donePoses, pose.id];
          setCompletedPoses(newCompleted);

          if (data.all_passed) {
            // ครบ 5 ท่า
            stopAutoCapture();
            setSessionToken(data.session_token);
            setMessage({ type: 'success', text: data.message });
            await loadChallengesAndGoStep4(data.session_token);
            return;
          } else {
            // ผ่านท่านี้  ไปท่าถัดไป
            const nextIdx = poseIdx + 1;
            setCurrentPoseIndex(nextIdx);
            setMessage({ type: 'success', text: data.message });
            stopAutoCapture();
            setTimeout(() => startFaceAutoCapture(token, nextIdx, newCompleted), 800);
            checkingRef.current = false;
            return;
          }
        } else {
          setMessage({ type: 'info', text: data.message || `กำลังตรวจ ${pose.label}...` });
        }
      } catch (err) {
        console.log('Face check:', err.message);
      }
      checkingRef.current = false;
    }, AUTO_CAPTURE_INTERVAL);
  }, [stopAutoCapture]);

  // โหลดคำถาม  ไป step 4
  const loadChallengesAndGoStep4 = async (token) => {
    try {
      const res = await getChallenges(token);
      setQuestions(res.data.questions);
    } catch {
      setQuestions([
        { id: 1, question: '7 + 8 = ?', choices: ['13', '14', '15', '16'] },
        { id: 3, question: '12 × 3 = ?', choices: ['33', '36', '39', '42'] },
        { id: 5, question: '25 - 17 = ?', choices: ['6', '7', '8', '9'] },
      ]);
    }
    setCurrentQ(0);
    setAnswers([]);
    setQuestionStartTime(performance.now());
    setStep(4);
  };

  // Step 1 Password 
  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMessage(null);

    try {
      const res = await loginPassword(username, password);
      const data = res.data;
      setSessionToken(data.session_token);

      const challenge = data.message?.includes('blink') ? 'blink' : 'turn_head';
      setLivenessChallenge(challenge);
      setMessage({ type: 'success', text: data.message });
      setStep(2);
      setTimeout(() => startLivenessAutoCapture(data.session_token, challenge), 1500);
    } catch (err) {
      setMessage({ type: 'error', text: err.response?.data?.detail || 'เข้าสู่ระบบล้มเหลว' });
    } finally {
      setLoading(false);
    }
  };

  //Step 4 Cognitive Challenge 
  const handleChallengeAnswer = async (choiceIndex) => {
    const reactionTime = performance.now() - questionStartTime;
    const currentQuestion = questions[currentQ];
    const newAnswer = {
      question_id: currentQuestion.id,
      type: currentQuestion.type, // เพิ่ม type เพื่อให้ backend แยกแยะได้
      selected_index: choiceIndex,
      reaction_time_ms: Math.round(reactionTime * 100) / 100,
    };
    const updatedAnswers = [...answers, newAnswer];
    setAnswers(updatedAnswers);

    if (currentQ < questions.length - 1) {
      setCurrentQ(currentQ + 1);
      setQuestionStartTime(performance.now());
    } else {
      setLoading(true);
      setMessage(null);
      try {
        const res = await verifyBehavioral(sessionToken, updatedAnswers);
        const data = res.data;
        if (data.success) {
          setMessage({ type: 'success', text: data.message });
          localStorage.setItem('access_token', data.session_token);
          localStorage.setItem('username', username);
          setTimeout(() => navigate('/dashboard'), 1500);
        } else {
          setMessage({ type: 'error', text: data.message });
        }
      } catch (err) {
        setMessage({ type: 'error', text: err.response?.data?.detail || 'Behavioral Verification ล้มเหลว' });
      } finally {
        setLoading(false);
      }
    }
  };

  //  Render 
  const currentPose = FACE_POSES[currentPoseIndex];

  return (
    <div className="page-container">
      <div className="glass-card">
        <div className="card-header">
          <h1>🔑 เข้าสู่ระบบ</h1>
          <p>Multi-Factor Authentication (4 ขั้นตอน)</p>
        </div>

        {/* Progress Steps */}
        <div className="progress-steps">
          {STEP_LABELS.map((label, i) => (
            <div className="step-item" key={i}>
              <div className={`step-circle ${step > i + 1 ? 'completed' : step === i + 1 ? 'active' : ''}`}>
                {step > i + 1 ? '✓' : i + 1}
              </div>
              {i < 3 && <div className={`step-connector ${step > i + 1 ? 'active' : ''}`} />}
            </div>
          ))}
        </div>

        {message && <div className={`status-message ${message.type}`}>{message.text}</div>}

        {/* Step 1 Password */}
        {step === 1 && (
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>ชื่อผู้ใช้</label>
              <input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="username" required />
            </div>
            <div className="form-group">
              <label>รหัสผ่าน</label>
              <input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required />
            </div>
            <button className="btn btn-primary btn-full btn-lg" type="submit" disabled={loading}>
              {loading ? <span className="spinner" /> : '🔓 ตรวจสอบรหัสผ่าน'}
            </button>
          </form>
        )}

        {/* Step 2 Liveness + Face Identity (Auto) */}
        {step === 2 && (
          <div>
            <div className="status-message warning" style={{ textAlign: 'center', fontSize: '1rem', fontWeight: 600 }}>
              {livenessChallenge === 'blink'
                ? '👁 กรุณากะพริบตา — ระบบตรวจ Liveness + ยืนยันใบหน้าอัตโนมัติ'
                : '↔ กรุณาหันหน้าไปด้านข้าง — ระบบตรวจ Liveness + ยืนยันใบหน้าอัตโนมัติ'}
            </div>
            <div className="webcam-container">
              <Webcam ref={webcamRef} audio={false} screenshotFormat="image/jpeg" mirrored
                videoConstraints={{ facingMode: 'user', width: 480, height: 360 }} />
              <div className="webcam-overlay"><div className="webcam-reticle" /></div>
            </div>
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', animation: 'pulse 2s infinite' }}>
              ⏳ ตรวจ Liveness + ใบหน้าทุก {AUTO_CAPTURE_INTERVAL / 1000}s อัตโนมัติ — ป้องกันคนอื่นกะพริบแทน
            </div>
          </div>
        )}

        {/* Step 3 Multi-Pose Face (Auto) */}
        {step === 3 && (
          <div>
            {/* Pose Progress Circles */}
            <div style={{ display: 'flex', justifyContent: 'center', gap: '6px', marginBottom: '16px' }}>
              {FACE_POSES.map((pose, i) => (
                <div key={pose.id} style={{
                  width: '40px', height: '40px', borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.2rem',
                  border: `2px solid ${completedPoses.includes(pose.id) ? 'var(--accent-success)' : i === currentPoseIndex ? 'var(--accent-primary)' : 'var(--border-glass)'}`,
                  background: completedPoses.includes(pose.id) ? 'rgba(16, 185, 129, 0.2)' : i === currentPoseIndex ? 'rgba(139, 92, 246, 0.2)' : 'transparent',
                  transition: 'all 0.3s ease',
                }} title={pose.label}>
                  {completedPoses.includes(pose.id) ? '✓' : pose.icon}
                </div>
              ))}
            </div>

            {/* Current Pose Instruction */}
            {currentPose && (
              <div className="status-message info" style={{ textAlign: 'center', fontSize: '1rem', fontWeight: 600 }}>
                {currentPose.icon} ท่าที่ {currentPoseIndex + 1}/{FACE_POSES.length}: {currentPose.instruction}
              </div>
            )}

            <div className="webcam-container">
              <Webcam ref={webcamRef} audio={false} screenshotFormat="image/jpeg" mirrored
                videoConstraints={{ facingMode: 'user', width: 480, height: 360 }} />
              <div className="webcam-overlay"><div className="webcam-reticle" /></div>
              <div className="webcam-instruction">
                🔍 {currentPose?.instruction || 'กำลังตรวจ...'}
              </div>
            </div>
            <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.8rem', animation: 'pulse 2s infinite' }}>
              ⏳ ตรวจใบหน้าทุก {AUTO_CAPTURE_INTERVAL / 1000}s — ทำตามคำแนะนำแล้วระบบตรวจเอง
            </div>
          </div>
        )}

        {/* Step 4 Cognitive Challenge */}
        {step === 4 && questions.length > 0 && currentQ < questions.length && (
          <div>
            <div className="challenge-card">
              <div className="question-number">คำถามที่ {currentQ + 1} / {questions.length}</div>
              <div className="question-text">{questions[currentQ].question}</div>
              <div className="choices-grid">
                {questions[currentQ].choices.map((choice, i) => (
                  <button key={i} className="choice-btn" onClick={() => handleChallengeAnswer(i)} disabled={loading}>
                    {choice}
                  </button>
                ))}
              </div>
            </div>
            <div className="status-message info">⏱ ระบบจับเวลาตอบด้วย performance.now()</div>
          </div>
        )}

        <div className="text-center mt-24">
          <span style={{ color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            ยังไม่มีบัญชี?{' '}<Link to="/register" className="link-text">ลงทะเบียน</Link>
          </span>
        </div>
      </div>
    </div>
  );
}
