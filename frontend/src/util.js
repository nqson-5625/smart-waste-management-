export const fmt = iso => iso ? new Intl.DateTimeFormat('vi-VN', { timeZone: 'Asia/Ho_Chi_Minh', dateStyle: 'short', timeStyle: 'short' }).format(new Date(iso)) : '—'
export const iso = d => d.toISOString().replace(/\.\d{3}Z$/, 'Z')
