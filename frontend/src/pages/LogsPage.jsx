/**
 * LogsPage.jsx - 日志与统计页。
 *
 * 顶部为 24 小时概览与调用趋势图，下方为可过滤的调用日志明细。
 */

import { useEffect, useMemo, useState } from 'react'
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { getLogs, getPlatforms, getStatsSeries, getStatsSummary } from '../api.js'
import { LogsIcon, RefreshIcon, DownloadIcon, SearchIcon } from '../components/icons.jsx'
import { Button, Card, Empty, Input, PageHeader, Pill, Select, Spinner } from '../components/ui.jsx'

const STATUS_TONE = { ok: 'emerald', error: 'rose', degraded: 'orange' }
const PAGE_SIZE = 50

export default function LogsPage({ onToast }) {
  const [summary, setSummary] = useState(null)
  const [series, setSeries] = useState([])
  const [logs, setLogs] = useState([])
  const [platforms, setPlatforms] = useState([])
  const [status, setStatus] = useState('')
  const [platform, setPlatform] = useState('')
  const [query, setQuery] = useState('')
  const [offset, setOffset] = useState(0)
  const [loading, setLoading] = useState(true)

  async function load() {
    setLoading(true)
    try {
      const [s, se, l, p] = await Promise.all([
        getStatsSummary(),
        getStatsSeries(24),
        getLogs({ limit: PAGE_SIZE, offset, status, platform }),
        getPlatforms().catch(() => ({ platforms: [] })),
      ])
      setSummary(s)
      setSeries(se?.series || [])
      setLogs(l?.logs || [])
      setPlatforms(p?.platforms || [])
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [offset, status, platform])

  const filtered = useMemo(() => {
    if (!query) return logs
    const q = query.toLowerCase()
    return logs.filter(
      (l) =>
        (l.requested_model || '').toLowerCase().includes(q) ||
        (l.resolved_model || '').toLowerCase().includes(q) ||
        (l.platform || '').toLowerCase().includes(q),
    )
  }, [logs, query])

  function exportJson() {
    const blob = new Blob([JSON.stringify(filtered, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `juyuan-logs-${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex h-full flex-col px-5 py-4">
      <PageHeader
        title="日志与统计"
        desc="近 24 小时调用概览、趋势与逐条调用日志。"
        actions={
          <>
            <Button icon={DownloadIcon} onClick={exportJson} disabled={!filtered.length}>
              导出
            </Button>
            <Button icon={RefreshIcon} onClick={load} loading={loading}>
              刷新
            </Button>
          </>
        }
      />

      {/* 概览 */}
      <div className="mb-3 grid grid-cols-4 gap-2.5">
        <StatCard label="总调用" value={summary?.total ?? 0} />
        <StatCard
          label="成功率"
          value={`${Math.round((summary?.success_rate || 0) * 100)}%`}
          tone="emerald"
        />
        <StatCard label="平均延迟" value={`${Math.round(summary?.avg_latency_ms || 0)} ms`} tone="orange" />
        <StatCard label="总 Tokens" value={summary?.total_tokens ?? 0} tone="violet" />
      </div>

      {/* 趋势图 */}
      <Card className="mb-3 px-3 py-2">
        <div className="mb-1 text-[12px] font-medium text-ink-2">调用趋势（每小时）</div>
        <div className="h-[120px]">
          {series.length === 0 ? (
            <div className="flex h-full items-center justify-center text-[12px] text-ink-3">
              暂无调用数据
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData(series)} margin={{ top: 4, right: 8, left: -18, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.918 0.004 106)" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 10, fill: 'oklch(0.602 0.007 106)' }} tickLine={false} axisLine={false} />
                <YAxis tick={{ fontSize: 10, fill: 'oklch(0.602 0.007 106)' }} tickLine={false} axisLine={false} allowDecimals={false} />
                <Tooltip
                  contentStyle={{
                    fontSize: 12,
                    borderRadius: 8,
                    border: '1px solid oklch(0.918 0.004 106)',
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="count"
                  name="调用量"
                  stroke="oklch(0.62 0.155 240)"
                  fill="oklch(0.955 0.026 240)"
                  strokeWidth={1.6}
                />
              </AreaChart>
            </ResponsiveContainer>
          )}
        </div>
      </Card>

      {/* 过滤 */}
      <div className="mb-2 flex items-center gap-2">
        <div className="relative flex-1">
          <SearchIcon size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-3" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索模型"
            className="pl-8"
          />
        </div>
        <Select
          value={status}
          onChange={(e) => {
            setOffset(0)
            setStatus(e.target.value)
          }}
          className="w-[120px]"
        >
          <option value="">全部状态</option>
          <option value="ok">成功</option>
          <option value="error">失败</option>
        </Select>
        <Select
          value={platform}
          onChange={(e) => {
            setOffset(0)
            setPlatform(e.target.value)
          }}
          className="w-[140px]"
        >
          <option value="">全部平台</option>
          {platforms.map((p) => (
            <option key={p.platform_id} value={p.platform_id}>
              {p.display_name}
            </option>
          ))}
        </Select>
      </div>

      {/* 日志表 */}
      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="grid shrink-0 grid-cols-[1.1fr_1.2fr_0.9fr_0.7fr_0.7fr_0.9fr] gap-2 border-b border-line
          bg-surface-2/60 px-3 py-2 text-[11px] font-medium text-ink-3">
          <span>时间</span>
          <span>请求 → 解析</span>
          <span>平台</span>
          <span>状态</span>
          <span>延迟</span>
          <span className="text-right">Tokens</span>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {loading ? (
            <div className="flex h-full items-center justify-center">
              <Spinner size={20} />
            </div>
          ) : filtered.length === 0 ? (
            <Empty icon={LogsIcon} title="暂无日志" desc="调用网关后，明细会在此展示。" />
          ) : (
            filtered.map((l) => (
              <div
                key={l.id}
                className="grid grid-cols-[1.1fr_1.2fr_0.9fr_0.7fr_0.7fr_0.9fr] items-center gap-2 border-b border-line px-3 py-1.5 text-[12px] last:border-b-0"
              >
                <span className="font-mono text-ink-3">{fmtTime(l.ts)}</span>
                <span className="truncate font-mono text-ink-2">
                  {l.requested_model} → {l.resolved_model}
                </span>
                <span className="truncate font-mono text-ink">{l.platform}</span>
                <Pill tone={STATUS_TONE[l.status] || 'neutral'} dot>
                  {l.status}
                </Pill>
                <span className="text-ink-2">{l.latency_ms} ms</span>
                <span className="text-right font-mono text-ink-3">{l.total_tokens ?? 0}</span>
              </div>
            ))
          )}
        </div>
        <div className="flex shrink-0 items-center justify-between border-t border-line px-3 py-2">
          <span className="text-[11px] text-ink-3">
            第 {Math.floor(offset / PAGE_SIZE) + 1} 页
          </span>
          <div className="flex gap-1.5">
            <Button size="sm" onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))} disabled={offset === 0}>
              上一页
            </Button>
            <Button size="sm" onClick={() => setOffset(offset + PAGE_SIZE)} disabled={logs.length < PAGE_SIZE}>
              下一页
            </Button>
          </div>
        </div>
      </Card>
    </div>
  )
}

function StatCard({ label, value, tone = 'brand' }) {
  const toneCls = {
    brand: 'text-brand-ink',
    emerald: 'text-func-emerald',
    orange: 'text-func-orange',
    violet: 'text-func-violet',
  }[tone]
  return (
    <Card className="px-3 py-2.5">
      <div className="text-[11px] text-ink-3">{label}</div>
      <div className={`mt-0.5 text-[18px] font-semibold leading-tight ${toneCls}`}>{value}</div>
    </Card>
  )
}

function chartData(series) {
  return series.map((s) => {
    const d = new Date(s.ts * 1000)
    return { ...s, label: `${String(d.getHours()).padStart(2, '0')}:00` }
  })
}

function fmtTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}
