import { useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { api } from '../api'
import ImagePlaceholder from './ImagePlaceholder'

// Dữ liệu mẫu 10 ngày (D1 -> D10) theo đúng ảnh nguyên mẫu
const DAYS_DATA = [
  { day: 'D1', plastic: 5, paper: 4 },
  { day: 'D2', plastic: 0, paper: 1 },
  { day: 'D3', plastic: 2, paper: 2 },
  { day: 'D4', plastic: 3, paper: 3 },
  { day: 'D5', plastic: 4, paper: 4 },
  { day: 'D6', plastic: 10, paper: 9.5 },
  { day: 'D7', plastic: 12, paper: 12.5 },
  { day: 'D8', plastic: 10, paper: 10 },
  { day: 'D9', plastic: 19, paper: 18.5 },
  { day: 'D10', plastic: 10, paper: 5 },
]

// Component biểu đồ Combo: Cột Plastic + Đường Paper
function DaysComboChart({ data = DAYS_DATA }) {
  const W = 360, H = 210, padLeft = 32, padBottom = 30, padTop = 15, padRight = 15
  const chartW = W - padLeft - padRight
  const chartH = H - padTop - padBottom
  const maxY = 25

  const getY = (val) => padTop + chartH - (val / maxY) * chartH
  const getX = (index) => padLeft + (index + 0.5) * (chartW / data.length)

  // Tạo path đường cong spline mượt mà cho Paper
  const linePath = useMemo(() => {
    return data.reduce((acc, curr, i) => {
      const x = getX(i)
      const y = getY(curr.paper)
      if (i === 0) return `M ${x} ${y}`
      const prevX = getX(i - 1)
      const prevY = getY(data[i - 1].paper)
      const cx1 = prevX + (x - prevX) / 2
      const cx2 = prevX + (x - prevX) / 2
      return `${acc} C ${cx1} ${prevY}, ${cx2} ${y}, ${x} ${y}`
    }, '')
  }, [data])

  const yTicks = [0, 5, 10, 15, 20, 25]

  return (
    <div className="m-chart-wrapper">
      <svg viewBox={`0 0 ${W} ${H}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
        {/* Lưới ngang (Grid lines) */}
        {yTicks.map((val) => (
          <g key={val}>
            <line
              x1={padLeft}
              x2={W - padRight}
              y1={getY(val)}
              y2={getY(val)}
              stroke="#f1f5f9"
              strokeWidth="1.2"
            />
            <text
              x={padLeft - 6}
              y={getY(val) + 3}
              fontSize="10"
              fill="#94a3b8"
              textAnchor="end"
              fontFamily="sans-serif"
            >
              {val}
            </text>
          </g>
        ))}

        {/* Cột Bar: Plastic (Màu xanh ngọc) */}
        {data.map((d, i) => {
          const x = getX(i) - 7
          const y = getY(d.plastic)
          const barH = getY(0) - y
          return (
            <rect
              key={d.day}
              x={x}
              y={y}
              width={14}
              height={Math.max(0, barH)}
              fill="#26a69a"
              rx={2}
            />
          )
        })}

        {/* Đường Line cong: Paper (Màu cam) */}
        <path
          d={linePath}
          fill="none"
          stroke="#f57c00"
          strokeWidth="2.5"
          strokeLinecap="round"
        />

        {/* Nhãn ngày D1 -> D10 trên trục X */}
        {data.map((d, i) => (
          <text
            key={d.day}
            x={getX(i)}
            y={H - 10}
            fontSize="10"
            fill="#64748b"
            textAnchor="middle"
            fontFamily="sans-serif"
          >
            {d.day}
          </text>
        ))}
      </svg>

      {/* Chú thích Legend theo nguyên mẫu */}
      <div className="m-chart-legend">
        <div className="m-legend-note-title">Note</div>
        <div className="m-legend-items-row">
          <div className="m-legend-badge">
            <span className="m-badge-bar-icon" />
            <span>Plastic</span>
          </div>
          <div className="m-legend-badge">
            <span className="m-badge-line-icon" />
            <span>Paper</span>
          </div>
        </div>
      </div>
    </div>
  )
}

export default function MobileBinDetail() {
  const { id } = useParams()
  const nav = useNavigate()

  const { data: bin, isLoading } = useQuery({
    queryKey: ['bin', id],
    queryFn: () => api('GET', `/bins/${id}`),
  })

  // Định dạng ngày hôm nay (04/01/2023 như mẫu hoặc ngày thực tế)
  const todayStr = useMemo(() => {
    const d = new Date()
    const dd = String(d.getDate()).padStart(2, '0')
    const mm = String(d.getMonth() + 1).padStart(2, '0')
    const yyyy = d.getFullYear()
    return `${dd}/${mm}/${yyyy}`
  }, [])

  const fillPct = bin?.state?.fill_pct != null ? Math.round(bin.state.fill_pct) : 75
  const address = bin?.address || '12 Ngo Quyen street, Hoang Mai, HN'

  return (
    <div className="m-detail-container">
      {/* Header bar */}
      <div className="m-detail-header-bar">
        <button
          className="m-back-floating-btn"
          onClick={() => nav(-1)}
          aria-label="Quay lại"
          style={{ width: 38, height: 38, boxShadow: 'none', border: '1px solid #e2e8f0' }}
        >
          <ArrowLeft size={20} />
        </button>
        <div>
          <h2 className="m-detail-main-title">Adress</h2>
        </div>
      </div>

      <p className="m-detail-address">{address}</p>

      {/* Ảnh lớn điểm đặt thùng */}
      <div className="m-detail-hero-img">
        <ImagePlaceholder
          src="/images/bin-spot-large.jpg"
          label="Ảnh thực tế điểm đặt thùng (Street View)"
          iconType="map"
        />
      </div>

      {/* Hàng ngày & Mức % đỏ to */}
      <div className="m-detail-status-row">
        <div className="m-detail-date">Today: {todayStr}</div>
        <div className="m-detail-big-pct">{fillPct}%</div>
      </div>

      {/* Biểu đồ Days (D1 -> D10) */}
      <h3 className="m-analytics-title">Days</h3>
      <DaysComboChart />
    </div>
  )
}
