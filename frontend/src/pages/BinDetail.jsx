import { useState } from 'react'
import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api, auth } from '../api'
import { binStatus, WASTE } from './Bins'
import { fmt, iso } from '../util'

const RANGES = { '24h': 24, '7d': 168 }

function Chart({ items }) {
  const pts = [...items].reverse() // API trả giảm dần, vẽ tăng dần
  if (pts.length < 2) return <p className="empty">Chưa có số đo trong khoảng này.</p>
  const W = 640, H = 200, P = 30
  const T = p => new Date(p.sampled_at).getTime(), t0 = T(pts[0]), t1 = T(pts[pts.length - 1])
  const x = t => P + (W - 2 * P) * ((t - t0) / (t1 - t0 || 1)), y = v => H - P - (H - 2 * P) * v / 100
  const segs = []; let cur = [] // ngắt đường khi fill_pct null, không nối qua chỗ mất số đo
  pts.forEach(p => { if (p.fill_pct == null) { if (cur.length) segs.push(cur); cur = [] } else cur.push(`${x(T(p))},${y(p.fill_pct)}`) })
  if (cur.length) segs.push(cur)
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="chart" role="img" aria-label="Biểu đồ mức đầy theo thời gian">
      {[0, 50, 100].map(v => <g key={v}><line x1={P} x2={W - P} y1={y(v)} y2={y(v)} stroke="#e3e8ef" /><text x="2" y={y(v) + 4} fontSize="11" fill="#6b7280">{v}%</text></g>)}
      <line x1={P} x2={W - P} y1={y(80)} y2={y(80)} stroke="#d32f2f" strokeDasharray="4 4" />
      {segs.map((s, i) => <polyline key={i} points={s.join(' ')} fill="none" stroke="#1976d2" strokeWidth="2" />)}
      <text x={P} y={H - 8} fontSize="11" fill="#6b7280">{fmt(pts[0].sampled_at)}</text>
      <text x={W - P} y={H - 8} fontSize="11" fill="#6b7280" textAnchor="end">{fmt(pts[pts.length - 1].sampled_at)}</text>
    </svg>
  )
}

// Một hộp thoại cho cả hai việc: đăng ký thiết bị mới (POST /devices) rồi gắn vào thùng (POST /bins/{id}/assignments)
function DeviceModal({ bin, onClose }) {
  const qc = useQueryClient()
  const [mode, setMode] = useState('existing')
  const [created, setCreated] = useState(false)
  const [f, setF] = useState({ id: '', hardware_model: '', firmware_version: '', gateways: '', serial_number: '', sensor_model: '', reason: '' })
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const save = useMutation({
    mutationFn: async () => {
      if (mode === 'new' && !created) {
        // Bước 1: Tạo thiết bị
        await api('POST', '/devices', {
          id: f.id, hardware_model: f.hardware_model, firmware_version: f.firmware_version,
          gateway_ids: f.gateways.split(',').map(s => s.trim()).filter(Boolean),
          sensors: [{ sensor_id: 'us-1', type: 'ultrasonic', model: f.sensor_model }],
          ...(f.serial_number ? { serial_number: f.serial_number } : {}),
        })
        // Bước 2: Nạp cấu hình hiệu chuẩn ban đầu (theo mục 3.16 đặc tả)
        await api('POST', `/devices/${f.id}/configs`, {
          config_rev: 1,
          empty_distance_mm: 1000,
          full_distance_mm: 200,
          sample_interval_s: 60,
          report_interval_s: 21600,
        })
        setCreated(true) // nếu bước gắn lỗi, bấm lại sẽ không đăng ký lần hai
      }
      // Bước 3: Gắn vào thùng
      return api('POST', `/bins/${bin.id}/assignments`, { device_id: f.id, reason: f.reason })
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['bin', bin.id] }); qc.invalidateQueries({ queryKey: ['bins'] }); onClose() },
  })
  return (
    <div className="overlay" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h3>Gắn thiết bị cho {bin.code}</h3>
        <div className="row">
          <label className="inl"><input type="radio" checked={mode === 'existing'} onChange={() => setMode('existing')} /> Thiết bị đã đăng ký</label>
          <label className="inl"><input type="radio" checked={mode === 'new'} onChange={() => setMode('new')} /> Đăng ký thiết bị mới</label>
        </div>
        <label>Mã thiết bị<input value={f.id} onChange={set('id')} placeholder="bin-001" disabled={created} /></label>
        {mode === 'new' && <>
          <div className="row">
            <label>Mẫu phần cứng<input value={f.hardware_model} onChange={set('hardware_model')} /></label>
            <label>Phiên bản firmware<input value={f.firmware_version} onChange={set('firmware_version')} /></label>
          </div>
          <div className="row">
            <label>Mẫu cảm biến siêu âm<input value={f.sensor_model} onChange={set('sensor_model')} /></label>
            <label>Số serial (không bắt buộc)<input value={f.serial_number} onChange={set('serial_number')} /></label>
          </div>
          <label>Gateway (ngăn cách bằng dấu phẩy)<input value={f.gateways} onChange={set('gateways')} /></label>
        </>}
        <label>Lý do gắn<input value={f.reason} onChange={set('reason')} placeholder="Lắp mới / thay thiết bị hỏng" /></label>
        {save.error && <p className="err">{save.error.status === 409 ? 'Trùng hoặc đang gắn thùng khác: ' : ''}{save.error.message}</p>}
        <div className="actions">
          <button className="btn red" onClick={onClose}>HỦY</button>
          <button className="btn blue" disabled={save.isPending || !f.id || !f.reason} onClick={() => save.mutate()}>XÁC NHẬN</button>
        </div>
      </div>
    </div>
  )
}

