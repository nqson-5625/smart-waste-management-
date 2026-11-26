import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search, User, LogOut, Truck, Trash2, AlertTriangle } from 'lucide-react'
import { auth } from '../api'
import ImagePlaceholder from './ImagePlaceholder'

export default function MobileHome() {
  const nav = useNavigate()
  const [searchTerm, setSearchTerm] = useState('')
  const user = auth.user || { display_name: 'Nguyễn Văn Gom', phone: '09223828', roles: ['collector'] }
  const isAdmin = auth.isAdmin

  const handleLogout = () => {
    auth.clear()
    nav('/m/login', { replace: true })
  }

  return (
    <div className="m-home-container">
      {/* Cảnh báo nếu đang dùng tài khoản Admin trên Mobile */}
      {isAdmin && (
        <div style={{ background: '#fef2f2', borderBottom: '1px solid #fecaca', padding: '10px 16px', fontSize: '12px', color: '#991b1b', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <AlertTriangle size={16} />
            <span>Tài khoản Admin không phù hợp cho Mobile.</span>
          </div>
          <button
            onClick={handleLogout}
            style={{ background: '#dc2626', color: '#fff', border: 'none', borderRadius: 4, padding: '4px 8px', fontSize: '11px', fontWeight: 700, cursor: 'pointer' }}
          >
            Đổi sang Người thu gom
          </button>
        </div>
      )}

      {/* Header cong màu xanh lá theo nguyên mẫu */}
      <div className="m-home-curved-header">
        <h1 className="m-home-app-title">Smart Garbaging</h1>

        {/* Thông tin User */}
        <div className="m-home-user-profile">
          <div className="m-home-avatar">
            <User size={30} strokeWidth={2.2} />
          </div>
          <div className="m-home-user-info">
            <div className="m-home-username">{user.display_name || 'Nguyễn Văn Gom'}</div>
            <div className="m-home-userphone">{user.phone || '09223828'}</div>
          </div>
          <button
            className="m-home-action-btn"
            onClick={handleLogout}
            title="Đăng xuất"
            aria-label="Đăng xuất"
          >
            <LogOut size={20} />
          </button>
        </div>

        {/* Search bar */}
        <div className="m-home-search-bar">
          <input
            type="text"
            placeholder="Tìm kiếm địa điểm, mã thùng hoặc tuyến đường…"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <Search size={18} color="#9ca3af" />
        </div>
      </div>

      {/* Thân trang: Let's collect garbage */}
      <div className="m-home-body">
        <h2 className="m-section-heading">Let's collect garbage</h2>

        <div className="m-cards-grid">
          {/* Card 1: Start with garbage truck */}
          <div
            className="m-action-card"
            onClick={() => nav('/m/map?mode=truck')}
            role="button"
            tabIndex={0}
          >
            <div className="m-card-img-wrap">
              <ImagePlaceholder
                src="/images/truck-route.png"
                label="Lộ trình xe thu gom"
                iconType="truck"
              />
            </div>
            <div className="m-card-title-footer">
              Start with garbage truck
            </div>
          </div>

          {/* Card 2: Smart bin */}
          <div
            className="m-action-card"
            onClick={() => nav('/m/map?mode=bins')}
            role="button"
            tabIndex={0}
          >
            <div className="m-card-img-wrap">
              <ImagePlaceholder
                src="/images/smart-bin-preview.png"
                label="Thùng rác thông minh"
                iconType="bin"
              />
            </div>
            <div className="m-card-title-footer">
              Smart bin
            </div>
          </div>
        </div>

        {/* Thông tin nhanh tiện ích */}
        <div style={{ marginTop: 28, background: '#ffffff', borderRadius: 18, padding: 16, border: '1px solid #f1f5f9', boxShadow: '0 4px 12px rgba(0,0,0,0.03)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
            <span style={{ width: 10, height: 10, borderRadius: '50%', background: '#22c55e' }} />
            <b style={{ fontSize: 13, color: '#334155' }}>Trạng thái mạng lưới IoT:</b>
          </div>
          <p style={{ margin: 0, fontSize: 13, color: '#64748b', lineHeight: 1.5 }}>
            Hệ thống đang giám sát và đồng bộ tự động 10 điểm thu gom rác trên bản đồ theo thời gian thực.
          </p>
        </div>
      </div>
    </div>
  )
}
