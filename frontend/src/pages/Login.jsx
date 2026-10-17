import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
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
        <h2>Đăng nhập</h2>
        <input placeholder="Email" type="email" required value={f.email} onChange={e => setF({ ...f, email: e.target.value })} />
        <input placeholder="Mật khẩu" type="password" required value={f.password} onChange={e => setF({ ...f, password: e.target.value })} />
        {err && <p className="err">{err}</p>}
        <button className="btn blue">Đăng nhập</button>
      </form>
    </div>
  )
}
