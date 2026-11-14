import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { MapContainer, TileLayer, Circle, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import { ArrowLeft, Search, ArrowRight, Truck } from 'lucide-react'
import { api } from '../api'
import ImagePlaceholder from './ImagePlaceholder'

// Fix icon default Leaflet khi đóng gói Vite
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

// Tọa độ trung tâm mặc định (Hoàng Mai, Hà Nội theo thiết kế)
const DEFAULT_CENTER = [20.985, 105.845]

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
const truckIcon = L.divIcon({
  className: 'custom-truck-pin',
  html: `
    <div style="
      background: #2e7d32;
      color: #fff;
      width: 36px;
      height: 36px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      border: 3px solid #ffffff;
      box-shadow: 0 4px 12px rgba(0,0,0,0.35);
      transform: translate(-50%, -50%);
    ">
      🚚
    </div>
  `,
  iconSize: [36, 36],
  iconAnchor: [18, 18],
})

// Component căn chỉnh bản đồ khi chọn thùng
function MapController({ center }) {
  const map = useMap()
  useEffect(() => {
    if (center) {
      map.setView(center, 15, { animate: true })
    }
  }, [center, map])
  return null
}

export default function MobileMap() {
  const nav = useNavigate()
  const [searchParams] = useSearchParams()
  const mode = searchParams.get('mode') || 'bins'

  // Lấy dữ liệu thùng rác từ API
  const { data, isLoading } = useQuery({
    queryKey: ['bins'],
    queryFn: () => api('GET', '/bins?status=active&limit=100'),
    refetchInterval: 30000,
  })

  const bins = data?.items || []

  // Vị trí người dùng / xe rác
  const [userPos, setUserPos] = useState(() => {
    const savedLat = localStorage.getItem('sw_lat')
    const savedLng = localStorage.getItem('sw_lng')
    return savedLat && savedLng ? [parseFloat(savedLat), parseFloat(savedLng)] : DEFAULT_CENTER
  })

  // Thùng được chọn để hiển thị Bottom Sheet
  const [selectedBin, setSelectedBin] = useState(null)

  useEffect(() => {
    if (bins.length > 0 && !selectedBin) {
      // Mặc định chọn thùng đầu tiên hoặc thùng có mức rác 60% như nguyên mẫu
      const target = bins.find((b) => Math.round(b.state?.fill_pct || 0) === 60) || bins[0]
      setSelectedBin(target)
    }
  }, [bins, selectedBin])

  const curPct = selectedBin?.state?.fill_pct != null ? Math.round(selectedBin.state.fill_pct) : 60

  return (
    <div className="m-map-screen-container">
      {/* Top Floating Bar */}
      <div className="m-map-top-bar">
        <button
          className="m-back-floating-btn"
          onClick={() => nav('/m/home')}
          aria-label="Quay lại"
        >
          <ArrowLeft size={22} />
        </button>

        <div className="m-map-search-pill">
          <Search size={16} color="#94a3b8" />
          <span>{mode === 'truck' ? 'Đang điều hướng xe gom rác' : 'Tìm thùng rác theo bán kính…'}</span>
        </div>
      </div>

      {/* Bản đồ Leaflet */}
      <div className="m-leaflet-map-wrapper">
        <MapContainer
          center={userPos}
          zoom={15}
          zoomControl={false}
          style={{ width: '100%', height: '100%' }}
        >
          <TileLayer
            attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
            url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
          />

          <MapController center={selectedBin ? [selectedBin.lat, selectedBin.lng] : userPos} />

          {/* Vòng tròn bán kính quét (Radius circle quanh tâm) */}
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

          {/* Ghim xe gom rác */}
          <Marker position={userPos} icon={truckIcon}>
            <Popup>
              <b>Xe thu gom rác số 01</b><br />
              Đang hoạt động trong bán kính phục vụ
            </Popup>
          </Marker>

          {/* Ghim các thùng rác */}
          {bins.map((bin) => {
            const isSelected = selectedBin?.id === bin.id
            const fillPct = bin.state?.fill_pct
            return (
              <Marker
                key={bin.id}
                position={[bin.lat, bin.lng]}
                icon={createBinIcon(fillPct, isSelected)}
                eventHandlers={{
                  click: () => setSelectedBin(bin),
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
      {selectedBin && (
        <div className="m-map-bottom-sheet">
          <div className="m-sheet-header">
            <div>
              <h3 className="m-sheet-title">Information</h3>
              <p className="m-sheet-address">
                {selectedBin.address || '12 Ngo Quyen street, Hoang Mai, HN'}
              </p>
            </div>
            <div className="m-sheet-pct">{curPct}%</div>
          </div>

          <div className="m-sheet-body">
            <div className="m-sheet-thumbnail">
              <ImagePlaceholder
                src="/images/bin-spot-thumb.jpg"
                label="Ảnh điểm đặt thùng"
                iconType="map"
              />
            </div>

            <div style={{ fontSize: 13, color: '#4b5563' }}>
              <div><b>Mã thùng:</b> {selectedBin.code}</div>
              <div style={{ color: '#6b7280', marginTop: 2 }}>
                Dung tích: {selectedBin.capacity_l || 240}L
              </div>
            </div>

            <button
              className="m-sheet-nav-btn"
              onClick={() => nav(`/m/bins/${selectedBin.id}`)}
              title="Xem chi tiết & biểu đồ phân tích"
              aria-label="Xem chi tiết"
            >
              <ArrowRight size={22} />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
