import React, { useState, useEffect } from 'react'
import { taskApi } from '../api'
import StatusBadge from './StatusBadge'

function formatTime(iso) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function formatDuration(seconds) {
  if (!seconds) return '-'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m${s}s`
}

export default function TaskDetailModal({ task, onClose, repoName }) {
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    async function fetchDetail() {
      setLoading(true)
      setError('')
      try {
        const res = await taskApi.get(task.id)
        if (mounted) setDetail(res.data)
      } catch (e) {
        if (mounted) setError(e.response?.data?.detail || e.message)
      } finally {
        if (mounted) setLoading(false)
      }
    }
    fetchDetail()
    return () => { mounted = false }
  }, [task.id])

  const logs = detail?.logs || []
  const t = detail || task

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <div className="modal-title">
            任务详情 · {repoName} · #{task.id}
          </div>
          <button className="modal-close" onClick={onClose}>&times;</button>
        </div>
        <div className="modal-body">
          <div className="task-info-grid">
            <div className="task-info-item">
              <span className="task-info-label">状态</span>
              <span className="task-info-value"><StatusBadge status={t.status} /></span>
            </div>
            <div className="task-info-item">
              <span className="task-info-label">进度</span>
              <span className="task-info-value">{t.progress}%</span>
            </div>
            <div className="task-info-item">
              <span className="task-info-label">阶段</span>
              <span className="task-info-value">{t.stage || '-'}</span>
            </div>
            <div className="task-info-item">
              <span className="task-info-label">耗时</span>
              <span className="task-info-value">{formatDuration(t.duration_seconds)}</span>
            </div>
            <div className="task-info-item">
              <span className="task-info-label">开始时间</span>
              <span className="task-info-value">{formatTime(t.started_at)}</span>
            </div>
            <div className="task-info-item">
              <span className="task-info-label">结束时间</span>
              <span className="task-info-value">{formatTime(t.finished_at)}</span>
            </div>
            <div className="task-info-item" style={{ gridColumn: '1 / -1' }}>
              <span className="task-info-label">当前消息</span>
              <span className="task-info-value" style={{ fontFamily: 'inherit' }}>{t.message || '-'}</span>
            </div>
          </div>

          <div style={{ marginBottom: 12, color: 'var(--text-muted)', fontSize: 13 }}>
            执行日志 ({logs.length} 条)
          </div>
          {loading && (
            <div className="loading-indicator" style={{ padding: '20px 0' }}>
              <div className="spinner" /> 加载日志中...
            </div>
          )}
          {error && (
            <div style={{ color: 'var(--error)', padding: '12px 0' }}>{error}</div>
          )}
          {!loading && logs.length === 0 && (
            <div style={{ color: 'var(--text-muted)', padding: '20px 0', textAlign: 'center' }}>暂无日志</div>
          )}
          <div className="log-panel">
            {logs.map(log => (
              <div key={log.id} className="log-entry">
                <span className="log-time">{formatTime(log.created_at)}</span>
                <span className={`log-level ${log.level}`}>{log.level}</span>
                <span>{log.message}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="modal-footer">
          <button className="btn btn-secondary" onClick={onClose}>关闭</button>
        </div>
      </div>
    </div>
  )
}
