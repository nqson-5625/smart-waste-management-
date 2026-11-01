const BASE = import.meta.env.VITE_API_BASE || '/api/v1'
const MOCK = import.meta.env.VITE_USE_MOCK === 'true'

export const auth = {
  get token() { return localStorage.getItem('sw_token') },
  get user() { try { return JSON.parse(localStorage.getItem('sw_user')) } catch { return null } },
  get isAdmin() { return this.user?.roles?.includes('admin') ?? false },
  get isDispatcher() { return this.user?.roles?.includes('dispatcher') ?? false },
  get isCollector() { return this.user?.roles?.includes('collector') ?? false },
  set(t, u) { localStorage.setItem('sw_token', t); localStorage.setItem('sw_user', JSON.stringify(u)) },
  clear() { localStorage.removeItem('sw_token'); localStorage.removeItem('sw_user') },
}

// Lỗi backend: {code, message, request_id, details} -> ném Error có status/code/details
export async function api(method, path, body, headers = {}) {
  if (MOCK) return mock(method, path, body)
  const res = await fetch(BASE + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...(auth.token ? { Authorization: `Bearer ${auth.token}` } : {}), ...headers },
    body: body ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401 && path !== '/auth/login') { auth.clear(); location.assign('/login') }
  const data = await res.json().catch(() => null)
  if (!res.ok) throw Object.assign(new Error(data?.message || res.statusText), { status: res.status, code: data?.code, details: data?.details })
  return data
}

/* ---------- Dữ liệu giả, bám đúng đặc tả v0.1 ---------- */
const mk = (i, fill, alarm) => ({
  id: `WB-00${i}`, code: `WB-00${i}`, name: `Điểm ${i}`, address: `Ngõ ${i} Đại Cồ Việt`, ward_code: 'BK',
  waste_type: 'general', capacity_l: 240, status: 'active', lat: 21.005 + i * 0.0007, lng: 105.844 + i * 0.0005,
  state: fill == null ? null : { device_id: `bin-00${i}`, fill_pct: fill, alarm_active: alarm, latest_quality: 'ok', fresh: true, sampled_at: new Date().toISOString() },
})
let bins = [mk(1, 86.5, true), mk(2, 45, false), mk(3, 8, false), mk(4, null), mk(5, 92, true), mk(6, 60, false), mk(7, 15, false), mk(8, 70, false), mk(9, 5, false), mk(10, 33, false)]

const dev = Object.fromEntries(bins.filter(b => b.state).map(b => [b.id, b.state.device_id]))
const devices = new Set(Object.values(dev))
const acked = new Set()
const err = (st, code, msg) => Object.assign(new Error(msg), { status: st, code })
const alertsOf = () => bins.filter(x => x.state?.alarm_active).map(x => ({
  id: 'a' + x.id, type: 'full', status: acked.has('a' + x.id) ? 'acknowledged' : 'open', severity: 'warning', scope_type: 'bin',
  scope_id: x.id, bin_id: x.id, opened_at: new Date(Date.now() - 3600e3).toISOString(), acknowledged_at: null, acknowledged_by: null, resolved_at: null, resolve_reason: null,
}))

