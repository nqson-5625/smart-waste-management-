import { useState } from 'react'
import { Image as ImageIcon, Truck, Trash2, MapPin } from 'lucide-react'

export default function ImagePlaceholder({ src, alt, label, iconType = 'image', className = '' }) {
  const [error, setError] = useState(false)

  if (src && !error) {
    return (
      <img
        src={src}
        alt={alt || label || 'Hình ảnh'}
        className={className}
        onError={() => setError(true)}
        style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
      />
    )
  }

  const renderIcon = () => {
    switch (iconType) {
      case 'truck':
        return <Truck size={36} color="#2e7d32" strokeWidth={1.75} />
      case 'bin':
        return <Trash2 size={36} color="#2e7d32" strokeWidth={1.75} />
      case 'map':
        return <MapPin size={36} color="#e53935" strokeWidth={1.75} />
      default:
        return <ImageIcon size={32} color="#64748b" strokeWidth={1.5} />
    }
  }

  return (
    <div className={`m-img-placeholder ${className}`}>
      {renderIcon()}
      <span>{label || 'Chỗ giữ ảnh (Placeholder)'}</span>
    </div>
  )
}
