/**
 * ChatPage.jsx - 统一对话窗口（首页）。
 *
 * 左：会话历史列表；右：消息流 + 输入区 + 模型选择 + 路由说明。
 * 流式响应通过 SSE 逐字渲染，可随时中断。
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  createConversation,
  deleteConversation,
  getConversation,
  getModels,
  listConversations,
  sendChatStream,
} from '../api.js'
import {
  ChatIcon,
  PlusIcon,
  SendIcon,
  StopIcon,
  TrashIcon,
  HistoryIcon,
  ZapIcon,
  CheckIcon,
  CopyIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '../components/icons.jsx'
import { Button, Empty, Pill, Spinner, Textarea } from '../components/ui.jsx'

const MODEL_LABELS = {
  'deepseek-chat': 'chat',
  'deepseek-reasoner': 'reasoner',
  'deepseek-chat-online': 'chat-online',
  'deepseek-reasoner-online': 'reasoner-online',
}

const DEFAULT_MODELS = Object.keys(MODEL_LABELS)

export default function ChatPage({ onToast, resetKey }) {
  const [models, setModels] = useState(DEFAULT_MODELS)
  const [model, setModel] = useState('deepseek-chat')
  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [messages, setMessages] = useState([])
  const [route, setRoute] = useState(null)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [loadingConv, setLoadingConv] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)

  const abortRef = useRef(null)
  const scrollRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    // 固定仅展示 DeepSeek 4 个模型选项
    setModels(DEFAULT_MODELS)
    refreshConversations()
  }, [])

  useEffect(() => {
    if (resetKey > 0) newConversation()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resetKey])

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [messages, streaming])

  async function refreshConversations() {
    try {
      const res = await listConversations()
      setConversations(res?.conversations || [])
    } catch {
      /* 忽略 */
    }
  }

  async function openConversation(id) {
    if (streaming) return
    setActiveId(id)
    setRoute(null)
    setLoadingConv(true)
    try {
      const data = await getConversation(id)
      setMessages(data?.messages || [])
      if (data?.model) setModel(data.model)
    } catch (err) {
      onToast?.(err.message, 'error')
    } finally {
      setLoadingConv(false)
    }
  }

  function newConversation() {
    if (streaming) return
    setActiveId(null)
    setMessages([])
    setRoute(null)
    setInput('')
    textareaRef.current?.focus()
  }

  async function removeConversation(e, id) {
    e.stopPropagation()
    try {
      await deleteConversation(id)
      if (id === activeId) newConversation()
      refreshConversations()
    } catch (err) {
      onToast?.(err.message, 'error')
    }
  }

  function stopStream() {
    abortRef.current?.abort()
    abortRef.current = null
    setStreaming(false)
  }

  async function send() {
    const content = input.trim()
    if (!content || streaming) return

    let convId = activeId
    if (!convId) {
      try {
        const res = await createConversation(content.slice(0, 24) || '新对话', model)
        convId = res?.id || null
        setActiveId(convId)
      } catch (err) {
        onToast?.(err.message, 'error')
        return
      }
    }

    setMessages((prev) => [
      ...prev,
      { role: 'user', content },
      { role: 'assistant', content: '', streaming: true },
    ])
    setInput('')
    setStreaming(true)
    setRoute(null)

    abortRef.current = sendChatStream(
      { conversation_id: convId, model, content },
      (evt) => {
        if (evt.route) setRoute(evt.route)
        if (evt.delta) {
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last && last.role === 'assistant') {
              next[next.length - 1] = { ...last, content: last.content + evt.delta }
            }
            return next
          })
        }
        if (evt.done) {
          setStreaming(false)
          abortRef.current = null
          setMessages((prev) => {
            const next = [...prev]
            const last = next[next.length - 1]
            if (last && last.streaming) next[next.length - 1] = { ...last, streaming: false }
            return next
          })
          refreshConversations()
        }
      },
      (err) => {
        setStreaming(false)
        abortRef.current = null
        onToast?.(err.message, 'error')
      },
    )
  }

  function onKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault()
      send()
    }
  }

  const modelOptions = useMemo(
    () => models.filter((m) => m !== 'auto'),
    [models],
  )

  const InputBox = (
    <div className="mx-auto flex w-full max-w-[640px] items-end gap-2">
      <Textarea
        ref={textareaRef}
        rows={2}
        value={input}
        placeholder="输入消息，Enter 发送，Shift+Enter 换行"
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={onKeyDown}
        disabled={streaming}
        className="max-h-[120px] flex-1"
      />
      {streaming ? (
        <Button variant="danger" size="lg" icon={StopIcon} onClick={stopStream}>
          停止
        </Button>
      ) : (
        <Button
          variant="primary"
          size="lg"
          icon={SendIcon}
          onClick={send}
          disabled={!input.trim()}
        >
          发送
        </Button>
      )}
    </div>
  )

  return (
    <div className="flex h-full">
      {/* 会话历史 */}
      {!sidebarCollapsed ? (
        <aside className="flex w-[212px] shrink-0 flex-col border-r border-line bg-surface-2/60">
          <div className="flex items-center justify-between px-3 py-2.5">
            <span className="flex items-center gap-1.5 text-[12px] font-medium text-ink-2">
              <HistoryIcon size={14} /> 会话历史
            </span>
            <div className="flex items-center gap-0.5">
              <button
                onClick={newConversation}
                className="rounded-md p-1 text-ink-3 transition-colors hover:bg-surface hover:text-brand"
                title="新建对话"
              >
                <PlusIcon size={16} />
              </button>
              <button
                onClick={() => setSidebarCollapsed(true)}
                className="rounded-md p-1 text-ink-3 transition-colors hover:bg-surface hover:text-ink-2"
                title="收起"
              >
                <ChevronLeftIcon size={16} />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-2 pb-2">
            {conversations.length === 0 ? (
              <p className="px-2 py-4 text-[12px] text-ink-3">暂无会话，开始新的对话吧。</p>
            ) : (
              conversations.map((c) => (
                <div
                  key={c.id}
                  onClick={() => openConversation(c.id)}
                  className={`group mb-0.5 flex cursor-pointer items-center gap-1 rounded-md px-2 py-1.5
                    transition-colors ${
                      c.id === activeId ? 'bg-brand-soft text-brand-ink' : 'text-ink-2 hover:bg-surface'
                    }`}
                >
                  <ChatIcon size={13} className="shrink-0 opacity-70" />
                  <span className="min-w-0 flex-1 truncate text-[12px]">{c.title || '未命名会话'}</span>
                  <button
                    onClick={(e) => removeConversation(e, c.id)}
                    className="shrink-0 text-ink-3 opacity-0 transition-opacity hover:text-func-rose group-hover:opacity-100"
                  >
                    <TrashIcon size={13} />
                  </button>
                </div>
              ))
            )}
          </div>
        </aside>
      ) : (
        <button
          onClick={() => setSidebarCollapsed(false)}
          className="flex h-full w-7 shrink-0 items-center justify-center border-r border-line bg-surface-2/40 text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink-2"
          title="展开会话历史"
        >
          <ChevronRightIcon size={14} />
        </button>
      )}

      {/* 对话主区 */}
      <section className="flex min-w-0 flex-1 flex-col">
        {/* 顶部：模型选择 + 路由说明 */}
        <div className="flex items-center gap-2 border-b border-line px-4 py-2.5">
          <ZapIcon size={15} className="text-brand" />
          <select
            value={model}
            onChange={(e) => setModel(e.target.value)}
            disabled={streaming}
            className="h-7 cursor-pointer rounded-md border border-line bg-surface px-2 text-[12px] text-ink
              outline-none transition-colors hover:border-line-strong focus:border-brand"
          >
            {modelOptions.map((m) => (
              <option key={m} value={m}>
                {MODEL_LABELS[m] || m}
              </option>
            ))}
          </select>
          {route ? <RouteBadge route={route} /> : null}
          <div className="flex-1" />
          <span className="rounded-md bg-func-orange-soft px-2 py-0.5 text-[11px] text-func-orange">
            仅用于测试
          </span>
          <Button variant="ghost" size="sm" icon={PlusIcon} onClick={newConversation} disabled={streaming}>
            新对话
          </Button>
        </div>

        {/* 消息流 */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {loadingConv ? (
            <div className="flex h-full items-center justify-center">
              <Spinner size={20} />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-6 px-4 pb-12">
              <div className="flex flex-col items-center gap-3">
                <h2 className="text-xl font-semibold tracking-wide text-ink">
                  聚元汇智，通达四方
                </h2>
                <p className="text-[13px] text-ink-3">
                  当前接入 DeepSeek 网页版：chat、reasoner、chat-online、reasoner-online 四种模式。
                </p>
              </div>
              <div className="w-full max-w-[640px] rounded-xl border border-line bg-surface px-4 py-3 shadow-sm">
                {InputBox}
              </div>
            </div>
          ) : (
            <div className="mx-auto flex max-w-[620px] flex-col gap-4 px-4 py-3">
              {messages.map((m, i) => (
                <div key={i} className="message-in">
                  <MessageBubble message={m} />
                </div>
              ))}
            </div>
          )}
        </div>

        {/* 输入区（有消息时显示在底部） */}
        {messages.length > 0 && (
          <div className="border-t border-line px-4 py-3">
            {InputBox}
          </div>
        )}
      </section>
    </div>
  )
}

