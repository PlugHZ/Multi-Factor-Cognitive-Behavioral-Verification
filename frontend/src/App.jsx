import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import RegisterPage from './pages/RegisterPage';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';

function Navbar() {
  const location = useLocation();

  return (
    <nav className="navbar">
      <Link to="/" className="navbar-brand">
        🛡️ Digital ID
      </Link>
      <div className="navbar-links">
        <Link to="/register" className={location.pathname === '/register' ? 'active' : ''}>
          ลงทะเบียน
        </Link>
        <Link to="/login" className={location.pathname === '/login' ? 'active' : ''}>
          เข้าสู่ระบบ
        </Link>
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <div className="app-container">
        <Navbar />
        <Routes>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
