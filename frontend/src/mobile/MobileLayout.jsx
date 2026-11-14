import { Outlet, Link, useNavigate, useLocation } from 'react-router-dom'
import './mobile.css'

export default function MobileLayout() {
  const nav = useNavigate()
  const loc = useLocation()

  return (
    <div className="mobile-app-root">
      {/* Thanh công cụ hỗ trợ người phát triển thử nghiệm trên Desktop */}
      <header className="mobile-dev-bar">
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ color: '#4ade80', fontWeight: 700 }}>📱 MOBILE PWA</span>
          <Link to="/m/splash">Splash</Link>
          <Link to="/m/onboarding">Tour</Link>
          <Link to="/m/login">Login</Link>
          <Link to="/m/home">Home</Link>
          <Link to="/m/map">Map</Link>
        </div>
        <div>
          <button onClick={() => nav('/bins')}>💻 Chế độ Web Desktop</button>
        </div>
      </header>

      {/* Khung điện thoại thông minh (Phone Device Shell) */}
      <main className="mobile-device-frame">
        <Outlet />
      </main>
    </div>
  )
}