export default function BinDetail() {
  const { id } = useParams()
  const [range, setRange] = useState('24h')
  const [showDev, setShowDev] = useState(false)
  const isAdmin = auth.isAdmin
  const bin = useQuery({ queryKey: ['bin', id], queryFn: () => api('GET', `/bins/${id}`), refetchInterval: 30000 })
  const tele = useQuery({
    queryKey: ['tele', id, range], enabled: !!bin.data?.device, refetchInterval: 30000,
    queryFn: async () => {
      const to = new Date(), from = new Date(to - RANGES[range] * 3600e3)
      let allItems = []
      let cursor = null
      // Lặp lấy qua cursor nếu có nhiều hơn 100 bản tin (tối đa 5 trang / 500 bản tin)
      for (let i = 0; i < 5; i++) {
        const q = `from=${iso(from)}&to=${iso(to)}&limit=100${cursor ? `&cursor=${cursor}` : ''}`
        const res = await api('GET', `/bins/${id}/telemetry?${q}`)
        const list = res?.items || []
        allItems = [...allItems, ...list]
        if (!res?.next_cursor || list.length < 100) break
        cursor = res.next_cursor
      }
      return { items: allItems }
    },
  })
  if (bin.isLoading) return <p className="empty">Đang tải…</p>
  if (bin.error) return <p className="err">{bin.error.status === 404 ? 'Không tìm thấy thùng này.' : bin.error.message}</p>
  const b = bin.data, s = binStatus(b), st = b.state, items = tele.data?.items || []
  const bad = items.filter(i => i.quality !== 'ok').length
  return (
    <div className="detail">
      <section className="box">
        <h3>{b.name} <small>({b.code})</small></h3>
        <dl className="info">
          <dt>Địa chỉ</dt><dd>{b.address}</dd>
          <dt>Phường</dt><dd>{b.ward_code}</dd>
          <dt>Loại rác</dt><dd>{WASTE[b.waste_type] || b.waste_type}</dd>
          <dt>Dung tích</dt><dd>{b.capacity_l ?? '—'} lít</dd>
          <dt>Trạng thái</dt><dd><span className={`badge ${s.key}`}>{s.label}</span>{st?.fill_pct != null && s.key !== 'none' && ` ${Math.round(st.fill_pct)}%`}</dd>
          <dt>Đo lần cuối</dt><dd>{fmt(st?.sampled_at)}</dd>
          {st && st.latest_quality !== 'ok' && <><dt>Cảm biến</dt><dd className="err">⚠️ Bản tin mới nhất lỗi ({st.latest_quality}); số hiển thị là lần đo tốt gần nhất</dd></>}
          <dt>Cảnh báo mở</dt><dd>{b.open_alerts?.length ? b.open_alerts.length + ' (xác nhận ở chuông trên đầu trang)' : 'Không có'}</dd>
        </dl>
      </section>
      <section className="box">
        <h3>Thiết bị</h3>
        {b.device ? <p>Mã <b>{b.device.id}</b> · {b.device.enabled ? 'đang bật' : 'đã tắt'} · {b.device.lifecycle}</p> : <p className="empty">Thùng chưa có thiết bị.</p>}
        {isAdmin && <button className="btn blue" onClick={() => setShowDev(true)}>{b.device ? 'ĐỔI THIẾT BỊ' : 'GẮN THIẾT BỊ'}</button>}
      </section>
      <section className="box wide">
        <h3>Mức đầy theo thời gian
          <span className="tabs">{Object.keys(RANGES).map(r => <button key={r} className={r === range ? 'on' : ''} onClick={() => setRange(r)}>{r === '24h' ? '24 giờ' : '7 ngày'}</button>)}</span>
        </h3>
        {!b.device ? <p className="empty">Gắn thiết bị để có dữ liệu đo.</p> : tele.isLoading ? <p className="empty">Đang tải số đo…</p> : tele.error ? <p className="err">{tele.error.message}</p> : <>
          <Chart items={items} />
          <p className="hint">{items.length} bản tin gần nhất trong khoảng chọn{bad > 0 && `, ${bad} bản tin lỗi chất lượng (không có số đo, bị ngắt trên đường)`}. Đường đỏ nét đứt là mức 80%.</p>
        </>}
      </section>
      {showDev && <DeviceModal bin={b} onClose={() => setShowDev(false)} />}
    </div>
  )
}
