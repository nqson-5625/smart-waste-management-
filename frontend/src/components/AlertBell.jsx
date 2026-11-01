import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { api } from '../api'
import { fmt } from '../util'

const TYPES = { full: 'Thùng đầy', sensor_fault: 'Cảm biến lỗi', device_stale: 'Thiết bị mất liên lạc', gateway_offline: 'Gateway mất kết nối' }

export default function AlertBell() {
  const qc = useQueryClient()
  const [open, setOpen] = useState(false)
  const { data } = useQuery({
    queryKey: ['alerts', 'active'],
    queryFn: () => api('GET', '/alerts?status=open,acknowledged&limit=100'),
    refetchInterval: 30000,
  })
  const ack = useMutation({
    mutationFn: id => api('POST', `/alerts/${id}/ack`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['alerts'] }),
  })
  const items = data?.items || []
  return (
    <div className="bellwrap">
      <button className="bell" onClick={() => setOpen(!open)} aria-label="Cảnh báo đang mở">
        🔔{items.length > 0 && <i>{items.length > 99 ? '99+' : items.length}</i>}
      </button>
      {open && (
        <div className="panel">
          <b>Cảnh báo hoạt động</b>
          {items.length === 0 && <p className="empty">Không có cảnh báo cần xử lý.</p>}
          {items.map(a => (
            <div key={a.id} className={`alert ${a.severity}`}>
              <div>
                <b>{TYPES[a.type] || a.type}</b> · {a.bin_id ? <Link to={`/bins/${a.bin_id}`} onClick={() => setOpen(false)}>{a.bin_id}</Link> : a.scope_id}
                <br /><small>Mở lúc {fmt(a.opened_at)}</small>
              </div>
              {a.status === 'acknowledged' ? (
                <span className="hint" style={{ fontSize: '11px', whiteSpace: 'nowrap' }}>Đã xem</span>
              ) : (
                <button className="mini" disabled={ack.isPending} onClick={() => ack.mutate(a.id)}>Đã xem</button>
              )}
            </div>
          ))}
          {ack.error && <p className="err">Không xác nhận được: {ack.error.message}</p>}
        </div>
      )}
    </div>
  )
}
