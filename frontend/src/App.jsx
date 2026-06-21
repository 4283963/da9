import React, { useState, useEffect, useCallback, useRef } from 'react'
import { repoApi, syncApi } from './api'
import RepoCard from './components/RepoCard'
import TaskDetailModal from './components/TaskDetailModal'

function Toast({ message, type = 'info', onClose }) {
  useEffect(() => {
    const timer = setTimeout(onClose, 3000)
    return () => clearTimeout(timer)
  }, [onClose])

  return (
    <div className={`toast ${type}`}>
      <div className="toast-message">{message}</div>
    </div>
  )
}

export default function App() {
  const [repos, setRepos] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [syncingAll, setSyncingAll] = useState(false)
  const [syncStatus, setSyncStatus] = useState({ running_count: 0, queued_count: 0, max_workers: 3 })
  const [toasts, setToasts] = useState([])
  const [selectedTask, setSelectedTask] = useState(null)
  const [selectedRepoName, setSelectedRepoName] = useState('')
  const toastIdRef = useRef(0)

  const showToast = useCallback((message, type = 'info') => {
    const id = ++toastIdRef.current
    setToasts(prev => [...prev, { id, message, type }])
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id))
  }, [])

  const fetchRepos = useCallback(async () => {
    try {
      const res = await repoApi.list()
      setRepos(res.data)
    } catch (e) {
      setError(e.response?.data?.detail || e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  const fetchSyncStatus = useCallback(async () => {
    try {
      const res = await syncApi.status()
      setSyncStatus(res.data)
    } catch (e) {
      // ignore
    }
  }, [])

  useEffect(() => {
    fetchRepos()
    fetchSyncStatus()
  }, [fetchRepos, fetchSyncStatus])

  useEffect(() => {
    if (!autoRefresh) return
    const interval = setInterval(() => {
      fetchRepos()
      fetchSyncStatus()
    }, 3000)
    return () => clearInterval(interval)
  }, [autoRefresh, fetchRepos, fetchSyncStatus])

  const stats = repos.reduce(
    (acc, r) => {
      acc.total += 1
      if (r.latest_task) {
        if (r.latest_task.status === 'success') acc.success += 1
        else if (r.latest_task.status === 'failed') acc.failed += 1
      }
      return acc
    },
    { total: 0, success: 0, failed: 0 }
  )

  const filteredRepos = repos.filter(r => {
    const matchSearch = r.name.toLowerCase().includes(search.toLowerCase())
    let matchFilter = true
    if (filter !== 'all') {
      const status = r.latest_task?.status || 'pending'
      if (filter === 'active') {
        matchFilter = status === 'cloning' || status === 'pushing' || status === 'pending'
      } else {
        matchFilter = status === filter
      }
    }
    return matchSearch && matchFilter
  })

  const handleSyncAll = async () => {
    setSyncingAll(true)
    try {
      const res = await syncApi.start({ all_active: true })
      showToast(res.data.message, 'success')
      setTimeout(() => {
        fetchRepos()
        fetchSyncStatus()
      }, 500)
    } catch (e) {
      showToast(e.response?.data?.detail || e.message, 'error')
    } finally {
      setSyncingAll(false)
    }
  }

  const handleSyncStarted = (data) => {
    showToast(data.message, 'success')
    setTimeout(() => {
      fetchRepos()
      fetchSyncStatus()
    }, 500)
  }

  const handleShowTask = (task, repoName) => {
    setSelectedTask(task)
    setSelectedRepoName(repoName)
  }

  const isAnyRunning = repos.some(r =>
    r.latest_task && ['cloning', 'pushing', 'pending'].includes(r.latest_task.status)
  )

  return (
    <div className="container">
      <header className="header">
        <div>
          <h1>Git 仓库批量同步监视器</h1>
          <p>监控 cc1 ~ cc10 等仓库从 GitHub 到备份服务器的镜像同步状态</p>
        </div>
      </header>

      <div className="stats-bar">
        <div className="stat-card total">
          <div className="label">仓库总数</div>
          <div className="value">{stats.total}</div>
        </div>
        <div className="stat-card running">
          <div className="label">运行中</div>
          <div className="value">{syncStatus.running_count}</div>
        </div>
        <div className="stat-card success">
          <div className="label">同步成功</div>
          <div className="value">{stats.success}</div>
        </div>
        <div className="stat-card failed">
          <div className="label">同步失败</div>
          <div className="value">{stats.failed}</div>
        </div>
      </div>

      <div className="toolbar">
        <div className="toolbar-left">
          <input
            className="search-input"
            type="text"
            placeholder="搜索仓库名称..."
            value={search}
            onChange={e => setSearch(e.target.value)}
          />
          <select
            className="filter-select"
            value={filter}
            onChange={e => setFilter(e.target.value)}
          >
            <option value="all">全部状态</option>
            <option value="active">运行中</option>
            <option value="success">成功</option>
            <option value="failed">失败</option>
            <option value="pending">等待中</option>
            <option value="cloning">克隆中</option>
            <option value="pushing">推送中</option>
          </select>
        </div>
        <div className="toolbar-right">
          <label className="auto-refresh-toggle">
            <input
              type="checkbox"
              checked={autoRefresh}
              onChange={e => setAutoRefresh(e.target.checked)}
            />
            自动刷新 (3s)
          </label>
          <button
            className="btn btn-secondary"
            onClick={() => { fetchRepos(); fetchSyncStatus() }}
          >
            刷新
          </button>
          <button
            className="btn btn-primary"
            onClick={handleSyncAll}
            disabled={syncingAll || repos.length === 0}
          >
            {syncingAll ? '发起中...' : '全部同步'}
          </button>
        </div>
      </div>

      {error && (
        <div style={{
          padding: '12px 16px',
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid var(--error)',
          borderRadius: 8,
          color: '#fca5a5',
          marginBottom: 20,
        }}>
          错误: {error}
          <button
            style={{ marginLeft: 12, color: '#fca5a5', background: 'none', border: 'none', cursor: 'pointer' }}
            onClick={() => setError('')}
          >
            ✕
          </button>
        </div>
      )}

      {loading ? (
        <div style={{ textAlign: 'center', padding: 60 }}>
          <div className="loading-indicator" style={{ justifyContent: 'center' }}>
            <div className="spinner" /> 加载仓库列表中...
          </div>
        </div>
      ) : filteredRepos.length === 0 ? (
        <div className="empty-state">
          <div className="empty-state-icon">📦</div>
          <h3>没有找到匹配的仓库</h3>
          <p style={{ marginTop: 8 }}>请调整搜索条件或筛选器</p>
        </div>
      ) : (
        <div className="repo-list">
          {filteredRepos.map(repo => (
            <RepoCard
              key={repo.id}
              repo={repo}
              onSyncStarted={handleSyncStarted}
              onShowTask={handleShowTask}
            />
          ))}
        </div>
      )}

      {selectedTask && (
        <TaskDetailModal
          task={selectedTask}
          repoName={selectedRepoName}
          onClose={() => setSelectedTask(null)}
        />
      )}

      {toasts.map(t => (
        <Toast
          key={t.id}
          message={t.message}
          type={t.type}
          onClose={() => removeToast(t.id)}
        />
      ))}
    </div>
  )
}
