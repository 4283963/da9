import React from 'react'
import StatusBadge from './StatusBadge'
import TaskDetailModal from './TaskDetailModal'
import { syncApi, repoApi } from '../api'

function formatTime(iso) {
  if (!iso) return '从未同步'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function formatDuration(seconds) {
  if (!seconds) return '-'
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${m}m${s}s`
}

export default function RepoCard({ repo, onSyncStarted, onShowTask }) {
  const [syncing, setSyncing] = React.useState(false)
  const [showHistory, setShowHistory] = React.useState(false)
  const [history, setHistory] = React.useState([])
  const [historyLoading, setHistoryLoading] = React.useState(false)

  const task = repo.latest_task
  const statusClass = task?.status || 'pending'

  const handleSync = async (e) => {
    e.stopPropagation()
    if (syncing) return
    setSyncing(true)
    try {
      const res = await syncApi.startSingle(repo.id)
      onSyncStarted && onSyncStarted(res.data)
    } finally {
      setSyncing(false)
    }
  }

  const handleViewDetails = async (e) => {
    e.stopPropagation()
    if (task) {
      onShowTask && onShowTask(task, repo.name)
    }
  }

  const handleShowHistory = async (e) => {
    e.stopPropagation()
    setShowHistory(!showHistory)
    if (!showHistory && history.length === 0) {
      setHistoryLoading(true)
      try {
        const res = await repoApi.tasks(repo.id, { limit: 10 })
        setHistory(res.data)
      } catch (e) {
        console.error('加载历史失败:', e)
      } finally {
        setHistoryLoading(false)
      }
    }
  }

  const handleHistoryItem = (t) => {
    onShowTask && onShowTask(t, repo.name)
  }

  return (
    <>
      <div className={`repo-card ${statusClass}`}>
        <div className="repo-header">
          <div>
            <div className="repo-name-row">
              <span className="repo-id">#{repo.id}</span>
              <span className="repo-name">{repo.name}</span>
              <StatusBadge status={task?.status || 'pending'} />
            </div>
            {repo.description && (
              <div style={{ color: 'var(--text-muted)', fontSize: 13, marginTop: 6 }}>
                {repo.description}
              </div>
            )}
          </div>
          <div className="repo-actions">
            <button
              className="btn btn-sm btn-secondary"
              onClick={handleViewDetails}
              disabled={!task}
            >
              详情
            </button>
            <button
              className="btn btn-sm btn-secondary"
              onClick={handleShowHistory}
            >
              历史
            </button>
            <button
              className="btn btn-sm btn-primary"
              onClick={handleSync}
              disabled={syncing || (task && ['cloning', 'pushing', 'pending'].includes(task.status))}
            >
              {syncing ? '发起中...' : '立即同步'}
            </button>
          </div>
        </div>

        <div className="repo-urls">
          <div className="url-block">
            <div className="url-label">源仓库 (GitHub)</div>
            <div className="url-value">{repo.source_url}</div>
          </div>
          <div className="url-block">
            <div className="url-label">备份服务器</div>
            <div className="url-value">{repo.target_url}</div>
          </div>
        </div>

        {task ? (
          <div className="progress-section">
            <div className="progress-header">
              <span className="progress-stage">
                {task.stage
                  ? {
                      starting: '任务初始化',
                      clone: '克隆源仓库',
                      clone_done: '源仓库克隆完成',
                      remote_check: '配置备份地址',
                      push: '推送到备份服务器',
                      done: '同步完成',
                      error: '错误处理',
                    }[task.stage] || task.stage
                  : '等待中'}
              </span>
              <span className="progress-percent">{task.progress}%</span>
            </div>
            <div className="progress-bar">
              <div
                className={`progress-fill ${task.status}`}
                style={{ width: `${task.progress}%` }}
              />
            </div>
            {task.message && (
              <div className={`progress-message ${task.status === 'failed' ? 'error' : ''}`}>
                {task.message}
              </div>
            )}
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: 13, padding: '8px 0' }}>
            尚未执行过同步任务
          </div>
        )}

        <div className="repo-meta">
          <div className="repo-stats">
            <div className="repo-stat">
              <span style={{ color: 'var(--text-muted)' }}>总次数</span>
              <span className="stat-num">{repo.total_tasks}</span>
            </div>
            <div className="repo-stat">
              <span style={{ color: 'var(--success)' }}>成功</span>
              <span className="stat-num">{repo.success_count}</span>
            </div>
            <div className="repo-stat">
              <span style={{ color: 'var(--error)' }}>失败</span>
              <span className="stat-num">{repo.failed_count}</span>
            </div>
          </div>
          <div className="task-meta">
            {task && (
              <>
                <span>上次: {formatTime(task.created_at)}</span>
                <span>耗时: {formatDuration(task.duration_seconds)}</span>
              </>
            )}
          </div>
        </div>

        {showHistory && (
          <div style={{
            marginTop: 16,
            padding: 16,
            background: 'var(--bg-primary)',
            borderRadius: 6,
            border: '1px solid var(--border-color)',
          }}>
            <div style={{
              color: 'var(--text-muted)',
              fontSize: 13,
              marginBottom: 12,
              fontWeight: 600,
            }}>同步历史（最近 10 条）</div>
            {historyLoading ? (
              <div className="loading-indicator">
                <div className="spinner" /> 加载中...
              </div>
            ) : history.length === 0 ? (
              <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: 12 }}>
                暂无历史记录
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                {history.map((t) => (
                  <div
                    key={t.id}
                    onClick={() => handleHistoryItem(t)}
                    style={{
                      display: 'flex',
                      justifyContent: 'space-between',
                      alignItems: 'center',
                      padding: '8px 12px',
                      background: 'var(--bg-secondary)',
                      borderRadius: 6,
                      cursor: 'pointer',
                    }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                      <StatusBadge status={t.status} />
                      <span style={{
                        fontFamily: "'SF Mono', Monaco, monospace",
                        fontSize: 12,
                        color: 'var(--text-secondary)',
                      }}>
                        #{t.id}
                      </span>
                    </div>
                    <div style={{ display: 'flex', gap: 16, fontSize: 12, color: 'var(--text-muted)' }}>
                      <span>进度 {t.progress}%</span>
                      <span>{formatTime(t.created_at)}</span>
                      <span>{formatDuration(t.duration_seconds)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </>
  )
}
