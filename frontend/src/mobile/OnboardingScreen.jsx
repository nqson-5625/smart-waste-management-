import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ArrowRight, MapPin, Wifi, Trash2, Truck } from 'lucide-react'

export default function OnboardingScreen() {
  const nav = useNavigate()
  const [slide, setSlide] = useState(1) // 1 hoặc 2
  const [showPermDialog, setShowPermDialog] = useState(false)

  const handleNext = () => {
    if (slide === 1) {
      // Khi ở slide 1, bấm Next sẽ mở hộp thoại xin quyền GPS
      setShowPermDialog(true)
    } else {
      // Đã xong slide 2 -> Chuyển đến màn hình đăng nhập
      localStorage.setItem('sw_onboarded', 'true')
      nav('/m/login')
    }
  }

  const handlePermission = (type) => {
    if (type === 'allow') {
      if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(
          (pos) => {
            localStorage.setItem('sw_lat', pos.coords.latitude)
            localStorage.setItem('sw_lng', pos.coords.longitude)
          },
          () => {},
          { timeout: 5000 }
        )
      }
    }
    setShowPermDialog(false)
    setSlide(2) // Chuyển sang slide 2
  }

  const handleSkip = () => {
    localStorage.setItem('sw_onboarded', 'true')
    nav('/m/login')
  }

  return (
    <div className="m-onboarding-container">
      {/* Header nút Bỏ qua */}
      <div className="m-onboarding-top">
        <button className="m-skip-btn" onClick={handleSkip}>
          Bỏ qua
        </button>
      </div>

      {/* Nội dung Slide */}
      {slide === 1 ? (
        <div className="m-onboarding-content">
          <div className="m-onboarding-illustration">
            {/* Minh họa Thùng rác thông minh */}
            <div style={{
              width: 130,
              height: 160,
              background: '#43a047',
              borderRadius: '24px 24px 16px 16px',
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              boxShadow: '0 16px 30px rgba(67, 160, 71, 0.35)',
            }}>
              {/* Sóng Wi-Fi phía trên thùng */}
              <div style={{ position: 'absolute', top: -32, right: 10, color: '#334155' }}>
                <Wifi size={40} strokeWidth={2.5} />
              </div>
              <Trash2 size={54} color="#ffffff" strokeWidth={1.8} />
              <div style={{ marginTop: 8, background: '#ffffff', borderRadius: 8, padding: '3px 8px', fontSize: 11, fontWeight: 800, color: '#2e7d32' }}>
                IOT SMART
              </div>
            </div>
          </div>

          <h2 className="m-onboarding-title">Smart Bin</h2>
          <p className="m-onboarding-desc">
            The system of smart trash cans is connected to locate and notify information everywhere
          </p>
        </div>
      ) : (
        <div className="m-onboarding-content">
          <div className="m-onboarding-illustration">
            {/* Minh họa Xe gom rác */}
            <div style={{
              width: 170,
              height: 140,
              background: '#ffffff',
              borderRadius: 24,
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              position: 'relative',
              boxShadow: '0 16px 30px rgba(0,0,0,0.08)',
              border: '2px solid #e2e8f0',
            }}>
              <Truck size={68} color="#2e7d32" strokeWidth={1.8} />
              <div style={{ marginTop: 6, fontSize: 11, fontWeight: 700, color: '#374151' }}>
                Tuyến thu gom tối ưu
              </div>
            </div>
          </div>

          <h2 className="m-onboarding-title">Support garbage truck</h2>
          <p className="m-onboarding-desc">
            Provide location of garbage trucks and dump locations.
          </p>
        </div>
      )}

      {/* Điều khiển phía dưới: Dots + Next button */}
      <div className="m-onboarding-bottom">
        <div className="m-dots-indicator">
          <span className={`m-dot ${slide === 1 ? 'active' : ''}`} />
          <span className={`m-dot ${slide === 2 ? 'active' : ''}`} />
          <span className="m-dot" />
        </div>

        <button className="m-circle-next-btn" onClick={handleNext} aria-label="Tiếp tục">
          <ArrowRight size={26} strokeWidth={2.5} />
        </button>
      </div>

      {/* Modal Popup Xin quyền GPS (Màn hình 3 trong nguyên mẫu) */}
      {showPermDialog && (
        <div className="m-permission-overlay">
          <div className="m-permission-card">
            <MapPin className="m-permission-icon" strokeWidth={2} />
            <h3 className="m-permission-title">
              Cho phép <b>smartgarbaging</b> truy cập vào vị trí của thiết bị này?
            </h3>
            <div className="m-permission-actions">
              <button className="m-perm-btn" onClick={() => handlePermission('allow')}>
                CHỈ CHO PHÉP KHI DÙNG ỨNG DỤNG
              </button>
              <button className="m-perm-btn secondary" onClick={() => handlePermission('deny')}>
                TỪ CHỐI
              </button>
              <button className="m-perm-btn secondary" onClick={() => handlePermission('never')}>
                TỪ CHỐI VÀ KHÔNG HỎI LẠI
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