function RouteBadge({ route }) {
  const label = route.auto ? 'AUTO' : '手动'
  return (
    <Pill tone={route.auto ? 'brand' : 'neutral'} title={route.reason}>
      {label} · {route.platform}
      {route.variant && route.variant !== 'default' ? `:${route.variant}` : ''}
      {typeof route.score === 'number' ? ` · ${route.score.toFixed(2)}` : ''}
    </Pill>
  )
}

function MessageBubble({ message }) {
  const [copied, setCopied] = useState(false)
  const isUser = message.role === 'user'

  function copy() {
    navigator.clipboard?.writeText(message.content || '')
    setCopied(true)
    setTimeout(() => setCopied(false), 1200)
  }

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-lg bg-brand-soft px-3 py-2 text-[13px] text-ink">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="md text-ink">
        {message.content ? (
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
        ) : message.streaming ? (
          <span className="caret" />
        ) : (
          <span className="text-ink-3">（空响应）</span>
        )}
      </div>
      {!message.streaming && message.content ? (
        <div className="flex items-center gap-1 text-ink-3">
          <button onClick={copy} className="rounded p-1 hover:text-ink-2" title="复制">
            {copied ? <CheckIcon size={13} /> : <CopyIcon size={13} />}
          </button>
        </div>
      ) : null}
    </div>
  )
}
