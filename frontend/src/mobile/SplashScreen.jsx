import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Wifi, RefreshCw, AlertTriangle, Trash } from 'lucide-react'

export default function SplashScreen() {
  const nav = useNavigate()

  useEffect(() => {
    // Tự động chuyển qua Onboarding sau 2.5 giây nếu người dùng không bấm
    const timer = setTimeout(() => {
      nav('/m/onboarding')
    }, 2800)
    return () => clearTimeout(timer)
  }, [nav])

  return (
    <div className="m-splash-container">
      {/* Nền hiệu ứng quả địa cầu mờ */}
      <div className="m-splash-globe-bg" />

      {/* Header Logo + Tiêu đề Smart Garbaging */}
      <div className="m-splash-header">
        <div className="m-splash-logo-box">
          <Trash size={42} color="#1e88e5" strokeWidth={2.2} />
          <Wifi size={22} color="#1e88e5" strokeWidth={2.4} style={{ marginTop: '-8px' }} />
        </div>
        <h1 className="m-splash-title">Smart Garbaging</h1>
      </div>

      {/* 4 Thùng rác phân loại màu theo nguyên mẫu */}
      <div className="m-splash-bins-group">
        <div className="m-splash-bins-row">
          {/* Thùng Xanh Dương: Tái chế */}
          <div className="m-splash-bin-item blue">
            <RefreshCw size={20} strokeWidth={2.2} style={{ marginBottom: '6px' }} />
            <span>TÁI CHẾ</span>
            <small style={{ fontSize: '8px', opacity: 0.85 }}>Recyclable</small>
          </div>

          {/* Thùng Vàng: Không tái chế */}
          <div className="m-splash-bin-item orange">
            <Trash size={20} strokeWidth={2.2} style={{ marginBottom: '6px' }} />
            <span>VÔ CƠ</span>
            <small style={{ fontSize: '8px', opacity: 0.85 }}>Other</small>
          </div>

          {/* Thùng Xanh Lá: Hữu cơ */}
          <div className="m-splash-bin-item green">
            <RefreshCw size={20} strokeWidth={2.2} style={{ marginBottom: '6px' }} />
            <span>HỮU CƠ</span>
            <small style={{ fontSize: '8px', opacity: 0.85 }}>Organic</small>
          </div>

          {/* Thùng Đỏ: Nguy hại */}
          <div className="m-splash-bin-item red">
            <AlertTriangle size={20} strokeWidth={2.2} style={{ marginBottom: '6px' }} />
            <span>NGUY HẠI</span>
            <small style={{ fontSize: '8px', opacity: 0.85 }}>Hazardous</small>
          </div>
        </div>

        <button className="m-splash-start-btn" onClick={() => nav('/m/onboarding')}>
          Bắt đầu ngay &rarr;
        </button>
      </div>
    </div>
  )
}
