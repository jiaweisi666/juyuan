/**
 * RoutingPage.jsx - 路由配置页。
 *
 * 控制 AUTO 智能路由开关与反馈自优化，调整「准确率/延迟/成本」权重，
 * 并查看模型画像与最近的自动路由决策。
 */

import { useEffect, useMemo, useState } from 'react'
import {
  getDecisions,
  getProfiles,
  getRoutingConfig,
  getRoutingWeights,
  setRoutingConfig,
  setRoutingWeights,
} from '../api.js'
import { RoutingIcon, RefreshIcon, ZapIcon, CheckIcon, ShieldIcon } from '../components/icons.jsx'
import { Button, Card, Empty, PageHeader, Pill, Select, Toggle } from '../components/ui.jsx'

const TASK_LABELS = {
  general: '通用',
  code_generation: '代码生成',
  knowledge_qa: '知识问答',
  data_analysis: '数据分析',
  creative_writing: '创意写作',
  translation: '翻译',
}

const DIMENSIONS = [
  { key: 'accuracy', label: '准确率', tone: 'text-func-emerald', bar: 'bg-func-emerald' },
  { key: 'latency', label: '低延迟', tone: 'text-func-orange', bar: 'bg-func-orange' },
  { key: 'cost', label: '低成本', tone: 'text-func-violet', bar: 'bg-func-violet' },
]

