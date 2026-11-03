import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { MapContainer, TileLayer, CircleMarker, Popup, useMapEvents } from 'react-leaflet'
import { Link } from 'react-router-dom'
import { api, auth } from '../api'

const CENTER = [21.005, 105.8442] // [lat, lng] cho Leaflet
export const WASTE = { general: 'Rác thường', organic: 'Hữu cơ', recyclable: 'Tái chế', hazardous: 'Nguy hại', other: 'Khác' }

// Mã màu cho từng trạng thái trên bản đồ
export const STATUS_COLORS = {
  full: { border: '#b71c1c', fill: '#e53935' },  // Đỏ (≥80%)
  mid: { border: '#e65100', fill: '#ffb300' },   // Vàng cam (20% - 79%)
  empty: { border: '#1b5e20', fill: '#43a047' }, // Xanh lá (<20%)
  none: { border: '#424242', fill: '#9e9e9e' },  // Xám (chưa có số đo / mất tín hiệu)
}

// Ngưỡng chỉ để hiển thị; "Đầy" ưu tiên cờ alarm_active do cảm biến báo
export function binStatus(b) {
  const s = b.state
  if (!s || s.fill_pct == null || !s.fresh) return { key: 'none', label: 'Chưa có dữ liệu' }
  if (s.alarm_active || s.fill_pct >= 80) return { key: 'full', label: 'Đầy' }
  if (s.fill_pct < 20) return { key: 'empty', label: 'Rỗng' }
  return { key: 'mid', label: 'Trung bình' }
}

function Picker({ pos, onPick }) {
  useMapEvents({ click: e => onPick([e.latlng.lat, e.latlng.lng]) })
  return <CircleMarker center={pos} radius={9} pathOptions={{ color: '#c62828', fillColor: '#e53935', fillOpacity: 0.9 }} />
}

