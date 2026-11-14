import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { api, auth } from '../api'

export default function Login() {
  const nav = useNavigate()
  const [f, setF] = useState({ email: '', password: '' })
  const [err, setErr] = useState('')
  const submit = async e => {
    e.preventDefault(); setErr('')
    try {
      const r = await api('POST', '/auth/login', f)
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
        <button className="btn blue">Đăng nhập</button>
        <div style={{ marginTop: '8px', fontSize: '12px', color: '#6b7280', textAlign: 'center', lineHeight: 1.5 }}>
          <b>Tài khoản thử nghiệm:</b><br />
          • <code>admin@smartwaste.local</code> (Quản trị viên)<br />
          • <code>collector@smartwaste.local</code> (Người thu gom)
        </div>
      </form>
    </div>
  )
}