export default function RoutingPage({ onToast }) {
  const [config, setConfig] = useState(null)
  const [weights, setWeights] = useState({ accuracy: 0.5, latency: 0.2, cost: 0.3 })
  const [profiles, setProfiles] = useState([])
  const [decisions, setDecisions] = useState([])
  const [taskFilter, setTaskFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)

  async function load() {
    setLoading(true)
    try {
      const [c, w, p, d] = await Promise.all([
        getRoutingConfig(),
        getRoutingWeights(),
        getProfiles(),
        getDecisions(40),
      ])
      setConfig(c)
      if (w?.weights) setWeights(w.weights)
      setProfiles(p?.profiles || [])
      setDecisions(d?.decisions || [])
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const total = weights.accuracy + weights.latency + weights.cost || 1
  const normalized = {
    accuracy: Math.round((weights.accuracy / total) * 100),
    latency: Math.round((weights.latency / total) * 100),
    cost: Math.round((weights.cost / total) * 100),
  }

  async function toggleConfig(patch) {
    const prev = config
    setConfig({ ...config, ...patch })
    try {
      const res = await setRoutingConfig(patch)
      setConfig(res)
    } catch (err) {
      setConfig(prev)
      onToast?.(err.message, 'error')
    }
  }

  async function saveWeights() {
    setSaving(true)
    try {
      const res = await setRoutingWeights(weights)
      if (res?.weights) setWeights(res.weights)
      onToast?.('路由权重已保存', 'success')
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setSaving(false)
    }
  }

  const filteredProfiles = useMemo(
    () => (taskFilter ? profiles.filter((p) => p.task_type === taskFilter) : profiles),
    [profiles, taskFilter],
  )

  const taskTypes = useMemo(
    () => [...new Set(profiles.map((p) => p.task_type))].filter(Boolean),
    [profiles],
  )

  return (
    <div className="flex h-full flex-col px-5 py-4">
      <PageHeader
        title="路由配置"
        desc="调整 AUTO 智能路由策略：开关、权重与反馈自优化。"
        actions={
          <Button icon={RefreshIcon} onClick={load} loading={loading}>
            刷新
          </Button>
        }
      />

      <div className="flex-1 overflow-y-auto">
        <div className="grid grid-cols-2 gap-3 pb-3">
          {/* 开关 */}
          <Card className="flex flex-col gap-3 p-3">
            <div className="flex items-center gap-1.5 text-[13px] font-medium text-ink-2">
              <ZapIcon size={14} className="text-brand" /> 运行策略
            </div>
            <Toggle
              checked={!!config?.auto_router_enabled}
              onChange={(v) => toggleConfig({ auto_router_enabled: v })}
              label="启用 AUTO 智能路由"
            />
            <Toggle
              checked={!!config?.feedback_optimize}
              onChange={(v) => toggleConfig({ feedback_optimize: v })}
              label="启用反馈自优化"
            />
            <p className="text-[11px] leading-relaxed text-ink-3">
              关闭 AUTO 后，请求将回退至 DeepSeek 默认模型；反馈自优化会依据点赞/点踩动态调整模型画像。
            </p>
          </Card>

          {/* 权重 */}
          <Card className="flex flex-col gap-2.5 p-3">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-[13px] font-medium text-ink-2">
                <RoutingIcon size={14} className="text-brand" /> 决策权重
              </span>
              <span className="text-[11px] text-ink-3">运行时自动归一化</span>
            </div>
            {DIMENSIONS.map((d) => (
              <div key={d.key} className="flex items-center gap-2">
                <span className="w-[52px] shrink-0 text-[12px] text-ink-2">{d.label}</span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={weights[d.key]}
                  onChange={(e) => setWeights({ ...weights, [d.key]: Number(e.target.value) })}
                  className="h-1 flex-1 cursor-pointer accent-brand"
                />
                <span className={`w-[42px] shrink-0 text-right text-[12px] font-medium ${d.tone}`}>
                  {normalized[d.key]}%
                </span>
              </div>
            ))}
            <div className="mt-1 flex items-center justify-between border-t border-line pt-2">
              <span className="text-[11px] text-ink-3">
                得分 = 准确率×{weights.accuracy.toFixed(2)} + 延迟×{weights.latency.toFixed(2)} + 成本×
                {weights.cost.toFixed(2)}
              </span>
              <Button size="sm" variant="primary" icon={CheckIcon} onClick={saveWeights} loading={saving}>
                保存
              </Button>
            </div>
          </Card>
        </div>

        {/* 画像 */}
        <div className="mb-2 flex items-center justify-between">
          <span className="flex items-center gap-1.5 text-[13px] font-medium text-ink-2">
            <ShieldIcon size={14} className="text-ink-3" /> 模型画像（{filteredProfiles.length}）
          </span>
          <Select
            value={taskFilter}
            onChange={(e) => setTaskFilter(e.target.value)}
            className="w-[140px]"
          >
            <option value="">全部任务类型</option>
            {taskTypes.map((t) => (
              <option key={t} value={t}>
                {TASK_LABELS[t] || t}
              </option>
            ))}
          </Select>
        </div>

        <Card className="mb-3 overflow-hidden">
          <div className="grid grid-cols-[1fr_0.8fr_1fr_0.7fr_0.8fr_0.6fr] gap-2 border-b border-line
            bg-surface-2/60 px-3 py-2 text-[11px] font-medium text-ink-3">
            <span>平台</span>
            <span>变体</span>
            <span>任务类型</span>
            <span>准确率</span>
            <span>平均延迟</span>
            <span className="text-right">样本</span>
          </div>
          <div className="max-h-[180px] overflow-y-auto">
            {filteredProfiles.length === 0 ? (
              <Empty title="暂无画像数据" />
            ) : (
              filteredProfiles.map((p, i) => (
                <div
                  key={`${p.platform}-${p.variant}-${p.task_type}-${i}`}
                  className="grid grid-cols-[1fr_0.8fr_1fr_0.7fr_0.8fr_0.6fr] items-center gap-2 border-b border-line px-3 py-1.5 text-[12px] last:border-b-0"
                >
                  <span className="font-mono text-ink">{p.platform}</span>
                  <span className="font-mono text-ink-2">{p.variant}</span>
                  <span className="text-ink-2">{TASK_LABELS[p.task_type] || p.task_type}</span>
                  <span className="text-func-emerald">{Math.round((p.accuracy || 0) * 100)}%</span>
                  <span className="text-ink-2">{Math.round(p.avg_latency_ms || 0)} ms</span>
                  <span className="text-right font-mono text-ink-3">{p.samples ?? 0}</span>
                </div>
              ))
            )}
          </div>
        </Card>

        {/* 最近决策 */}
        <div className="mb-2 flex items-center gap-1.5 text-[13px] font-medium text-ink-2">
          <RoutingIcon size={14} className="text-ink-3" /> 最近路由决策（{decisions.length}）
        </div>
        <div className="flex flex-col gap-2 pb-2">
          {decisions.length === 0 ? (
            <Card>
              <Empty title="暂无路由记录" desc="发起一次 AUTO 对话后，这里会展示决策详情。" />
            </Card>
          ) : (
            decisions.map((d) => (
              <Card key={d.id} className="px-3 py-2">
                <div className="flex items-center gap-2">
                  <Pill tone={d.auto ? 'brand' : 'neutral'}>{d.auto ? 'AUTO' : '手动'}</Pill>
                  <span className="font-mono text-[12px] text-ink">
                    {d.platform}
                    {d.variant && d.variant !== 'default' ? `:${d.variant}` : ''}
                  </span>
                  {typeof d.score === 'number' && d.score > 0 ? (
                    <span className="text-[11px] text-ink-3">score {d.score.toFixed(3)}</span>
                  ) : null}
                  <span className="flex-1" />
                  <span className="font-mono text-[11px] text-ink-3">
                    {d.requested_model} → {d.resolved_model}
                  </span>
                </div>
                <p className="mt-1 line-clamp-2 text-[11px] leading-relaxed text-ink-3">{d.reason}</p>
              </Card>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
