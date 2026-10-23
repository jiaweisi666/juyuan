/**
 * ModelsPage.jsx - 模型配置页。
 *
 * 展示网关信息、各平台适配器状态（含连通性测试）与模型别名映射清单。
 */

import { useEffect, useMemo, useState } from 'react'
import {
  getGatewayInfo,
  getModelCatalog,
  getModels,
  getPlatforms,
  refreshModels,
  testPlatform,
} from '../api.js'
import { ModelsIcon, RefreshIcon, ZapIcon, CheckIcon, LinkIcon } from '../components/icons.jsx'
import { Button, Card, Empty, PageHeader, Pill, Spinner } from '../components/ui.jsx'

const STATE_TONE = { ready: 'emerald', degraded: 'orange', unavailable: 'rose' }
const STATE_LABEL = { ready: '就绪', degraded: '模拟降级', unavailable: '不可用' }

export default function ModelsPage({ onToast }) {
  const [info, setInfo] = useState(null)
  const [platforms, setPlatforms] = useState([])
  const [models, setModels] = useState([])
  const [catalog, setCatalog] = useState(null)
  const [loading, setLoading] = useState(true)
  const [platformsLoading, setPlatformsLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [testing, setTesting] = useState({})

  // 核心信息（网关信息/模型清单/目录）本地即可快速返回 → 先渲染页面
  async function loadCore(showSpinner = true) {
    if (showSpinner) setLoading(true)
    try {
      const [i, m, cat] = await Promise.all([
        getGatewayInfo(),
        getModels(),
        getModelCatalog().catch(() => null),
      ])
      setInfo(i)
      setModels(m?.data || [])
      setCatalog(cat)
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      if (showSpinner) setLoading(false)
    }
  }

  // 平台状态需逐个探测底座标签页，耗时较长 → 单独加载，不阻塞页面首屏
  async function loadPlatforms() {
    setPlatformsLoading(true)
    try {
      const p = await getPlatforms()
      setPlatforms(p?.platforms || [])
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setPlatformsLoading(false)
    }
  }

  function load() {
    return Promise.all([loadCore(), loadPlatforms()])
  }

  useEffect(() => {
    loadCore()
    loadPlatforms()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function syncFromBase() {
    setSyncing(true)
    try {
      const cat = await refreshModels()
      setCatalog(cat)
      await Promise.all([loadCore(false), loadPlatforms()])
      if (cat?.source === 'base') {
        onToast?.(`已从底座同步 ${cat?.count || 0} 个模型`, 'success')
      } else {
        // 未同步成功多为「底座暂无已打开站点」等可预期情况，用提示而非报错
        onToast?.(cat?.error || '底座不可达，沿用静态模型', 'info')
      }
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setSyncing(false)
    }
  }

  async function runTest(id) {
    setTesting((s) => ({ ...s, [id]: true }))
    try {
      const res = await testPlatform(id)
      if (res?.healthy) {
        onToast?.(`${id} 连通正常`, 'success')
      } else {
        onToast?.(`${id} 连通失败：${res?.reason || '未知原因'}`, 'error')
      }
      await load()
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setTesting((s) => ({ ...s, [id]: false }))
    }
  }

  // 仅展示当前正式支持的模型：过滤已下线的 auto 与底座返回的站点标识
  // （如 chat.deepseek.com / www.chat.deepseek.com / deepseek）
  const visibleModels = useMemo(
    () =>
      models.filter(
        (m) =>
          m.id !== 'auto' &&
          !m.id.includes('.') &&
          m.id !== 'deepseek' &&
          m.id !== 'web-browser',
      ),
    [models],
  )

  const grouped = useMemo(() => {
    const map = {}
    for (const m of visibleModels) {
      const key = m.owned_by || 'juyuan'
      ;(map[key] = map[key] || []).push(m.id)
    }
    return map
  }, [visibleModels])

  return (
    <div className="flex h-full flex-col px-5 py-4">
      <PageHeader
        title="模型配置"
        desc="当前正式支持 DeepSeek 的 4 个模型；同步底座只用于检查连通性，不会混入站点标识。"
        actions={
          <>
            <Button icon={RefreshIcon} onClick={load} loading={loading}>
              刷新
            </Button>
            <Button variant="primary" icon={RefreshIcon} onClick={syncFromBase} loading={syncing}>
              同步底座模型
            </Button>
          </>
        }
      />

      <div className="flex-1 overflow-y-auto">
        {loading ? (
          <div className="flex h-full items-center justify-center">
            <Spinner size={22} />
          </div>
        ) : (
          <div className="flex flex-col gap-4 pb-2">
            {/* 网关信息 */}
            <Card className="grid grid-cols-3 divide-x divide-line px-1 py-2">
              <InfoCell label="版本" value={info?.version || '-'} />
              <InfoCell
                label="适配器模式"
                value={info?.real_browser_enabled ? '真实浏览器' : '模拟适配器'}
                tone={info?.real_browser_enabled ? 'emerald' : 'orange'}
              />
              <InfoCell label="监听地址" value={`${info?.host || '-'}:${info?.port || '-'}`} />
            </Card>

            {/* 动态模型目录 */}
            <CatalogStrip catalog={catalog} />

            {/* 平台卡片 */}
            <div>
              <SectionTitle icon={ModelsIcon}>接入平台（{platforms.length}）</SectionTitle>
              {platformsLoading && platforms.length === 0 ? (
                <Card className="flex items-center justify-center gap-2 py-6 text-[12px] text-ink-3">
                  <Spinner size={16} />
                  正在探测各平台状态…
                </Card>
              ) : (
              <div className="grid grid-cols-2 gap-3">
                {platforms.map((p) => (
                  <Card key={p.platform_id} className="ui-card-hover flex flex-col gap-3 overflow-hidden p-0">
                    <div className="relative flex items-center justify-between overflow-hidden bg-gradient-to-r from-[#f1f8ff] via-white to-white px-3.5 py-3">
                      <span className="pointer-events-none absolute -right-6 -top-8 size-24 rounded-full bg-brand/10 blur-2xl" />
                      <span className="relative flex items-center gap-2 text-[13px] font-semibold text-ink">
                        <span className="flex size-8 items-center justify-center rounded-xl bg-white text-brand shadow-[0_4px_12px_-8px_rgba(47,134,246,0.7)] ring-1 ring-brand/10">
                          <ZapIcon size={15} />
                        </span>
                        {p.display_name}
                        <span className="rounded-full bg-white/80 px-1.5 py-0.5 text-[9px] font-medium text-ink-3 ring-1 ring-line/70">
                          {p.adapter || 'mock'}
                        </span>
                      </span>
                      <Pill tone={STATE_TONE[p.state] || 'neutral'} dot>
                        {STATE_LABEL[p.state] || p.state}
                      </Pill>
                    </div>
                    <div className="flex flex-wrap gap-1.5 px-3.5">
                      {(p.models || [])
                        .filter((m) => m !== 'auto' && !m.includes('.') && m !== 'deepseek' && m !== 'web-browser')
                        .map((m) => (
                          <span
                            key={m}
                            className="rounded-md border border-brand/10 bg-brand-soft/60 px-1.5 py-0.5 font-mono text-[10px] text-brand-ink"
                          >
                            {m}
                          </span>
                        ))}
                    </div>
                    <div className="mt-auto flex items-center justify-between border-t border-line/60 bg-surface-2/40 px-3.5 py-2.5">
                      <span className="flex items-center gap-1.5 text-[11px] text-ink-3">
                        <span className="size-1.5 rounded-full bg-func-emerald/70" />
                        {p.account_count ?? 0} 个账号
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        icon={CheckIcon}
                        loading={testing[p.platform_id]}
                        onClick={() => runTest(p.platform_id)}
                      >
                        测试
                      </Button>
                    </div>
                    {p.health_reason ? (
                      <p className="px-3.5 pb-2.5 text-[11px] leading-snug text-func-rose">{p.health_reason}</p>
                    ) : null}
                  </Card>
                ))}
              </div>
              )}
            </div>

            {/* 模型别名映射 */}
            <div>
              <SectionTitle icon={LinkIcon}>模型别名映射（{visibleModels.length}）</SectionTitle>
              <Card className="divide-y divide-line/70">
                {Object.entries(grouped).map(([owner, ids]) => (
                  <div key={owner} className="flex items-start gap-3 px-3.5 py-3">
                    <Pill tone="brand" className="mt-0.5 shrink-0">
                      {owner}
                    </Pill>
                    <div className="flex flex-wrap gap-1.5">
                      {ids.map((id) => (
                        <span
                          key={id}
                          className="rounded-md border border-line/80 bg-surface-2/70 px-2 py-0.5 font-mono text-[11px] text-ink-2"
                        >
                          {id}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
                {visibleModels.length === 0 ? <Empty title="暂无模型" /> : null}
              </Card>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function CatalogStrip({ catalog }) {
  const source = catalog?.source === 'base' ? 'base' : 'static'
  const isBase = source === 'base'
  const updated = catalog?.updated_at ? formatTime(catalog.updated_at) : '-'
  return (
    <Card className="flex flex-wrap items-center gap-3 px-3 py-2.5">
      <span className="flex items-center gap-1.5 text-[12px] font-medium text-ink-2">
        <LinkIcon size={14} className="text-ink-3" />
        动态模型目录
      </span>
      <Pill tone={isBase ? 'emerald' : 'orange'} dot>
        {isBase ? '底座同步' : '静态配置'}
      </Pill>
      <span className="text-[12px] text-ink-3">
        {isBase
          ? `已同步 ${catalog?.count || 0} 个模型（站点标识已自动忽略）`
          : '底座不可达，使用 platforms.json 内置模型'}
      </span>
      <span className="text-[11px] text-ink-3">更新于 {updated}</span>
      {catalog?.error ? (
        <span className="text-[11px] text-func-rose">{catalog.error}</span>
      ) : null}
    </Card>
  )
}

function InfoCell({ label, value, tone = 'neutral' }) {
  return (
    <div className="px-4 py-2.5">
      <div className="text-[10px] font-medium uppercase tracking-[0.1em] text-ink-3">{label}</div>
      <div className="mt-1.5">
        {tone === 'neutral' ? (
          <span className="text-[13px] font-semibold text-ink">{value}</span>
        ) : (
          <Pill tone={tone}>{value}</Pill>
        )}
      </div>
    </div>
  )
}

function SectionTitle({ icon: Icon, children }) {
  return (
    <div className="mb-2.5 flex items-center gap-2 text-[13px] font-semibold text-ink-2">
      <span className="flex size-6 items-center justify-center rounded-lg bg-brand-soft/80 text-brand-ink">
        <Icon size={13} />
      </span>
      {children}
    </div>
  )
}

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
