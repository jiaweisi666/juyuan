/**
 * KeysPage.jsx - API 密钥管理页（核心功能）。
 *
 * 把网关聚合的各网页大模型（含 AUTO 智能路由）签发为 OpenAI / Anthropic
 * 兼容的 API Key，供第三方应用（如 Trae、各类 SDK 客户端）直接调用。
 */

import { useEffect, useMemo, useState } from 'react'
import {
  createApiKey,
  deleteApiKey,
  getApiKeys,
  getKeyMeta,
  revealApiKey,
  updateApiKey,
} from '../api.js'
import {
  KeyIcon,
  CopyIcon,
  TrashIcon,
  PlusIcon,
  CheckIcon,
  RefreshIcon,
  LinkIcon,
  ShieldIcon,
  AlertIcon,
  InfoIcon,
  ChevronDownIcon,
} from '../components/icons.jsx'
import { Button, Card, Empty, Field, Input, Modal, PageHeader, Pill, Spinner, Toggle } from '../components/ui.jsx'

const CODE_CLS =
  'rounded border border-line bg-surface-2 px-1.5 py-0.5 font-mono text-[11px] text-ink-2'

export default function KeysPage({ onToast }) {
  const [keys, setKeys] = useState([])
  const [meta, setMeta] = useState(null)
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [showCreate, setShowCreate] = useState(false)
  const [newSecret, setNewSecret] = useState(null)
  const [busy, setBusy] = useState({})

  async function load() {
    setLoading(true)
    try {
      const [k, m] = await Promise.all([getApiKeys(), getKeyMeta()])
      setKeys(k?.keys || [])
      setMeta(m)
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

  async function copyText(text, okMsg = '已复制到剪贴板') {
    try {
      await navigator.clipboard.writeText(text)
      onToast?.(okMsg, 'success')
    } catch {
      onToast?.('复制失败，请手动选择文本', 'error')
    }
  }

  async function handleCreate({ name, models }) {
    setCreating(true)
    try {
      const res = await createApiKey({ name, models })
      setShowCreate(false)
      setNewSecret({ secret: res.secret, name: res.key?.name })
      await load()
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setCreating(false)
    }
  }

  async function reveal(keyId) {
    setBusy((s) => ({ ...s, [keyId]: true }))
    try {
      const res = await revealApiKey(keyId)
      if (!res?.secret) {
        onToast?.('无法取回明文（可能已损坏）', 'error')
        return
      }
      await copyText(res.secret, '密钥已复制到剪贴板')
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setBusy((s) => ({ ...s, [keyId]: false }))
    }
  }

  async function toggleEnabled(item) {
    setBusy((s) => ({ ...s, [item.id]: true }))
    try {
      await updateApiKey(item.id, { enabled: !item.enabled })
      setKeys((prev) => prev.map((k) => (k.id === item.id ? { ...k, enabled: !k.enabled } : k)))
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setBusy((s) => ({ ...s, [item.id]: false }))
    }
  }

  async function remove(item) {
    setBusy((s) => ({ ...s, [item.id]: true }))
    try {
      await deleteApiKey(item.id)
      setKeys((prev) => prev.filter((k) => k.id !== item.id))
      onToast?.('密钥已删除', 'success')
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setBusy((s) => ({ ...s, [item.id]: false }))
    }
  }

  return (
    <div className="flex h-full flex-col px-5 py-4">
      <PageHeader
        title="API 密钥"
        desc="把聚合的网页大模型（含 AUTO 智能路由）签发为 API Key，供第三方应用以 OpenAI / Anthropic 协议调用。"
        actions={
          <>
            <Button icon={RefreshIcon} onClick={load} loading={loading}>
              刷新
            </Button>
            <Button variant="primary" icon={PlusIcon} onClick={() => setShowCreate(true)}>
              新建密钥
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
            {/* 密钥列表 */}
            <div>
              <SectionTitle icon={ShieldIcon}>已签发密钥（{keys.length}）</SectionTitle>
              <Card className="divide-y divide-line">
                {keys.length === 0 ? (
                  <Empty
                    icon={KeyIcon}
                    title="还没有 API 密钥"
                    desc="点击右上角「新建密钥」，选择要授权的模型后即可供 Trae 等第三方应用调用。"
                  />
                ) : (
                  keys.map((item) => (
                    <KeyRow
                      key={item.id}
                      item={item}
                      busy={!!busy[item.id]}
                      onCopy={copyText}
                      onReveal={reveal}
                      onToggle={toggleEnabled}
                      onDelete={remove}
                    />
                  ))
                )}
              </Card>
            </div>

            {/* 接入指南 */}
            <div>
              <SectionTitle icon={LinkIcon}>第三方接入</SectionTitle>
              <IntegrationCard meta={meta} onCopy={copyText} />
            </div>
          </div>
        )}
      </div>

      <CreateKeyModal
        open={showCreate}
        meta={meta}
        loading={creating}
        onClose={() => setShowCreate(false)}
        onSubmit={handleCreate}
      />

      <SecretModal
        open={!!newSecret}
        name={newSecret?.name}
        secret={newSecret?.secret || ''}
        onClose={() => setNewSecret(null)}
        onCopy={copyText}
      />
    </div>
  )
}

function KeyRow({ item, busy, onCopy, onReveal, onToggle, onDelete }) {
  const models = item.models || []
  return (
    <div className="flex flex-col gap-2 px-3 py-2.5">
      <div className="flex items-center gap-2">
        <KeyIcon size={15} className="shrink-0 text-brand" />
        <span className="text-[13px] font-medium text-ink">{item.name || '未命名密钥'}</span>
        <Pill tone={item.enabled ? 'emerald' : 'neutral'} dot>
          {item.enabled ? '启用中' : '已禁用'}
        </Pill>
        <div className="flex-1" />
        <span className="font-mono text-[11px] text-ink-3">{item.key_prefix}…</span>
      </div>

      <div className="flex items-center gap-2">
        <span className={CODE_CLS}>
          {models.length ? `${models.length} 个模型` : '全部模型（含 AUTO）'}
        </span>
        <span className="text-[11px] text-ink-3">调用 {item.usage_count || 0} 次</span>
        {item.last_used_at ? (
          <span className="text-[11px] text-ink-3">最近 {formatTime(item.last_used_at)}</span>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-1.5">
        <Button size="sm" variant="ghost" icon={CopyIcon} onClick={() => onReveal(item.id)} loading={busy}>
          复制密钥
        </Button>
        <Button size="sm" variant="ghost" icon={busy ? undefined : item.enabled ? AlertIcon : CheckIcon} onClick={() => onToggle(item)}>
          {item.enabled ? '禁用' : '启用'}
        </Button>
        <div className="flex-1" />
        <Toggle checked={item.enabled} onChange={() => onToggle(item)} disabled={busy} />
        <Button size="sm" variant="danger" icon={TrashIcon} onClick={() => onDelete(item)} disabled={busy}>
          删除
        </Button>
      </div>
    </div>
  )
}

function IntegrationCard({ meta, onCopy }) {
  const [expanded, setExpanded] = useState(false)
  const base = meta?.base_url || 'http://127.0.0.1:8300'
  const openaiBase = meta?.openai_base_url || `${base}/v1`
  const anthropicBase = meta?.anthropic_base_url || base

  const curl = `curl ${openaiBase}/chat/completions \\
  -H "Authorization: Bearer <你的密钥>" \\
  -H "Content-Type: application/json" \\
  -d '{
    "model": "deepseek-chat",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true
  }'`

  return (
    <Card className="flex flex-col gap-3 p-3">
      <p className="text-[12px] text-ink-2">
        任意兼容 OpenAI 或 Anthropic 协议的应用（Trae、Cursor、Claude Code、各类 SDK）都可把接口地址指向本网关。
        第三方既能直连官方 API，也能通过本网关使用网页大模型。
      </p>
      <div className="grid grid-cols-2 gap-3">
        <Field label="OpenAI 兼容 Base URL">
          <CopyableRow value={openaiBase} onCopy={onCopy} />
        </Field>
        <Field label="Anthropic 兼容 Base URL">
          <CopyableRow value={anthropicBase} onCopy={onCopy} />
        </Field>
      </div>
      <Field label="调用示例（model 可填 deepseek-chat / deepseek-reasoner 等）">
        <pre className="overflow-x-auto rounded-md border border-line bg-surface-2 px-3 py-2 font-mono text-[11px] leading-relaxed text-ink-2">
          {curl}
        </pre>
      </Field>

      {/* 折叠展开：小白详细指南 */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1 self-start rounded-md bg-brand-soft/50 px-2 py-1 text-[12px] font-medium text-brand transition-colors hover:bg-brand-soft"
      >
        <span>{expanded ? '收起' : '展开'} 详细使用指南</span>
        <span className={`transition-transform ${expanded ? 'rotate-180' : ''}`}>
          <ChevronDownIcon size={14} />
        </span>
      </button>

      {expanded && (
        <div className="flex flex-col gap-3 rounded-md bg-surface-2/60 p-3 text-[12px] leading-relaxed text-ink-2">
          <div>
            <span className="font-semibold text-ink">1. API Key 是什么？</span>
            <p className="mt-0.5">
              API Key 是一把「钥匙」。第三方应用（如 Trae、Cursor）需要它才能调用本网关。你先在上方「新建密钥」生成一把，复制后填到第三方应用里即可。
            </p>
          </div>
          <div>
            <span className="font-semibold text-ink">2. Base URL 是什么？</span>
            <p className="mt-0.5">
              Base URL 是「接口地址」。告诉第三方应用「去哪里找网关」。默认是 <code className="rounded bg-surface px-1 py-0.5 font-mono text-[11px]">{openaiBase}</code>，通常只需复制粘贴到第三方应用的「OpenAI Base URL」或「API 地址」一栏。
            </p>
          </div>
          <div>
            <span className="font-semibold text-ink">3. 模型怎么填？</span>
            <p className="mt-0.5">
              在第三方应用的「模型」一栏，填写本网关支持的模型名即可，例如：
            </p>
            <ul className="mt-1 list-inside list-disc space-y-0.5 pl-1">
              <li><code className="rounded bg-surface px-1 py-0.5 font-mono text-[11px]">deepseek-chat</code> — 标准对话模式</li>
              <li><code className="rounded bg-surface px-1 py-0.5 font-mono text-[11px]">deepseek-reasoner</code> — 深度思考模式</li>
              <li><code className="rounded bg-surface px-1 py-0.5 font-mono text-[11px]">deepseek-chat-online</code> — 在线搜索模式</li>
              <li><code className="rounded bg-surface px-1 py-0.5 font-mono text-[11px]">deepseek-reasoner-online</code> — 深度思考 + 在线</li>
            </ul>
          </div>
          <div>
            <span className="font-semibold text-ink">4. 以 Trae 为例的配置步骤</span>
            <p className="mt-0.5">
              打开 Trae → 设置 → 模型提供方 → 选择「OpenAI 兼容」→ Base URL 填 <code className="rounded bg-surface px-1 py-0.5 font-mono text-[11px]">{openaiBase}</code> → API Key 填你从本网关复制的密钥 → 模型填 <code className="rounded bg-surface px-1 py-0.5 font-mono text-[11px]">deepseek-chat</code> → 保存即可开始使用。
            </p>
          </div>
          <div>
            <span className="font-semibold text-ink">5. 注意事项</span>
            <p className="mt-0.5">
              网关和第三方应用必须在同一台电脑运行（默认只监听 127.0.0.1）。如果第三方应用报「连接失败」，请检查网关是否已启动（看左下角绿灯）。
            </p>
          </div>
        </div>
      )}
    </Card>
  )
}

function CopyableRow({ value, onCopy }) {
  return (
    <div className="flex items-center gap-2">
      <code className="min-w-0 flex-1 truncate rounded-md border border-line bg-surface-2 px-2 py-1.5 font-mono text-[12px] text-ink-2">
        {value}
      </code>
      <Button size="sm" variant="ghost" icon={CopyIcon} onClick={() => onCopy(value, '已复制地址')} />
    </div>
  )
}

function CreateKeyModal({ open, meta, loading, onClose, onSubmit }) {
  const [name, setName] = useState('')
  const [selected, setSelected] = useState([])

  useEffect(() => {
    if (open) {
      setName('')
      setSelected([])
    }
  }, [open])

  const models = meta?.models || []
  const grouped = useMemo(() => {
    const map = {}
    for (const m of models) {
      const key = m.owned_by || 'juyuan'
      ;(map[key] = map[key] || []).push(m.id)
    }
    return map
  }, [models])

  function toggleModel(id) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((m) => m !== id) : [...prev, id]))
  }

  return (
    <Modal
      open={open}
      title="新建 API 密钥"
      width="520px"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button variant="primary" icon={CheckIcon} loading={loading} onClick={() => onSubmit({ name, models: selected })}>
            生成密钥
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <Field label="名称" hint="用于区分不同应用或环境，例如 Trae 桌面端">
          <Input value={name} placeholder="未命名密钥" onChange={(e) => setName(e.target.value)} />
        </Field>

        <div className="flex items-center justify-between">
          <span className="text-[12px] font-medium text-ink-2">
            模型授权{selected.length ? `（已选 ${selected.length}）` : '（默认全部）'}
          </span>
          <div className="flex gap-2">
            <button
              className="text-[11px] text-brand hover:underline"
              onClick={() => setSelected(models.map((m) => m.id))}
            >
              全选
            </button>
            <button className="text-[11px] text-ink-3 hover:underline" onClick={() => setSelected([])}>
              清空
            </button>
          </div>
        </div>

        <div className="max-h-[260px] overflow-y-auto rounded-md border border-line">
          {Object.entries(grouped).map(([owner, ids]) => (
            <div key={owner} className="border-b border-line px-3 py-2 last:border-b-0">
              <div className="mb-1 text-[11px] font-medium text-ink-3">{owner}</div>
              <div className="flex flex-wrap gap-1.5">
                {ids.map((id) => {
                  const active = selected.includes(id)
                  return (
                    <button
                      key={id}
                      onClick={() => toggleModel(id)}
                      className={`rounded-md border px-2 py-0.5 font-mono text-[11px] transition-colors ${
                        active
                          ? 'border-brand bg-brand-soft text-brand-ink'
                          : 'border-line bg-surface-2 text-ink-2 hover:border-line-strong'
                      }`}
                    >
                      {id}
                    </button>
                  )
                })}
              </div>
            </div>
          ))}
        </div>

        <div className="flex items-start gap-1.5 text-[11px] text-ink-3">
          <InfoIcon size={13} className="mt-0.5 shrink-0" />
          不选择任何模型表示授予「全部模型」权限（含 AUTO 智能路由）。选择后仅可调用所选模型。
        </div>
      </div>
    </Modal>
  )
}

function SecretModal({ open, name, secret, onClose, onCopy }) {
  return (
    <Modal
      open={open}
      title="密钥已生成"
      width="520px"
      onClose={onClose}
      footer={
        <>
          <Button icon={CopyIcon} onClick={() => onCopy(secret, '密钥已复制')}>
            复制密钥
          </Button>
          <Button variant="primary" icon={CheckIcon} onClick={onClose}>
            我已保存
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <div className="flex items-start gap-2 rounded-md bg-func-orange-soft px-3 py-2 text-[12px] text-func-orange">
          <AlertIcon size={15} className="mt-0.5 shrink-0" />
          <span>请立即复制并妥善保存，密钥不会再次完整显示（仍可在列表中重新取回）。</span>
        </div>
        {name ? <div className="text-[12px] text-ink-3">名称：{name}</div> : null}
        <code className="break-all rounded-md border border-line bg-surface-2 px-3 py-2 font-mono text-[12px] text-ink">
          {secret}
        </code>
      </div>
    </Modal>
  )
}

function SectionTitle({ icon: Icon, children }) {
  return (
    <div className="mb-2 flex items-center gap-1.5 text-[13px] font-medium text-ink-2">
      <Icon size={14} className="text-ink-3" />
      {children}
    </div>
  )
}

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
