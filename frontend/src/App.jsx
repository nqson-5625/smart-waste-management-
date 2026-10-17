import { Routes, Route, NavLink, Link, Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { auth } from './api'
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

function Layout() {
  const nav = useNavigate()
  if (!auth.token) return <Navigate to="/login" replace />
  const logout = () => { auth.clear(); nav('/login') }
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
            <span>{auth.user?.display_name}</span>
            <button className="link" onClick={logout}>Đăng xuất</button>
          </div>
        </header>
        <main className="content"><Outlet /></main>
      </div>
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
