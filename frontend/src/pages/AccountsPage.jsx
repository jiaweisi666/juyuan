/**
 * AccountsPage.jsx - 账号管理页。
 *
 * 账号池增删改、批量导入与连通性体检；敏感字段仅以掩码展示（密文存储于后端）。
 */

import { useEffect, useMemo, useState } from 'react'
import {
  accountsHealthCheck,
  createAccount,
  deleteAccount,
  getAccounts,
  getPlatforms,
  importAccounts,
  updateAccount,
} from '../api.js'
import {
  AccountsIcon,
  PlusIcon,
  RefreshIcon,
  TrashIcon,
  UploadIcon,
  ShieldIcon,
  CheckIcon,
  SearchIcon,
} from '../components/icons.jsx'
import { Button, Card, Empty, Field, Input, Modal, PageHeader, Pill, Select, Textarea } from '../components/ui.jsx'

const STATUS_META = {
  active: { tone: 'emerald', label: '正常' },
  cooldown: { tone: 'orange', label: '冷却中' },
  limited: { tone: 'orange', label: '限流' },
  invalid: { tone: 'rose', label: '失效' },
}

function emptyForm() {
  return { platform: '', email: '', session_key: '', cookies: '', remark: '' }
}

export default function AccountsPage({ onToast }) {
  const [accounts, setAccounts] = useState([])
  const [summary, setSummary] = useState({ total: 0, active: 0, cooldown: 0, invalid: 0 })
  const [platforms, setPlatforms] = useState([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [query, setQuery] = useState('')
  const [filter, setFilter] = useState('')

  const [showAdd, setShowAdd] = useState(false)
  const [form, setForm] = useState(emptyForm())
  const [showImport, setShowImport] = useState(false)
  const [importText, setImportText] = useState('')

  async function load() {
    setLoading(true)
    try {
      const [a, p] = await Promise.all([getAccounts(), getPlatforms()])
      setAccounts(a?.accounts || [])
      setSummary(a?.summary || { total: 0, active: 0, cooldown: 0, invalid: 0 })
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
  }, [])

  const filtered = useMemo(() => {
    return accounts.filter((a) => {
      if (filter && a.platform !== filter) return false
      if (query) {
        const q = query.toLowerCase()
        return (
          (a.email || '').toLowerCase().includes(q) ||
          (a.platform || '').toLowerCase().includes(q) ||
          (a.remark || '').toLowerCase().includes(q)
        )
      }
      return true
    })
  }, [accounts, query, filter])

  async function submitAdd() {
    if (!form.platform) {
      onToast?.('请选择平台', 'error')
      return
    }
    setBusy(true)
    try {
      await createAccount(form)
      onToast?.('账号已添加', 'success')
      setShowAdd(false)
      setForm(emptyForm())
      load()
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function runImport() {
    let items
    try {
      items = JSON.parse(importText)
      if (!Array.isArray(items)) throw new Error('需为 JSON 数组')
    } catch (err) {
      onToast?.(`导入格式错误：${err.message}`, 'error')
      return
    }
    setBusy(true)
    try {
      const res = await importAccounts(items)
      onToast?.(`导入完成：新增 ${res.added}，跳过 ${res.skipped}`, 'success')
      setShowImport(false)
      setImportText('')
      load()
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  async function removeAccount(a) {
    if (!window.confirm(`确认删除账号 ${a.email || a.id}？`)) return
    try {
      await deleteAccount(a.id)
      onToast?.('账号已删除', 'success')
      load()
    } catch (err) {
      onToast?.(err.message, 'error')
    }
  }

  async function toggleStatus(a) {
    const next = a.status === 'invalid' ? 'active' : 'invalid'
    try {
      await updateAccount(a.id, { status: next })
      load()
    } catch (err) {
      onToast?.(err.message, 'error')
    }
  }

  async function healthCheck() {
    setBusy(true)
    try {
      const res = await accountsHealthCheck()
      const healthy = (res?.results || []).filter((r) => r.healthy).length
      onToast?.(`连通性体检：${healthy}/${(res?.results || []).length} 个平台可用`, 'success')
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex h-full flex-col px-5 py-4">
      <PageHeader
        title="账号管理"
        desc="集中管理各平台账号，支持批量导入与连通性体检。敏感凭据加密存储，仅展示掩码。"
        actions={
          <>
            <Button icon={ShieldIcon} onClick={healthCheck} loading={busy}>
              体检
            </Button>
            <Button icon={UploadIcon} onClick={() => setShowImport(true)}>
              导入
            </Button>
            <Button variant="primary" icon={PlusIcon} onClick={() => setShowAdd(true)}>
              新增账号
            </Button>
          </>
        }
      />

      {/* 概览 */}
      <div className="mb-3 grid grid-cols-4 gap-2.5">
        <StatCard label="账号总数" value={summary.total} tone="brand" />
        <StatCard label="正常" value={summary.active} tone="emerald" />
        <StatCard label="冷却中" value={summary.cooldown} tone="orange" />
        <StatCard label="失效" value={summary.invalid} tone="rose" />
      </div>

      {/* 过滤栏 */}
      <div className="mb-2 flex items-center gap-2">
        <div className="relative flex-1">
          <SearchIcon size={14} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-ink-3" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索邮箱 / 备注"
            className="pl-8"
          />
        </div>
        <Select value={filter} onChange={(e) => setFilter(e.target.value)} className="w-[150px]">
          <option value="">全部平台</option>
          {platforms.map((p) => (
            <option key={p.platform_id} value={p.platform_id}>
              {p.display_name}
            </option>
          ))}
        </Select>
        <Button icon={RefreshIcon} onClick={load} loading={loading} />
      </div>

      {/* 列表 */}
      <Card className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="grid shrink-0 grid-cols-[1.4fr_1.6fr_0.8fr_0.9fr_auto] gap-2 border-b border-line
          bg-surface-2/60 px-3 py-2 text-[11px] font-medium text-ink-3">
          <span>平台</span>
          <span>账号 / 备注</span>
          <span>状态</span>
          <span>调用 / 成功率</span>
          <span className="text-right">操作</span>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {filtered.length === 0 ? (
            <Empty icon={AccountsIcon} title="暂无账号" desc="点击「新增账号」或「导入」批量添加。" />
          ) : (
            filtered.map((a) => {
              const meta = STATUS_META[a.status] || { tone: 'neutral', label: a.status }
              const rate = a.call_count ? Math.round((a.success_count / a.call_count) * 100) : 0
              return (
                <div
                  key={a.id}
                  className="grid grid-cols-[1.4fr_1.6fr_0.8fr_0.9fr_auto] items-center gap-2 border-b border-line px-3 py-2 last:border-b-0 hover:bg-surface-2/50"
                >
                  <span className="font-mono text-[12px] text-ink">{a.platform}</span>
                  <div className="min-w-0">
                    <div className="truncate text-[12px] text-ink">{a.email || '—'}</div>
                    <div className="truncate font-mono text-[11px] text-ink-3">
                      {a.masked_session || (a.has_cookies ? 'cookies 已配置' : '无凭据')}
                    </div>
                  </div>
                  <Pill tone={meta.tone} dot>
                    {meta.label}
                  </Pill>
                  <span className="text-[12px] text-ink-2">
                    {a.call_count} / {rate}%
                  </span>
                  <div className="flex items-center justify-end gap-1">
                    <Button size="sm" variant="ghost" onClick={() => toggleStatus(a)}>
                      {a.status === 'invalid' ? '启用' : '停用'}
                    </Button>
                    <button
                      onClick={() => removeAccount(a)}
                      className="rounded p-1 text-ink-3 hover:text-func-rose"
                    >
                      <TrashIcon size={14} />
                    </button>
                  </div>
                </div>
              )
            })
          )}
        </div>
      </Card>

      {/* 新增 */}
      <Modal
        open={showAdd}
        title="新增账号"
        onClose={() => setShowAdd(false)}
        footer={
          <>
            <Button onClick={() => setShowAdd(false)}>取消</Button>
            <Button variant="primary" icon={CheckIcon} onClick={submitAdd} loading={busy}>
              保存
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-3">
          <Field label="平台">
            <Select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}>
              <option value="">请选择平台</option>
              {platforms.map((p) => (
                <option key={p.platform_id} value={p.platform_id}>
                  {p.display_name} ({p.platform_id})
                </option>
              ))}
            </Select>
          </Field>
          <Field label="邮箱 / 标识">
            <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
          <Field label="Session Key" hint="敏感字段，后端加密存储">
            <Input
              value={form.session_key}
              onChange={(e) => setForm({ ...form, session_key: e.target.value })}
            />
          </Field>
          <Field label="Cookies" hint="可粘贴 JSON 或原始 Cookie 字符串">
            <Textarea
              rows={3}
              value={form.cookies}
              onChange={(e) => setForm({ ...form, cookies: e.target.value })}
            />
          </Field>
          <Field label="备注">
            <Input value={form.remark} onChange={(e) => setForm({ ...form, remark: e.target.value })} />
          </Field>
        </div>
      </Modal>

      {/* 导入 */}
      <Modal
        open={showImport}
        title="批量导入账号"
        onClose={() => setShowImport(false)}
        width="520px"
        footer={
          <>
            <Button onClick={() => setShowImport(false)}>取消</Button>
            <Button variant="primary" icon={UploadIcon} onClick={runImport} loading={busy}>
              导入
            </Button>
          </>
        }
      >
        <Field
          label="账号 JSON 数组"
          hint='示例：[{"platform":"deepseek","email":"a@b.com","session_key":"...","remark":"主号"}]'
        >
          <Textarea
            rows={9}
            className="font-mono text-[12px]"
            placeholder='[{"platform":"deepseek","email":"...","session_key":"..."}]'
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
          />
        </Field>
      </Modal>
    </div>
  )
}

function StatCard({ label, value, tone }) {
  const toneCls = {
    brand: 'text-brand-ink bg-brand-soft',
    emerald: 'text-func-emerald bg-func-emerald-soft',
    orange: 'text-func-orange bg-func-orange-soft',
    rose: 'text-func-rose bg-func-rose-soft',
  }[tone]
  return (
    <Card className="flex items-center justify-between px-3 py-2.5">
      <span className="text-[12px] text-ink-3">{label}</span>
      <span className={`rounded-md px-2 py-0.5 text-[15px] font-semibold ${toneCls}`}>{value}</span>
    </Card>
  )
}
