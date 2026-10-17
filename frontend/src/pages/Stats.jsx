import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { api } from '../api'
import { WASTE } from './Bins'
import { iso } from '../util'

const day = d => new Date(d.getTime() + 7 * 3600e3).toISOString().slice(0, 10) // ngày theo giờ VN

export default function Stats() {
  const [from, setFrom] = useState(day(new Date(Date.now() - 30 * 86400e3)))
  const [to, setTo] = useState(day(new Date()))
  const { data, isLoading, error } = useQuery({
    queryKey: ['stats', from, to],
    queryFn: () => api('GET', `/stats/waste-by-type?from=${iso(new Date(from + 'T00:00:00+07:00'))}&to=${iso(new Date(to + 'T23:59:59+07:00'))}`),
  })
  const rows = Array.isArray(data) ? data : data?.items || [] // đặc tả chưa nói rõ trả mảng hay {items}
  const max = Math.max(1, ...rows.map(r => r.collection_count))
  return (
    <>
      <div className="row filter">
        <label>Từ ngày<input type="date" value={from} max={to} onChange={e => setFrom(e.target.value)} /></label>
        <label>Đến ngày<input type="date" value={to} min={from} onChange={e => setTo(e.target.value)} /></label>
      </div>
      {isLoading ? <p className="empty">Đang tải…</p> : error ? <p className="err">{error.message}</p> : (
        <>
          <table className="tbl">
            <thead><tr><th>Loại rác</th><th>Số thùng</th><th>Lượt thu gom</th><th>Mức đầy TB</th><th>Khối lượng có cân (kg)</th><th>Lượt chưa có cân</th></tr></thead>
            <tbody>
              {rows.map(r => (
                <tr key={r.waste_type}>
                  <td>{WASTE[r.waste_type] || r.waste_type}</td><td>{r.bin_count}</td>
                  <td><div className="bar"><span style={{ width: `${(r.collection_count / max) * 100}%` }} />{r.collection_count}</div></td>
                  <td>{r.avg_fill_pct != null ? `${r.avg_fill_pct.toFixed(1)}%` : '—'}</td>
                  <td>{r.known_weight_kg ?? '—'}</td><td>{r.unknown_weight_count}</td>
                </tr>
              ))}
              {rows.length === 0 && <tr><td colSpan="6" className="empty">Không có dữ liệu trong khoảng này.</td></tr>}
            </tbody>
          </table>
          <p className="hint">Khối lượng chỉ cộng các lượt thu gom có cân; không suy ra từ mức đầy.</p>
        </>
      )}
    </>
  )
}
