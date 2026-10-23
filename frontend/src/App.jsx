/**
 * App.jsx - 应用外壳。
 *
 * 浅色云白底 + 聚元蓝；左侧品牌标签栏，右侧内容区。
 * 底部提供网关连接设置（baseUrl / API Key / 管理令牌），右上角为全局提示。
 */

import { useEffect, useState } from 'react'
import ChatPage from './pages/ChatPage.jsx'
import SetupPage from './pages/SetupPage.jsx'
import KeysPage from './pages/KeysPage.jsx'
import { getClientConfig, getGatewayInfo, saveClientConfig } from './api.js'
import {
  ChatIcon,
  SetupIcon,
  KeyIcon,
  SettingsIcon,
  CheckIcon,
  AlertIcon,
  InfoIcon,
} from './components/icons.jsx'
import { Button, Field, Input, Modal, Pill } from './components/ui.jsx'

const TABS = [
  { id: 'chat', label: '对话', icon: ChatIcon },
  { id: 'keys', label: 'API', icon: KeyIcon },
  { id: 'setup', label: '配置', icon: SetupIcon },
]

export default function App() {
  const [tab, setTab] = useState('chat')
  const [chatResetKey, setChatResetKey] = useState(0)
  const [toasts, setToasts] = useState([])
  const [showSettings, setShowSettings] = useState(false)
  const [gateway, setGateway] = useState(null)
  const [online, setOnline] = useState(null)

  useEffect(() => {
    getGatewayInfo()
      .then((info) => {
        setGateway(info)
        setOnline(true)
      })
      .catch(() => setOnline(false))
  }, [])

  function toast(message, tone = 'info') {
    const id = Math.random().toString(36).slice(2)
    setToasts((prev) => [...prev, { id, message, tone }])
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3600)
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-canvas">
      <div className="app-window app-shell relative flex overflow-hidden">
        {/* 左侧品牌标签栏 */}
        <nav className="relative z-10 flex w-[78px] shrink-0 flex-col items-center border-r border-white/70 bg-white/65 py-4 shadow-[1px_0_0_rgba(214,228,247,0.65)] backdrop-blur-xl">
          {/* 品牌 Logo */}
          <button
            onClick={() => {
              setTab('chat')
              setChatResetKey((k) => k + 1)
            }}
            title="聚元 · 返回对话"
            className="brand-mark flex size-12 items-center justify-center overflow-hidden rounded-2xl border border-white/90 bg-white"
          >
            <img
              src="./juyuan-logo.png"
              alt="聚元"
              className="size-11 object-contain"
              draggable="false"
            />
          </button>
          <div className="mb-5 mt-1.5 text-[10px] font-semibold tracking-[0.22em] text-brand-ink/75">
            聚元
          </div>

          <div className="flex flex-1 flex-col items-center gap-2">
            {TABS.map((t) => {
              const Icon = t.icon
              const active = tab === t.id
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  title={t.label}
                  data-active={active}
                  className="nav-item flex w-[58px] flex-col items-center gap-1 rounded-xl py-2.5 text-ink-3"
                >
                  <Icon size={19} className={active ? 'text-brand-ink' : ''} />
                  <span className="text-[10px] font-medium">{t.label}</span>
                </button>
              )
            })}
          </div>

          <button
            onClick={() => setShowSettings(true)}
            title="连接设置"
            className="ui-press flex w-[58px] flex-col items-center gap-1 rounded-xl py-2.5 text-ink-3 transition-colors hover:bg-white hover:text-ink-2"
          >
            <SettingsIcon size={19} />
            <span className="text-[10px] font-medium">设置</span>
          </button>

          <div
            className="mt-3 flex flex-col items-center gap-1 rounded-full bg-white/80 px-2 py-1.5 shadow-[0_1px_2px_rgba(18,54,105,0.04)]"
            title={online ? '网关在线' : '网关离线'}
          >
            <span
              className={`block size-2 rounded-full ${
                online === null
                  ? 'bg-ink-3'
                  : online
                    ? 'bg-func-emerald animate-pulse-dot'
                    : 'bg-func-rose animate-pulse-dot'
              }`}
            />
            <span className="text-[9px] font-medium leading-none text-ink-3">
              {online === null ? '检测' : online ? '在线' : '离线'}
            </span>
          </div>
        </nav>

        {/* 内容区 */}
        <main className="relative flex min-w-0 flex-1 flex-col bg-transparent">
          <div key={tab} className="fade-in flex min-h-0 flex-1 flex-col">
            {tab === 'chat' && <ChatPage onToast={toast} resetKey={chatResetKey} />}
            {tab === 'keys' && <KeysPage onToast={toast} />}
            {tab === 'setup' && <SetupPage onToast={toast} />}
          </div>
        </main>

        {/* 全局提示 */}
        <div className="pointer-events-none absolute right-4 top-4 z-40 flex w-[330px] flex-col gap-2">
          {toasts.map((t) => (
            <Toast key={t.id} {...t} />
          ))}
        </div>

        {/* 连接设置 */}
        <SettingsModal
          open={showSettings}
          gateway={gateway}
          online={online}
          onClose={() => setShowSettings(false)}
          onSaved={(cfg) => {
            toast('连接设置已保存', 'success')
            getGatewayInfo()
              .then((info) => {
                setGateway(info)
                setOnline(true)
              })
              .catch(() => setOnline(false))
            return cfg
          }}
        />
      </div>
    </div>
  )
}