function BinModal({ bin, onClose }) {
  const qc = useQueryClient()
  const [f, setF] = useState({
    code: bin?.code || '', name: bin?.name || '', capacity_l: bin?.capacity_l ?? 240,
    address: bin?.address || '', ward_code: bin?.ward_code || 'BK', waste_type: bin?.waste_type || 'general',
  })
  const [pos, setPos] = useState(bin ? [bin.lat, bin.lng] : CENTER)
  const set = k => e => setF({ ...f, [k]: e.target.value })
  const save = useMutation({
    mutationFn: () => {
      const body = { ...f, capacity_l: Number(f.capacity_l), location: { type: 'Point', coordinates: [pos[1], pos[0]] } } // GeoJSON: [lng, lat]
      if (bin) { const { code, ...rest } = body; return api('PATCH', `/bins/${bin.id}`, rest) } // không sửa code
      return api('POST', '/bins', body)
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['bins'] }); onClose() },
  })
  return (
    <div className="overlay" onMouseDown={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h3>{bin ? 'Sửa thùng rác' : 'Tạo thùng rác'}</h3>
        <label>Mã thùng<input value={f.code} onChange={set('code')} disabled={!!bin} placeholder="WB-011" /></label>
        <label>Tên thùng rác<input value={f.name} onChange={set('name')} /></label>
        <div className="row">
          <label>Dung tích (lít)<input type="number" min="0" value={f.capacity_l} onChange={set('capacity_l')} /></label>
          <label>Loại rác<select value={f.waste_type} onChange={set('waste_type')}>
            {Object.entries(WASTE).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
          <label>Mã phường<input value={f.ward_code} onChange={set('ward_code')} /></label>
        </div>
        <label>Địa chỉ<input value={f.address} onChange={set('address')} /></label>
        <p className="hint">Bấm lên bản đồ để chọn vị trí ({pos[0].toFixed(5)}, {pos[1].toFixed(5)})</p>
        <MapContainer center={pos} zoom={16} className="map">
          <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
          <Picker pos={pos} onPick={setPos} />
        </MapContainer>
        {save.error && <p className="err">{save.error.status === 409 ? 'Mã thùng đã tồn tại.' : save.error.message}</p>}
        <div className="actions">
          <button className="btn red" onClick={onClose}>HỦY</button>
          <button className="btn blue" disabled={save.isPending || !f.code || !f.name || !f.address} onClick={() => save.mutate()}>XÁC NHẬN</button>
        </div>
      </div>
    </div>
  )
}

export default function Bins() {
  const qc = useQueryClient()
  const isAdmin = auth.isAdmin
  const { data, isLoading, error } = useQuery({
    queryKey: ['bins'], queryFn: () => api('GET', '/bins?status=active&limit=100'), refetchInterval: 30000,
  })
  const [view, setView] = useState('table') // 'table' | 'map'
  const [focusBin, setFocusBin] = useState(null)
  const [page, setPage] = useState(0)
  const [modal, setModal] = useState(null) // null | {} (tạo mới) | bin (sửa)
  const [sel, setSel] = useState([])
  // API không cho xóa thùng: "Xóa" = chuyển status sang retired
  const retire = useMutation({ mutationFn: id => api('PATCH', `/bins/${id}`, { status: 'retired' }), onSuccess: () => qc.invalidateQueries({ queryKey: ['bins'] }) })

  const items = data?.items || []
  const SIZE = 8
  const rows = items.slice(page * SIZE, page * SIZE + SIZE)
  const toggle = id => setSel(s => s.includes(id) ? s.filter(x => x !== id) : [...s, id])
  const onRetire = b => window.confirm(`Ngừng sử dụng thùng ${b.code}?`) && retire.mutate(b.id)

  if (isLoading) return <p className="empty">Đang tải danh sách thùng…</p>
  if (error) return <p className="err">Không tải được danh sách: {error.message}</p>

  return (
    <>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px', flexWrap: 'wrap', gap: '10px' }}>
        <div className="tabs">
          <button className={view === 'table' ? 'on' : ''} onClick={() => setView('table')}>📋 Dạng bảng</button>
          <button className={view === 'map' ? 'on' : ''} onClick={() => { setView('map'); setFocusBin(null); }}>🗺️ Dạng bản đồ</button>
        </div>
        {view === 'map' && (
          <div style={{ display: 'flex', gap: '14px', fontSize: '12px', alignItems: 'center', color: '#6b7280', flexWrap: 'wrap' }}>
            <span><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#e53935', marginRight: 4, verticalAlign: 'middle' }}></i>Đầy (≥80%)</span>
            <span><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#ffb300', marginRight: 4, verticalAlign: 'middle' }}></i>Trung bình (20-79%)</span>
            <span><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#43a047', marginRight: 4, verticalAlign: 'middle' }}></i>Rỗng (&lt;20%)</span>
            <span><i style={{ display: 'inline-block', width: 10, height: 10, borderRadius: '50%', background: '#9e9e9e', marginRight: 4, verticalAlign: 'middle' }}></i>Chưa có số đo</span>
          </div>
        )}
      </div>

      {view === 'table' ? (
        <>
          <table className="tbl">
            <thead><tr>
              <th><input type="checkbox" checked={rows.length > 0 && rows.every(r => sel.includes(r.id))} onChange={e => setSel(e.target.checked ? rows.map(r => r.id) : [])} /></th>
              <th>ID</th><th>Tên</th><th>Địa chỉ</th><th>Trạng thái</th><th>Thao tác</th>
            </tr></thead>
            <tbody>
              {rows.map(b => { const s = binStatus(b); return (
                <tr key={b.id}>
                  <td><input type="checkbox" checked={sel.includes(b.id)} onChange={() => toggle(b.id)} /></td>
                  <td><Link to={`/bins/${b.id}`}>{b.code}</Link></td><td>{b.name}</td><td>{b.address}</td>
                  <td><span className={`badge ${s.key}`}>{s.label}</span>{b.state?.fill_pct != null && s.key !== 'none' && ` ${Math.round(b.state.fill_pct)}%`}
                    {b.state && b.state.latest_quality !== 'ok' && <span title="Cảm biến báo lỗi"> ⚠️</span>}</td>
                  <td>
                    <button className="mini" title="Xem trên bản đồ" onClick={() => { setFocusBin(b); setView('map'); }}>📍</button>
                    {isAdmin && <>
                      <button className="mini" onClick={() => setModal(b)}>Sửa</button>
                      <button className="mini del" title="Ngừng sử dụng" onClick={() => onRetire(b)}>🗑</button>
                    </>}
                  </td>
                </tr>) })}
              {rows.length === 0 && <tr><td colSpan={6} className="empty">{isAdmin ? 'Chưa có thùng nào. Bấm THÊM THÙNG RÁC để tạo thùng đầu tiên.' : 'Chưa có thùng nào.'}</td></tr>}
            </tbody>
          </table>
          <div className="foot">
            {isAdmin ? (
              <button className="btn blue" onClick={() => setModal({})}>THÊM THÙNG RÁC</button>
            ) : (
              <span style={{ marginRight: 'auto' }} />
            )}
            <span>{items.length ? `${page * SIZE + 1}–${Math.min((page + 1) * SIZE, items.length)} / ${items.length}` : '0'}</span>
            <button className="link" disabled={page === 0} onClick={() => setPage(page - 1)}>‹</button>
            <button className="link" disabled={(page + 1) * SIZE >= items.length} onClick={() => setPage(page + 1)}>›</button>
          </div>
        </>
      ) : (
        <div style={{ background: '#fff', borderRadius: '8px', border: '1px solid var(--line)', padding: '12px', boxShadow: '0 1px 3px rgba(0,0,0,0.05)' }}>
          <MapContainer
            center={focusBin ? [focusBin.lat, focusBin.lng] : CENTER}
            zoom={focusBin ? 17 : 15}
            style={{ height: '520px', width: '100%', borderRadius: '6px' }}
          >
            <TileLayer url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="© OpenStreetMap" />
            {items.map(b => {
              const s = binStatus(b)
              const c = STATUS_COLORS[s.key] || STATUS_COLORS.none
              const isFocus = focusBin?.id === b.id
              return (
                <CircleMarker
                  key={b.id}
                  center={[b.lat, b.lng]}
                  radius={isFocus ? 13 : 9}
                  pathOptions={{
                    color: c.border,
                    fillColor: c.fill,
                    fillOpacity: 0.9,
                    weight: isFocus ? 3 : 2,
                  }}
                >
                  <Popup>
                    <div style={{ minWidth: '160px', lineHeight: 1.5 }}>
                      <b style={{ color: 'var(--blue)', fontSize: '14px' }}>{b.name}</b> <small>({b.code})</small><br />
                      <span style={{ fontSize: '12px', color: '#6b7280' }}>{b.address}</span>
                      <div style={{ margin: '6px 0' }}>
                        <span className={`badge ${s.key}`}>{s.label}</span>
                        {b.state?.fill_pct != null && s.key !== 'none' && ` ${Math.round(b.state.fill_pct)}%`}
                      </div>
                      <Link to={`/bins/${b.id}`} style={{ color: 'var(--blue)', fontWeight: 500, fontSize: '13px' }}>
                        Xem chi tiết thùng ›
                      </Link>
                    </div>
                  </Popup>
                </CircleMarker>
              )
            })}
          </MapContainer>
          <div style={{ marginTop: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: '#6b7280' }}>
              Hiển thị <b>{items.length}</b> thùng rác trên bản đồ {focusBin && `(Đang chọn ${focusBin.code})`}
            </span>
            {isAdmin && <button className="btn blue" onClick={() => setModal({})}>THÊM THÙNG RÁC</button>}
          </div>
        </div>
      )}
      {modal && <BinModal key={modal.id || 'new'} bin={modal.id ? modal : null} onClose={() => setModal(null)} />}
    </>
  )
}
