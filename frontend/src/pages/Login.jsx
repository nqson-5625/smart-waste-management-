import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api, auth } from '../api'

export default function Login() {
  const nav = useNavigate()
  const [f, setF] = useState({ email: '', password: '' })
  const [err, setErr] = useState('')
  const [collectorNotice, setCollectorNotice] = useState(null)
  const submit = async e => {
    e.preventDefault(); setErr(''); setCollectorNotice(null)
    try {
      const r = await api('POST', '/auth/login', f)
      const isCollector = r.user?.roles?.includes('collector') && !r.user?.roles?.includes('admin')
      if (isCollector) {
        setCollectorNotice(r)
        return
      }
      auth.set(r.access_token, r.user); nav('/bins')
    } catch (x) { setErr(x.status === 401 ? 'Email hoặc mật khẩu không đúng, hoặc tài khoản chưa được kích hoạt.' : x.message) }
  }
  return (
    <div className="login">
      <form className="card" onSubmit={submit}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <h2>Đăng nhập</h2>
          <Link to="/m/splash" style={{ fontSize: '12px', color: '#2e7d32', fontWeight: 700, textDecoration: 'none', background: '#e8f5e9', padding: '4px 8px', borderRadius: '12px' }}>
            📱 Bản Mobile
          </Link>
        </div>
        <input placeholder="Email" type="email" required value={f.email} onChange={e => setF({ ...f, email: e.target.value })} />
        <input placeholder="Mật khẩu" type="password" required value={f.password} onChange={e => setF({ ...f, password: e.target.value })} />
        {err && <p className="err">{err}</p>}
        {collectorNotice && (
          <div style={{ background: '#fef2f2', border: '1px solid #fecaca', borderRadius: 6, padding: '10px 12px', fontSize: '13px', color: '#991b1b' }}>
            <p style={{ margin: '0 0 8px', fontWeight: 600 }}>Tài khoản Người thu gom chỉ dùng trên giao diện Mobile.</p>
            <button
              type="button"
              className="btn green"
              style={{ background: '#2e7d32', width: '100%', padding: '8px' }}
              onClick={() => {
                auth.set(collectorNotice.access_token, collectorNotice.user)
                nav('/m/home')
              }}
            >
              📱 Chuyển sang Bản Mobile PWA
            </button>
          </div>
        )}
        <button className="btn blue">Đăng nhập</button>
        <div style={{ marginTop: '8px', fontSize: '12px', color: '#6b7280', textAlign: 'center', lineHeight: 1.5 }}>
          <b>Tài khoản quản trị web:</b><br />
          • <code>admin@smartwaste.local</code> (Quản trị viên)<br />
          <span style={{ fontSize: '11px', color: '#9ca3af' }}>(Tài khoản <code>collector@smartwaste.local</code> vui lòng dùng trên Bản Mobile)</span>
        </div>
      </form>
    </div>
  )
}