function Toast({ message, tone }) {
  const map = {
    info: { cls: 'border-brand/10 bg-white/95 text-ink-2', iconCls: 'bg-brand-soft text-brand-ink', Icon: InfoIcon },
    success: {
      cls: 'border-func-emerald/15 bg-white/95 text-ink-2',
      iconCls: 'bg-func-emerald-soft text-func-emerald',
      Icon: CheckIcon,
    },
    error: {
      cls: 'border-func-rose/15 bg-white/95 text-ink-2',
      iconCls: 'bg-func-rose-soft text-func-rose',
      Icon: AlertIcon,
    },
  }
  const { cls, iconCls, Icon } = map[tone] || map.info
  return (
    <div
      className={`toast-in pointer-events-auto flex items-start gap-2.5 rounded-xl border px-3 py-2.5 text-[12px] shadow-[0_18px_40px_-22px_rgba(18,54,105,0.35)] backdrop-blur-xl ${cls}`}
    >
      <span className={`mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-lg ${iconCls}`}>
        <Icon size={14} />
      </span>
      <span className="flex-1 break-words leading-relaxed">{message}</span>
    </div>
  )
}

function SettingsModal({ open, gateway, online, onClose, onSaved }) {
  const [form, setForm] = useState(getClientConfig())

  useEffect(() => {
    if (open) setForm(getClientConfig())
  }, [open])

  function save() {
    saveClientConfig(form)
    onSaved?.(form)
    onClose()
  }

  return (
    <Modal
      open={open}
      title="网关连接设置"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button variant="primary" icon={CheckIcon} onClick={save}>
            保存
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-3">
        <div className="flex items-center gap-2.5 rounded-xl border border-line/70 bg-surface-2/70 px-3 py-2.5">
          <span className="flex size-9 items-center justify-center rounded-xl bg-white shadow-sm">
            <img src="./juyuan-logo.png" alt="" className="size-8 object-contain" />
          </span>
          <div className="min-w-0 flex-1">
            <div className="text-[12px] font-medium text-ink">
              {online ? `已连接网关 v${gateway?.version || '-'}` : '未连接到网关'}
            </div>
            <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-ink-3">
              <span
                className={`size-1.5 rounded-full ${online ? 'bg-func-emerald' : 'bg-func-rose'}`}
              />
              {gateway?.host || '127.0.0.1'}:{gateway?.port || '8300'}
            </div>
          </div>
          {gateway ? (
            <Pill tone={gateway.real_browser_enabled ? 'emerald' : 'orange'}>
              {gateway.real_browser_enabled ? '真实浏览器' : '模拟适配器'}
            </Pill>
          ) : null}
        </div>
        <Field label="网关地址" hint="留空表示同源（由 Vite 代理或后端托管）">
          <Input
            value={form.baseUrl}
            placeholder="http://127.0.0.1:8300"
            onChange={(e) => setForm({ ...form, baseUrl: e.target.value })}
          />
        </Field>
        <Field label="API Key" hint="对应 GATEWAY_API_KEY，用于 /v1/* 与 /api/* 鉴权">
          <Input
            type="password"
            value={form.apiKey}
            placeholder="留空表示未启用"
            onChange={(e) => setForm({ ...form, apiKey: e.target.value })}
          />
        </Field>
        <Field label="管理令牌" hint="对应 GATEWAY_ADMIN_TOKEN">
          <Input
            type="password"
            value={form.adminToken}
            placeholder="留空表示未启用"
            onChange={(e) => setForm({ ...form, adminToken: e.target.value })}
          />
        </Field>
      </div>
    </Modal>
  )
}
