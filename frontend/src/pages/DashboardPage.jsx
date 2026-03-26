import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';

/**
 * DashboardPage  หน้าหลังเข้าสู่ระบบสำเร็จ
 * แสดงข้อมูลการยืนยันตัวตนและสถิติ
 */
export default function DashboardPage() {
  const navigate = useNavigate();
  const [username] = useState(() => localStorage.getItem('username') || 'User');

  useEffect(() => {
    const token = localStorage.getItem('access_token');

    if (!token) {
      navigate('/login');
    }
  }, [navigate]);

  const handleLogout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('username');
    navigate('/login');
  };

  return (
    <div className="page-container wide">
      <div className="glass-card">
        <div className="dashboard-welcome" style={{ animation: 'successPop 0.5s ease-out' }}>
          <div className="welcome-icon">🎉</div>
          <h1>ยินดีต้อนรับ, {username}!</h1>
          <p>คุณผ่านการยืนยันตัวตนทั้ง 4 ขั้นตอนเรียบร้อยแล้ว</p>
        </div>

        <div className="dashboard-stats">
          <div className="stat-card">
            <div className="stat-icon">🔐</div>
            <div className="stat-value">✓</div>
            <div className="stat-label">Password Verified</div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">👁</div>
            <div className="stat-value">✓</div>
            <div className="stat-label">Liveness Detected</div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">📷</div>
            <div className="stat-value">✓</div>
            <div className="stat-label">Face Matched</div>
          </div>
          <div className="stat-card">
            <div className="stat-icon">🧠</div>
            <div className="stat-value">✓</div>
            <div className="stat-label">Behavioral OK</div>
          </div>
        </div>

        <div className="text-center mt-24">
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '20px' }}>
            ระบบ Multi-Factor Digital Identification with Cognitive Behavioral Verification<br />
            ผ่านการตรวจสอบ 3 ปัจจัย: สิ่งที่คุณ<strong>รู้</strong> + สิ่งที่คุณ<strong>เป็น</strong> + สิ่งที่คุณ<strong>ทำ</strong>
          </p>

          <button className="btn btn-danger btn-lg" onClick={handleLogout}>
            🚪 ออกจากระบบ
          </button>
        </div>
      </div>
    </div>
  );
}
