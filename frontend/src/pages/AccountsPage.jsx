/**
 * AccountsPage.jsx - 账号管理页。
 *
 * 账号池增删改、批量导入与连通性体检；敏感字段仅以掩码展示（密文存储于后端）。
 */

import { useEffect, useMemo, useState } from 'react'
import {
  accountsHealthCheck,
  autoImportAccounts,
  createAccount,
  deleteAccount,
  getAccounts,
  getPlatforms,
  importAccounts,
  openLoginPage,
  updateAccount,
} from '../api.js'
import {
  AccountsIcon,
  LinkIcon,
  PlusIcon,
  RefreshIcon,
  TrashIcon,
  UploadIcon,
  ShieldIcon,
  CheckIcon,
  SearchIcon,
  ZapIcon,
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
  const [showLoginPicker, setShowLoginPicker] = useState(false)

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
    if (!form.email.trim()) {
      onToast?.('请填写邮箱 / 标识', 'error')
      return
    }
    if (!form.session_key.trim() && !form.cookies.trim()) {
      onToast?.('请至少填写 Session Key 或 Cookies 中的一项', 'error')
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

  // 按钮一：读取受控浏览器中已登录站点的 Cookie 并写入账号池（重复点击即刷新）
  async function handleAutoImport() {
    setBusy(true)
    try {
      const res = await autoImportAccounts()
      const added = res?.added || 0
      const updated = res?.updated || 0
      const skipped = res?.skipped || 0
      if (added + updated === 0) {
        onToast?.(
          '未发现已登录站点，请先「登录导入」或在受控浏览器中登录大模型官网后再试',
          'error',
        )
      } else {
        onToast?.(`自动导入完成：新增 ${added}，更新 ${updated}，跳过 ${skipped}`, 'success')
      }
      load()
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  // 按钮二：在受控浏览器中打开平台官方登录页，登录后回到「一键自动导入」即可
  async function handleOpenLogin(platformId) {
    setShowLoginPicker(false)
    setBusy(true)
    try {
      const res = await openLoginPage(platformId)
      onToast?.(
        res?.success === false
          ? '已尝试打开登录页，请确认受控浏览器已启动'
          : '已打开官方登录页，登录完成后点击「一键自动导入」',
        res?.success === false ? 'error' : 'success',
      )
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
            <Button icon={ZapIcon} onClick={handleAutoImport} loading={busy}>
              一键自动导入
            </Button>
            <Button icon={LinkIcon} onClick={() => setShowLoginPicker(true)}>
              登录导入
            </Button>
            <Button icon={UploadIcon} onClick={() => setShowImport(true)}>
              手动导入
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
            <Empty icon={AccountsIcon} title="暂无账号" desc="点击「一键自动导入」读取浏览器登录态，或「新增账号」手动添加。" />
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
          <Field label="平台" required>
            <Select value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}>
              <option value="">请选择平台</option>
              {platforms.map((p) => (
                <option key={p.platform_id} value={p.platform_id}>
                  {p.display_name} ({p.platform_id})
                </option>
              ))}
            </Select>
          </Field>
          <Field label="邮箱 / 标识" required>
            <Input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </Field>
          <div className="flex flex-col gap-2">
            <span className="text-[12px] font-medium text-ink-2">
              凭据
              <span className="ml-0.5 text-func-rose">*</span>
              <span className="ml-1 text-[11px] font-normal text-ink-3">
                Session Key 与 Cookies 至少填一项
              </span>
            </span>
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
          </div>
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

      {/* 登录导入：选择平台后在受控浏览器打开官方登录页 */}
      <Modal
        open={showLoginPicker}
        title="登录导入"
        onClose={() => setShowLoginPicker(false)}
        width="440px"
      >
        <p className="mb-3 text-[12px] text-ink-3">
          选择平台后将在受控浏览器中打开其官方登录页；完成登录后返回点击「一键自动导入」即可写入账号池。
        </p>
        <div className="flex flex-col gap-1.5">
          {platforms.length === 0 ? (
            <Empty icon={LinkIcon} title="暂无可用平台" desc="请先在「模型」页确认平台清单。" />
          ) : (
            platforms.map((p) => (
              <button
                key={p.platform_id}
                onClick={() => handleOpenLogin(p.platform_id)}
                disabled={busy}
                className="flex items-center justify-between rounded-lg border border-line px-3 py-2 text-left
                  hover:border-brand-ink/40 hover:bg-surface-2 disabled:opacity-60"
              >
                <span className="text-[13px] text-ink">{p.display_name}</span>
                <span className="flex items-center gap-1 text-[11px] text-ink-3">
                  <LinkIcon size={12} />
                  打开登录页
                </span>
              </button>
            ))
          )}
        </div>
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
