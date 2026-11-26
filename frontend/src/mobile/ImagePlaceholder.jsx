import { useState, useMemo } from 'react'
import { Image as ImageIcon, Truck, Trash2, MapPin } from 'lucide-react'

/**
 * Trích xuất URL hình ảnh từ đối tượng backend hoặc đường dẫn chuỗi
 * Hỗ trợ các format phổ biến mà Backend có thể trả về sau này:
 * - image_url, photo_url, thumbnail_url, avatar_url, image, photo
 */
export function getBackendImageUrl(source, fallback = null) {
  if (!source) return fallback
  if (typeof source === 'string') return source
  if (typeof source === 'object') {
    return (
      source.image_url ||
      source.photo_url ||
      source.thumbnail_url ||
      source.avatar_url ||
      source.image ||
      source.photo ||
      fallback
    )
  }
  return fallback
}

export default function ImagePlaceholder({
  src,
  fallbackSrc,
  alt,
  label,
  iconType = 'image',
  className = '',
}) {
  const [error, setError] = useState(false)
  const [triedFallback, setTriedFallback] = useState(false)

  // Tự động phân giải URL từ chuỗi hoặc entity backend
  const resolvedSrc = useMemo(() => {
    return getBackendImageUrl(src, fallbackSrc || null)
  }, [src, fallbackSrc])

  const handleError = () => {
    if (!triedFallback && fallbackSrc && resolvedSrc !== fallbackSrc) {
      setTriedFallback(true)
    } else {
      setError(true)
    }
  }

  const currentSrc = triedFallback ? fallbackSrc : resolvedSrc

  if (currentSrc && !error) {
    return (
      <img
        src={currentSrc}
        alt={alt || label || 'Hình ảnh'}
        className={className}
        onError={handleError}
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
