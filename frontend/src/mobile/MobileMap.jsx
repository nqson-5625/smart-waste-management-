import { useState, useEffect, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, Circle, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import L from 'leaflet'
import { ArrowLeft, ArrowRight, Truck, Trash2, Navigation } from 'lucide-react'
import { api, auth, fetchAllBins } from '../api'
import ImagePlaceholder from './ImagePlaceholder'

// Fix icon default Leaflet khi đóng gói Vite
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

// Tọa độ trung tâm mặc định (Hoàng Mai, Hà Nội)
const DEFAULT_CENTER = [20.985, 105.845]

// Hàm kiểm tra và chuẩn hóa tọa độ tránh NaN crash Leaflet
const parseCoord = (val, fallback) => {
  const num = parseFloat(val)
  return !isNaN(num) && num > 0 ? num : fallback
}

// Custom Icon cho Ghim thùng rác hiển thị số %
const createBinIcon = (fillPct, isSelected) => {
  const pct = fillPct != null ? Math.round(fillPct) : 0
  const color = pct >= 80 ? '#d32f2f' : pct >= 20 ? '#f57c00' : '#388e3c'
  return L.divIcon({
    className: 'custom-bin-pin',
    html: `
      <div style="
        background: ${color};
        color: #fff;
        padding: 3px 6px;
        border-radius: 12px;
        font-size: 11px;
        font-weight: 800;
        border: ${isSelected ? '3px solid #111827' : '2px solid #ffffff'};
        box-shadow: 0 4px 10px rgba(0,0,0,0.35);
        white-space: nowrap;
        display: flex;
        align-items: center;
        gap: 3px;
        transform: translate(-50%, -50%);
      ">
        <span>📍</span>
        <span>${pct}%</span>
      </div>
    `,
    iconSize: [40, 24],
    iconAnchor: [20, 12],
  })
}

// Custom Icon cho Xe gom rác
const createTruckIcon = (isSelected) => L.divIcon({
  className: 'custom-truck-pin',
  html: `
    <div style="
      background: #2e7d32;
      color: #fff;
      width: 42px;
      height: 42px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      border: ${isSelected ? '3px solid #facc15' : '3px solid #ffffff'};
      box-shadow: 0 6px 14px rgba(46,125,50,0.45);
      font-size: 20px;
      transform: translate(-50%, -50%);
    ">
      🚚
    </div>
  `,
  iconSize: [42, 42],
  iconAnchor: [21, 21],
})

// Component giải quyết triệt để lỗi tính toán kích thước Leaflet
function MapFixer({ center }) {
  const map = useMap()
  useEffect(() => {
    const fix = () => {
      map.invalidateSize()
      if (center && !isNaN(center[0]) && !isNaN(center[1])) {
        map.setView(center, map.getZoom() || 15)
      }
    }
    fix()
    const t1 = setTimeout(fix, 100)
    const t2 = setTimeout(fix, 300)
    const t3 = setTimeout(fix, 800)
    return () => {
      clearTimeout(t1)
      clearTimeout(t2)
      clearTimeout(t3)
    }
  }, [map, center])
  return null
}

export default function MobileMap() {
  const nav = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const mode = searchParams.get('mode') || 'truck' // 'truck' | 'bins'

  // Lấy dữ liệu thùng rác từ API (lặp theo next_cursor lấy đủ toàn bộ)
  const { data } = useQuery({
    queryKey: ['bins'],
    queryFn: () => fetchAllBins('status=active'),
    refetchInterval: 30000,
  })

  const bins = data?.items || []

  // Vị trí người dùng / xe gom rác an toàn
  const userPos = useMemo(() => {
    try {
      const lat = parseCoord(localStorage.getItem('sw_lat'), DEFAULT_CENTER[0])
      const lng = parseCoord(localStorage.getItem('sw_lng'), DEFAULT_CENTER[1])
      return [lat, lng]
    } catch {
      return DEFAULT_CENTER
    }
  }, [])

  // Thông tin đối tượng đang được chọn (Thùng rác HOẶC Xe gom rác)
  const [selectedEntity, setSelectedEntity] = useState(() => {
    return mode === 'truck'
      ? { type: 'truck', name: 'Xe thu gom số 01', plate: '29H-882.14', driver: auth.user?.display_name || 'Nguyễn Văn Gom' }
      : null
  })

  // Khi thay đổi mode từ URL hoặc toggle
  useEffect(() => {
    if (mode === 'truck') {
      setSelectedEntity({
        type: 'truck',
        name: 'Xe thu gom số 01',
        plate: '29H-882.14',
        driver: auth.user?.display_name || 'Nguyễn Văn Gom',
      })
    } else if (bins.length > 0) {
      const defaultBin = bins.find((b) => Math.round(b.state?.fill_pct || 0) === 60) || bins[0]
      setSelectedEntity({ type: 'bin', data: defaultBin })
    }
  }, [mode, bins])

  // Lộ trình thu gom: Nối từ xe rác qua các thùng cần gom (fill_pct >= 50% hoặc alarm)
  const routePoints = useMemo(() => {
    const priorityBins = bins
      .filter((b) => (b.state?.fill_pct || 0) >= 40 || b.state?.alarm_active)
      .slice(0, 5)
    return [userPos, ...priorityBins.map((b) => [b.lat, b.lng])]
  }, [bins, userPos])

  // Chuyển chế độ
  const handleToggleMode = (newMode) => {
    setSearchParams({ mode: newMode })
    if (newMode === 'truck') {
      setSelectedEntity({
        type: 'truck',
        name: 'Xe thu gom số 01',
        plate: '29H-882.14',
        driver: auth.user?.display_name || 'Nguyễn Văn Gom',
      })
    } else if (bins.length > 0) {
      setSelectedEntity({ type: 'bin', data: bins[0] })
    }
  }

  const centerPos = useMemo(() => {
    if (selectedEntity?.type === 'bin' && selectedEntity.data) {
      return [selectedEntity.data.lat, selectedEntity.data.lng]
    }
    return userPos
  }, [selectedEntity, userPos])

  return (
    <div className="m-map-screen-container">
      {/* Top Floating Controls */}
      <div className="m-map-top-bar">
        <button
          className="m-back-floating-btn"
          onClick={() => nav('/m/home')}
          aria-label="Quay lại"
        >
          <ArrowLeft size={22} />
        </button>

        {/* Thanh chuyển chế độ Xe thu rác / Thùng rác */}
        <div className="m-map-mode-toggle">
          <button
            className={`m-mode-btn ${mode === 'truck' ? 'active' : ''}`}
            onClick={() => handleToggleMode('truck')}
          >
            <Truck size={16} /> Xe thu gom
          </button>
          <button
            className={`m-mode-btn ${mode === 'bins' ? 'active' : ''}`}
            onClick={() => handleToggleMode('bins')}
          >
            <Trash2 size={16} /> Thùng rác
          </button>
        </div>
      </div>

      {/* Bản đồ tương tác Leaflet */}
      <div className="m-leaflet-map-wrapper">
        <MapContainer
          center={userPos}
          zoom={15}
          zoomControl={false}
          style={{ width: '100%', height: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
            url="https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png"
          />

          <MapFixer center={centerPos} />

          {/* Vòng tròn bán kính phục vụ của xe gom rác */}
          <Circle
            center={userPos}
            radius={650}
            pathOptions={{
              color: '#0284c7',
              weight: 1.5,
              fillColor: '#38bdf8',
              fillOpacity: 0.15,
            }}
          />

          {/* Đường lộ trình xe gom rác chạy qua các thùng */}
          {mode === 'truck' && routePoints.length > 1 && (
            <Polyline
              positions={routePoints}
              pathOptions={{
                color: '#2e7d32',
                weight: 4,
                dashArray: '8, 8',
                opacity: 0.85,
              }}
            />
          )}

          {/* Ghim Xe gom rác (Nhấn vào sẽ hiển thị thông tin xe) */}
          <Marker
            position={userPos}
            icon={createTruckIcon(selectedEntity?.type === 'truck')}
            eventHandlers={{
              click: () => {
                setSelectedEntity({
                  type: 'truck',
                  name: 'Xe thu gom số 01',
                  plate: '29H-882.14',
                  driver: auth.user?.display_name || 'Nguyễn Văn Gom',
                })
              },
            }}
          >
            <Popup>
              <b>🚚 Xe thu gom rác số 01</b><br />
              Tài xế: {auth.user?.display_name || 'Nguyễn Văn Gom'}<br />
              Trạng thái: Đang trên lộ trình
            </Popup>
          </Marker>

          {/* Ghim các thùng rác */}
          {bins.map((bin) => {
            const isSelected = selectedEntity?.type === 'bin' && selectedEntity.data?.id === bin.id
            const fillPct = bin.state?.fill_pct
            return (
              <Marker
                key={bin.id}
                position={[bin.lat, bin.lng]}
                icon={createBinIcon(fillPct, isSelected)}
                eventHandlers={{
                  click: () => {
                    setSelectedEntity({ type: 'bin', data: bin })
                  },
                }}
              >
                <Popup>
                  <b>{bin.name} ({bin.code})</b><br />
                  {bin.address}<br />
                  <b>Mức rác: {fillPct != null ? `${Math.round(fillPct)}%` : 'Chưa đo'}</b>
                </Popup>
              </Marker>
            )
          })}
        </MapContainer>
      </div>

      {/* Bottom Sheet Information Card */}
      {selectedEntity?.type === 'truck' ? (
        /* Thẻ thông tin khi CHỌN XE THU RÁC */
        <div className="m-map-bottom-sheet">
          <div className="m-sheet-header">
            <div>
              <h3 className="m-sheet-title">Information</h3>
              <p className="m-sheet-address">
                Tuyến số 01 · Khu vực Quận Hoàng Mai, Hà Nội
              </p>
            </div>
            <div className="m-sheet-pct" style={{ color: '#2e7d32', fontSize: 18 }}>
              Đang chạy
            </div>
          </div>

          <div className="m-sheet-body">
            <div className="m-sheet-thumbnail">
              <ImagePlaceholder
                src={selectedEntity.image_url || selectedEntity.photo_url || '/images/truck-route.png'}
                fallbackSrc="/images/truck-route.png"
                label="Xe gom rác"
                iconType="truck"
              />
            </div>

            <div style={{ fontSize: 13, color: '#4b5563', flex: 1 }}>
              <div><b>{selectedEntity.name}</b> (BKS: {selectedEntity.plate})</div>
              <div style={{ color: '#6b7280', marginTop: 2 }}>
                Người gom: <b>{selectedEntity.driver}</b>
              </div>
              <div style={{ color: '#2e7d32', fontWeight: 600, marginTop: 2 }}>
                Lộ trình: {routePoints.length - 1} điểm cần gom rác
              </div>
            </div>

            <button
              className="m-sheet-nav-btn"
              onClick={() => {
                // Điều hướng tới thùng rác đầu tiên trên lộ trình
                if (bins.length > 0) {
                  const targetBin = bins.find((b) => (b.state?.fill_pct || 0) >= 50) || bins[0]
                  nav(`/m/bins/${targetBin.id}`)
                }
              }}
              title="Xem thùng rác trên tuyến"
              aria-label="Xem thùng rác trên tuyến"
            >
              <Navigation size={22} color="#2e7d32" />
            </button>
          </div>
        </div>
      ) : selectedEntity?.type === 'bin' && selectedEntity.data ? (
        /* Thẻ thông tin khi CHỌN THÙNG RÁC */
        <div className="m-map-bottom-sheet">
          <div className="m-sheet-header">
            <div>
              <h3 className="m-sheet-title">Information</h3>
              <p className="m-sheet-address">
                {selectedEntity.data.address || '12 Ngo Quyen street, Hoang Mai, HN'}
              </p>
            </div>
            <div className="m-sheet-pct">
              {selectedEntity.data.state?.fill_pct != null
                ? Math.round(selectedEntity.data.state.fill_pct)
                : 60}%
            </div>
          </div>

          <div className="m-sheet-body">
            <div className="m-sheet-thumbnail">
              <ImagePlaceholder
                src={selectedEntity.data.image_url || selectedEntity.data.photo_url || '/images/bin-spot-thumb.jpg'}
                fallbackSrc="/images/bin-spot-thumb.jpg"
                label="Ảnh điểm đặt thùng"
                iconType="map"
              />
            </div>

            <div style={{ fontSize: 13, color: '#4b5563', flex: 1 }}>
              <div><b>Mã thùng:</b> {selectedEntity.data.code}</div>
              <div style={{ color: '#6b7280', marginTop: 2 }}>
                Dung tích: {selectedEntity.data.capacity_l || 240}L
              </div>
            </div>

            <button
              className="m-sheet-nav-btn"
              onClick={() => nav(`/m/bins/${selectedEntity.data.id}`)}
              title="Xem chi tiết & biểu đồ phân tích"
              aria-label="Xem chi tiết"
            >
              <ArrowRight size={22} />
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
