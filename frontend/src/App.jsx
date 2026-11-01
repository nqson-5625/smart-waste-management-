import { useState, useEffect } from 'react'
import { Routes, Route, NavLink, Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useQuery, useMutation } from '@tanstack/react-query'
import { api, auth } from './api'
import Login from './pages/Login'
import Bins from './pages/Bins'
import BinDetail from './pages/BinDetail'
import Stats from './pages/Stats'
import AlertBell from './components/AlertBell'

function Crumb() {
  const { pathname } = useLocation()
  if (pathname.startsWith('/bins/')) return <nav className="crumb">Trang chủ / <Link to="/bins">Xem lượng rác</Link> / <b>Chi tiết thùng</b></nav>
  return <nav className="crumb">Trang chủ / <b>{pathname === '/stats' ? 'Xem thống kê' : 'Xem lượng rác'}</b></nav>
}

function ChangePasswordModal({ onClose }) {
  const [f, setF] = useState({ current_password: '', new_password: '' })
  const [msg, setMsg] = useState('')
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const change = useMutation({
    mutationFn: () => api('POST', '/auth/change-password', f),
    onSuccess: () => {
      setMsg('Đổi mật khẩu thành công!')
      setTimeout(onClose, 1200)
    },
  })
  return (
    <div className="overlay" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h3>Đổi mật khẩu</h3>
        <label>Mật khẩu hiện tại
          <input type="password" required value={f.current_password} onChange={set('current_password')} placeholder="Nhập mật khẩu hiện tại" />
        </label>
        <label>Mật khẩu mới (tối thiểu 8 ký tự)
          <input type="password" required minLength={8} value={f.new_password} onChange={set('new_password')} placeholder="Nhập mật khẩu mới" />
        </label>
        {msg && <p className="hint" style={{ color: '#2e7d32', textAlign: 'center' }}>{msg}</p>}
        {change.error && <p className="err">{change.error.message}</p>}
        <div className="actions">
          <button className="btn red" onClick={onClose}>HỦY</button>
          <button className="btn blue" disabled={change.isPending || !f.current_password || f.new_password.length < 8} onClick={() => change.mutate()}>XÁC NHẬN</button>
        </div>
      </div>
    </div>
  )
}

function Layout() {
  const nav = useNavigate()
  const [showPwd, setShowPwd] = useState(false)
  if (!auth.token) return <Navigate to="/login" replace />

  // Khôi phục phiên và lấy roles mới nhất từ server
  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: () => api('GET', '/auth/me'),
    staleTime: 60000,
  })

  useEffect(() => {
    if (me && auth.token) {
      auth.set(auth.token, me)
    }
  }, [me])

  const logout = () => { auth.clear(); nav('/login') }
  const user = me || auth.user

  return (
    <div className="shell">
      <aside className="side">
        <h1>PHẦN MỀM QUẢN LÝ RÁC THẢI</h1>
        <p className="grp">ĐỔ RÁC</p>
        <NavLink to="/bins">Xem lượng rác</NavLink>
        <p className="grp">THỐNG KÊ</p>
        <NavLink to="/stats">Xem thống kê</NavLink>
      </aside>
      <div className="main">
        <header className="top">
          <Crumb />
          <div className="top-r">
            <AlertBell />
            <span>{user?.display_name}</span>
            <button className="link" onClick={() => setShowPwd(true)}>Đổi mật khẩu</button>
            <button className="link" onClick={logout}>Đăng xuất</button>
          </div>
        </header>
        <main className="content"><Outlet /></main>
      </div>
      {showPwd && <ChangePasswordModal onClose={() => setShowPwd(false)} />}
    </div>
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route element={<Layout />}>
        <Route path="/" element={<Navigate to="/bins" replace />} />
        <Route path="/bins" element={<Bins />} />
        <Route path="/bins/:id" element={<BinDetail />} />
        <Route path="/stats" element={<Stats />} />
      </Route>
    </Routes>
  )
}
