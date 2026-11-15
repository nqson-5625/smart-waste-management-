import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { User, Lock, Eye, EyeOff } from 'lucide-react'
import { api, auth } from '../api'
import ImagePlaceholder from './ImagePlaceholder'

export default function MobileLogin() {
  const nav = useNavigate()
  const [f, setF] = useState({ email: 'collector@smartwaste.local', password: 'password123' })
  const [showPwd, setShowPwd] = useState(false)
  const [err, setErr] = useState('')
  const [loading, setLoading] = useState(false)
  const [showSignUpModal, setShowSignUpModal] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setErr('')
    setLoading(true)
    try {
      const res = await api('POST', '/auth/login', { email: f.email, password: f.password })
      // Mobile chỉ dành riêng cho người thu gom
      if (!res.user?.roles?.includes('collector')) {
        auth.clear()
        setErr('Tài khoản này là Quản trị viên. Giao diện Mobile chỉ dành riêng cho Người thu gom (Collector). Vui lòng sử dụng Giao diện Web Desktop.')
        return
      }
      auth.set(res.access_token, res.user)
      nav('/m/home', { replace: true })
    } catch (error) {
      setErr(error.message || 'Đăng nhập không thành công')
    } finally {
      setLoading(false)
    }
  }

  const fillAccount = (email) => {
    setF({ email, password: 'password123' })
  }

  return (
    <div className="m-login-container">
      {/* Header ảnh thực tế thùng rác ngoài trời (Placeholder giữ chỗ) */}
      <div className="m-login-header-img">
        <ImagePlaceholder
          src="/images/smart-bin-hero.jpg"
          label="Ảnh thực tế thùng rác công cộng"
          iconType="bin"
        />
      </div>

      {/* Khung nội dung đăng nhập bo tròn kéo lên */}
      <div className="m-login-card-sheet">
        <h2 className="m-login-title">Welcome to Smart Garbaging!</h2>
        <p className="m-login-sub">Sign in to your account</p>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column' }}>
          {/* Input Account name */}
          <div className="m-input-field">
            <User size={19} color="#9ca3af" />
            <input
              type="text"
              placeholder="Account name / Email"
              required
              value={f.email}
              onChange={(e) => setF({ ...f, email: e.target.value })}
            />
          </div>

          {/* Input Password */}
          <div className="m-input-field">
            <Lock size={19} color="#9ca3af" />
            <input
              type={showPwd ? 'text' : 'password'}
              placeholder="Password"
              required
              value={f.password}
              onChange={(e) => setF({ ...f, password: e.target.value })}
            />
            <button
              type="button"
              onClick={() => setShowPwd(!showPwd)}
              style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: '#9ca3af' }}
            >
              {showPwd ? <EyeOff size={18} /> : <Eye size={18} />}
            </button>
          </div>

          {err && (
            <p style={{ color: '#d32f2f', fontSize: 13, margin: '0 0 12px', textAlign: 'center' }}>
              {err}
            </p>
          )}

          <button className="m-btn-login" type="submit" disabled={loading}>
            {loading ? 'Đang xác thực…' : 'Login'}
          </button>

          {/* Nút chuyển sang Đăng ký */}
          <div className="m-login-footer">
            Don't have a account?{' '}
            <span onClick={() => setShowSignUpModal(true)}>Sign Up</span>
          </div>

          {/* Gợi ý tài khoản demo */}
          <div style={{ marginTop: 20, padding: 12, background: '#f8fafc', borderRadius: 12, border: '1px solid #f1f5f9', fontSize: 12, color: '#64748b' }}>
            <div style={{ fontWeight: 700, marginBottom: 4, color: '#334155' }}>Tài khoản Người thu gom:</div>
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <button
                type="button"
                onClick={() => fillAccount('collector@smartwaste.local')}
                style={{ background: '#e8f5e9', color: '#2e7d32', border: '1px solid #c8e6c9', borderRadius: 8, padding: '6px 12px', fontSize: 12, fontWeight: 700, cursor: 'pointer' }}
              >
                🚛 collector@smartwaste.local
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Modal Sign Up giải thích */}
      {showSignUpModal && (
        <div className="m-permission-overlay" onClick={() => setShowSignUpModal(false)}>
          <div className="m-permission-card" onClick={(e) => e.stopPropagation()}>
            <h3 style={{ margin: '0 0 10px', fontSize: 18, color: '#1f2937' }}>Đăng ký tài khoản (Sign Up)</h3>
            <p style={{ fontSize: 13, color: '#4b5563', lineHeight: 1.5, margin: '0 0 18px' }}>
              Hệ thống Smart Waste là ứng dụng nội bộ dành cho nhân viên điều phối và đội ngũ thu gom rác thực địa.
              Tài khoản mới sẽ được Quản trị viên (Admin) cấp phát trực tiếp.
            </p>
            <button
              className="m-btn-login"
              style={{ width: '100%', padding: '10px' }}
              onClick={() => setShowSignUpModal(false)}
            >
              Đã hiểu
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