async function mock(m, p, b) {
  await new Promise(r => setTimeout(r, 150))
  const [path, qs] = p.split('?'); const q = new URLSearchParams(qs); const seg = path.split('/')
  if (path === '/auth/login') return { access_token: 'mock', token_type: 'bearer', expires_in: 28800, user: { id: 'u1', display_name: 'Quản trị viên', roles: ['admin'] } }
  if (path === '/auth/me') return auth.user || { id: 'u1', display_name: 'Quản trị viên', roles: ['admin'] }
  if (path === '/auth/change-password') {
    if (!b?.current_password) throw err(422, 'VALIDATION', 'Vui lòng nhập mật khẩu hiện tại')
    if (!b?.new_password || b.new_password.length < 8) throw err(422, 'VALIDATION', 'Mật khẩu mới phải có ít nhất 8 ký tự')
    return { ok: true }
  }
  if (path === '/bins' && m === 'GET') return { items: bins.filter(x => x.status !== 'retired'), next_cursor: null }
  if (path === '/bins' && m === 'POST') {
    if (bins.some(x => x.code === b.code)) throw err(409, 'CONFLICT', 'Mã thùng đã tồn tại')
    const n = { ...b, id: b.code, status: 'active', lat: b.location.coordinates[1], lng: b.location.coordinates[0], state: null }
    bins = [...bins, n]; return n
  }
  if (seg[1] === 'bins' && seg[2]) {
    const bin = bins.find(x => x.id === seg[2])
    if (!bin) throw err(404, 'NOT_FOUND', 'Không tìm thấy thùng')
    if (!seg[3] && m === 'GET') return { ...bin, notes: '', device: dev[bin.id] ? { id: dev[bin.id], lifecycle: 'active', enabled: true } : null, open_alerts: alertsOf().filter(a => a.bin_id === bin.id && (a.status === 'open' || a.status === 'acknowledged')) }
    if (!seg[3] && m === 'PATCH') {
      const lat = b.location?.coordinates?.[1], lng = b.location?.coordinates?.[0]
      bins = bins.map(x => x.id === bin.id ? { ...x, ...b, ...(lat ? { lat, lng } : {}) } : x)
      return bins.find(x => x.id === bin.id)
    }
    if (seg[3] === 'telemetry') {
      if (!dev[bin.id]) return { items: [], next_cursor: null }
      const to = new Date(q.get('to')).getTime(), from = new Date(q.get('from')).getTime()
      const cursor = q.get('cursor') ? parseInt(q.get('cursor'), 10) : 0
      const total = 140, n = Math.min(100, Math.max(0, total - cursor))
      const step = (to - from) / total, base = bin.state?.fill_pct ?? 30
      const items = Array.from({ length: n }, (_, idx) => {
        const i = cursor + idx
        const bad = i % 23 === 7, fill = (base - i * 0.9 + 1000) % 100, t = new Date(to - i * step).toISOString()
        return { message_id: `m${i}`, sampled_at: t, received_at: t, reason: 'periodic', quality: bad ? 'no_echo' : 'ok', fill_pct: bad ? null : fill, distance_mm: null, alarm_active: !bad && fill >= 80, lid_open: false, rssi_dbm: -90, snr_db: 7, time_quality: 'ok' }
      })
      const nextCursor = cursor + n < total ? String(cursor + n) : null
      return { items, next_cursor: nextCursor }
    }
    if (seg[3] === 'assignments' && m === 'POST') {
      if (Object.entries(dev).some(([id, v]) => v === b.device_id && id !== bin.id)) throw err(409, 'CONFLICT', 'Thiết bị đang gắn với thùng khác')
      dev[bin.id] = b.device_id; bin.state = null
      return { bin_id: bin.id, device_id: b.device_id }
    }
  }
  if (path === '/devices' && m === 'POST') {
    if (!/^bin-\d{3,6}$/.test(b.id)) throw err(422, 'VALIDATION', 'Mã thiết bị phải dạng bin-001 (3 đến 6 chữ số)')
    if (devices.has(b.id)) throw err(409, 'CONFLICT', 'Mã thiết bị đã tồn tại')
    devices.add(b.id); return b
  }
  if (seg[1] === 'devices' && seg[3] === 'configs' && m === 'POST') {
    return { ok: true, ...b }
  }
  if (path === '/alerts' && m === 'GET') {
    const statuses = (q.get('status') || 'open').split(',').map(s => s.trim())
    return { items: alertsOf().filter(a => statuses.includes(a.status)), next_cursor: null }
  }
  if (seg[1] === 'alerts' && seg[3] === 'ack') {
    acked.add(seg[2]); return { ...alertsOf().find(a => a.id === seg[2]), status: 'acknowledged', acknowledged_at: new Date().toISOString() }
  }
  if (path === '/stats/waste-by-type') return {
    items: [
      { waste_type: 'general', bin_count: bins.length, collection_count: 24, avg_fill_pct: 71.2, known_weight_kg: 310.5, known_weight_count: 6, unknown_weight_count: 18 },
      { waste_type: 'organic', bin_count: 0, collection_count: 9, avg_fill_pct: 64, known_weight_kg: null, known_weight_count: 0, unknown_weight_count: 9 },
      { waste_type: 'recyclable', bin_count: 0, collection_count: 5, avg_fill_pct: 58.4, known_weight_kg: 42, known_weight_count: 2, unknown_weight_count: 3 },
    ]
  }
  throw err(404, 'NOT_FOUND', `Mock chưa hỗ trợ ${m} ${p}`)
}
