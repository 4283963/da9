import React from 'react'

const STATUS_LABELS = {
  pending: '等待中',
  cloning: '克隆中',
  pushing: '推送中',
  success: '成功',
  failed: '失败',
  cancelled: '已取消',
}

export default function StatusBadge({ status }) {
  const cls = status || 'pending'
  const label = STATUS_LABELS[cls] || cls
  return (
    <span className={`status-badge ${cls}`}>
      <span className="status-dot"></span>
      {label}
    </span>
  )
}
