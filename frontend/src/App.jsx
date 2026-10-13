/**
 * App.jsx - 应用外壳。
 *
 * 880×580 桌面窗口（16:10），左侧 64px 图标标签栏，右侧内容区。
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
  CloseIcon,
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
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 3200)
  }

  return (
    <div className="flex h-screen w-full overflow-hidden bg-canvas">
      <div className="app-window relative flex overflow-hidden bg-surface">
        {/* 左侧图标标签栏 */}
        <nav className="flex w-[64px] shrink-0 flex-col items-center border-r border-line bg-surface-2/70 py-3">
          {/* 品牌 Logo */}
          <button
            onClick={() => {
              setTab('chat')
              setChatResetKey((k) => k + 1)
            }}
            title="聚元"
            className="mb-3 flex size-9 items-center justify-center overflow-hidden rounded-xl border border-line bg-surface shadow-sm transition-transform hover:scale-105"
          >
            <span className="text-sm font-bold text-brand">聚元</span>
          </button>
          <div className="flex flex-1 flex-col items-center gap-1">
            {TABS.map((t) => {
              const Icon = t.icon
              const active = tab === t.id
              return (
                <button
                  key={t.id}
                  onClick={() => setTab(t.id)}
                  title={t.label}
                  className={`flex w-[52px] flex-col items-center gap-1 rounded-lg py-2 transition-colors
                    ${active ? 'bg-brand-soft text-brand-ink' : 'text-ink-3 hover:bg-surface hover:text-ink-2'}`}
                >
                  <Icon size={19} />
                  <span className="text-[10px] font-medium">{t.label}</span>
                </button>
              )
            })}
          </div>
          <button
            onClick={() => setShowSettings(true)}
            title="连接设置"
            className="flex w-[52px] flex-col items-center gap-1 rounded-lg py-2 text-ink-3 transition-colors hover:bg-surface hover:text-ink-2"
          >
            <SettingsIcon size={19} />
            <span className="text-[10px] font-medium">设置</span>
          </button>
          <div className="mt-2" title={online ? '网关在线' : '网关离线'}>
            <span
              className={`block size-2 rounded-full ${online === null ? 'bg-ink-3' : online ? 'bg-func-emerald' : 'bg-func-rose'} ${online ? '' : 'animate-pulse-dot'}`}
            />
          </div>
        </nav>

        {/* 内容区 */}
        <main className="flex min-w-0 flex-1 flex-col bg-canvas">
          <div key={tab} className="fade-in flex min-h-0 flex-1 flex-col">
            {tab === 'chat' && <ChatPage onToast={toast} resetKey={chatResetKey} />}
            {tab === 'keys' && <KeysPage onToast={toast} />}
            {tab === 'setup' && <SetupPage onToast={toast} />}
          </div>
        </main>

        {/* 全局提示 */}
        <div className="pointer-events-none absolute right-3 top-3 z-40 flex w-[300px] flex-col gap-2">
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
    info: { cls: 'border-line bg-surface text-ink-2', Icon: InfoIcon },
    success: { cls: 'border-transparent bg-func-emerald-soft text-func-emerald', Icon: CheckIcon },
    error: { cls: 'border-transparent bg-func-rose-soft text-func-rose', Icon: AlertIcon },
  }
  const { cls, Icon } = map[tone] || map.info
  return (
    <div className={`pointer-events-auto flex items-start gap-2 rounded-lg border px-3 py-2 text-[12px] ${cls}`}>
      <Icon size={15} className="mt-0.5 shrink-0" />
      <span className="flex-1 break-words">{message}</span>
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
        <div className="flex items-center gap-2 rounded-md bg-surface-2 px-3 py-2">
          <span className={`size-2 rounded-full ${online ? 'bg-func-emerald' : 'bg-func-rose'}`} />
          <span className="text-[12px] text-ink-2">
            {online ? `已连接网关 v${gateway?.version || '-'}` : '未连接到网关'}
          </span>
          {gateway ? (
            <Pill tone={gateway.real_browser_enabled ? 'emerald' : 'orange'} className="ml-auto">
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
