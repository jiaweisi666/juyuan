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
  ChevronDownIcon,
  SparklesIcon,
} from '../components/icons.jsx'
import { Button, Pill, Spinner } from '../components/ui.jsx'

const MODEL_LABELS = {
  'deepseek-chat': 'DeepSeek Chat',
  'deepseek-reasoner': 'DeepSeek Reasoner',
  'deepseek-chat-online': 'DeepSeek Chat · 联网',
  'deepseek-reasoner-online': 'DeepSeek Reasoner · 联网',
}

const DEFAULT_MODELS = Object.keys(MODEL_LABELS)

const SUGGESTIONS = [
  { title: '解释一个概念', prompt: '用通俗易懂的方式解释一下什么是「向量数据库」' },
  { title: '改写一段文字', prompt: '帮我润色下面这段话，让它更简洁专业：' },
  { title: '写一段代码', prompt: '用 Python 写一个读取 CSV 并统计缺失值的脚本' },
  { title: '制定一个计划', prompt: '帮我制定一份为期 7 天的 Python 入门学习计划' },
]

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

  function useSuggestion(prompt) {
    setInput(prompt)
    textareaRef.current?.focus()
  }

  const modelOptions = useMemo(() => models.filter((m) => m !== 'auto'), [models])

  const InputBox = (
    <div className="mx-auto w-full max-w-[720px]">
      <div className="group flex items-end gap-2 rounded-2xl border border-line/90 bg-white/90 p-2 pl-3 shadow-[0_10px_36px_-24px_rgba(18,54,105,0.35)] backdrop-blur-xl transition-all focus-within:border-brand/45 focus-within:shadow-[0_14px_44px_-22px_rgba(47,134,246,0.45)]">
        <textarea
          ref={textareaRef}
          rows={2}
          value={input}
          placeholder="输入消息，Enter 发送，Shift + Enter 换行"
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          disabled={streaming}
          className="max-h-[140px] min-h-[44px] flex-1 resize-none border-0 bg-transparent px-1 py-1.5 text-[13px] leading-relaxed text-ink outline-none placeholder:text-ink-3 disabled:opacity-60"
        />
        {streaming ? (
          <Button variant="danger" size="lg" icon={StopIcon} onClick={stopStream} className="shrink-0">
            停止
          </Button>
        ) : (
          <button
            onClick={send}
            disabled={!input.trim()}
            title="发送"
            className="ui-press flex size-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#4a9bff] via-brand to-[#1769e0] text-white shadow-[0_8px_18px_-8px_rgba(47,134,246,0.8)] transition-all hover:-translate-y-px hover:shadow-[0_12px_24px_-8px_rgba(47,134,246,0.85)] disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:translate-y-0"
          >
            <SendIcon size={18} />
          </button>
        )}
      </div>
      <div className="mt-1.5 flex items-center justify-between px-1 text-[10px] text-ink-3">
        <span className="flex items-center gap-1">
          <SparklesIcon size={11} className="text-brand/70" />
          聚元统一对话 · 当前接入 DeepSeek 网页版
        </span>
        <span>{input.length > 0 ? `${input.length} 字` : 'Enter 发送'}</span>
      </div>
    </div>
  )

  return (
    <div className="flex h-full">
      {/* 会话历史 */}
      {!sidebarCollapsed ? (
        <aside className="flex w-[224px] shrink-0 flex-col border-r border-white/70 bg-white/45 backdrop-blur-xl">
          <div className="flex items-center justify-between px-3.5 py-3">
            <span className="flex items-center gap-1.5 text-[12px] font-medium text-ink-2">
              <HistoryIcon size={14} className="text-brand/80" /> 会话历史
            </span>
            <div className="flex items-center gap-0.5">
              <button
                onClick={newConversation}
                className="ui-press rounded-lg p-1.5 text-ink-3 transition-colors hover:bg-brand-soft hover:text-brand-ink"
                title="新建对话"
              >
                <PlusIcon size={16} />
              </button>
              <button
                onClick={() => setSidebarCollapsed(true)}
                className="ui-press rounded-lg p-1.5 text-ink-3 transition-colors hover:bg-white hover:text-ink-2"
                title="收起"
              >
                <ChevronLeftIcon size={16} />
              </button>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto px-2 pb-2">
            {conversations.length === 0 ? (
              <div className="mx-1 mt-2 rounded-xl border border-dashed border-line/90 bg-white/50 px-3 py-5 text-center text-[12px] leading-relaxed text-ink-3">
                暂无会话
                <br />
                在右侧开始新的对话吧
              </div>
            ) : (
              conversations.map((c) => (
                <div
                  key={c.id}
                  onClick={() => openConversation(c.id)}
                  className={`group mb-1 flex cursor-pointer items-center gap-1.5 rounded-xl px-2.5 py-2 transition-all ${
                    c.id === activeId
                      ? 'bg-white text-brand-ink shadow-[0_4px_14px_-10px_rgba(18,54,105,0.4)] ring-1 ring-brand/10'
                      : 'text-ink-2 hover:bg-white/80 hover:text-ink'
                  }`}
                >
                  <ChatIcon
                    size={13}
                    className={`shrink-0 ${c.id === activeId ? 'text-brand' : 'opacity-60'}`}
                  />
                  <span className="min-w-0 flex-1 truncate text-[12px]">{c.title || '未命名会话'}</span>
                  <button
                    onClick={(e) => removeConversation(e, c.id)}
                    className="shrink-0 rounded p-0.5 text-ink-3 opacity-0 transition-opacity hover:bg-func-rose-soft hover:text-func-rose group-hover:opacity-100"
                    title="删除会话"
                  >
                    <TrashIcon size={13} />
                  </button>
                </div>
              ))
            )}
          </div>
          <div className="m-2 rounded-xl border border-line/60 bg-white/55 px-3 py-2.5">
            <div className="flex items-center gap-1.5 text-[11px] font-medium text-ink-2">
              <ZapIcon size={12} className="text-brand" />
              4 个模型可用
            </div>
            <p className="mt-1 text-[10px] leading-relaxed text-ink-3">
              Chat / Reasoner 与联网模式，按需切换。
            </p>
          </div>
        </aside>
      ) : (
        <button
          onClick={() => setSidebarCollapsed(false)}
          className="flex h-full w-8 shrink-0 items-center justify-center border-r border-white/70 bg-white/45 text-ink-3 backdrop-blur-xl transition-colors hover:bg-white/70 hover:text-ink-2"
          title="展开会话历史"
        >
          <ChevronRightIcon size={14} />
        </button>
      )}

      {/* 对话主区 */}
      <section className="flex min-w-0 flex-1 flex-col">
        {/* 顶部：模型选择 + 路由说明 */}
        <div className="flex items-center gap-2 border-b border-white/70 bg-white/45 px-5 py-3 backdrop-blur-xl">
          <div className="flex size-8 items-center justify-center rounded-xl bg-brand-soft text-brand-ink">
            <ZapIcon size={16} />
          </div>
          <div className="relative">
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              disabled={streaming}
              className="glass-input h-8 cursor-pointer appearance-none rounded-lg border border-line bg-white/85 py-0 pl-2.5 pr-7 text-[12px] font-medium text-ink outline-none transition-all hover:border-line-strong focus:border-brand disabled:opacity-60"
            >
              {modelOptions.map((m) => (
                <option key={m} value={m}>
                  {MODEL_LABELS[m] || m}
                </option>
              ))}
            </select>
            <ChevronDownIcon
              size={13}
              className="pointer-events-none absolute right-2 top-1/2 -translate-y-1/2 text-ink-3"
            />
          </div>
          {route ? <RouteBadge route={route} /> : null}
          <div className="flex-1" />
          <span className="hidden items-center gap-1 rounded-full bg-func-orange-soft px-2.5 py-1 text-[10px] font-medium text-func-orange sm:flex">
            <span className="size-1.5 rounded-full bg-current" />
            仅用于测试
          </span>
          <Button
            variant="primary"
            size="sm"
            icon={PlusIcon}
            onClick={newConversation}
            disabled={streaming}
            className="!h-8 !px-3"
          >
            新对话
          </Button>
        </div>

        {/* 消息流 */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto">
          {loadingConv ? (
            <div className="flex h-full items-center justify-center">
              <Spinner size={22} />
            </div>
          ) : messages.length === 0 ? (
            <div className="flex h-full flex-col items-center justify-center gap-6 px-5 pb-14">
              <div className="flex flex-col items-center gap-4 text-center">
                <div className="animate-float">
                  <div className="relative">
                    <div className="absolute inset-0 rounded-[28px] bg-brand/20 blur-2xl" />
                    <img
                      src="./juyuan-logo.png"
                      alt="聚元"
                      className="relative size-[86px] rounded-[26px] border border-white/90 bg-white object-contain p-1 shadow-[0_20px_50px_-24px_rgba(47,134,246,0.55)]"
                    />
                  </div>
                </div>
                <div>
                  <h2 className="brand-gradient-text text-[24px] font-semibold tracking-tight">
                    聚元汇智，通达四方
                  </h2>
                  <p className="mt-1.5 text-[12px] text-ink-3">
                    一个窗口，连接 DeepSeek 网页版的四种模式
                  </p>
                </div>
              </div>

              <div className="grid w-full max-w-[640px] grid-cols-2 gap-2">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.title}
                    onClick={() => useSuggestion(s.prompt)}
                    className="ui-card ui-card-hover group flex items-start gap-2.5 rounded-xl px-3 py-2.5 text-left"
                  >
                    <span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-lg bg-brand-soft text-brand-ink transition-transform group-hover:scale-105">
                      <SparklesIcon size={14} />
                    </span>
                    <span className="min-w-0">
                      <span className="block text-[12px] font-medium text-ink">{s.title}</span>
                      <span className="mt-0.5 block truncate text-[11px] text-ink-3">{s.prompt}</span>
                    </span>
                  </button>
                ))}
              </div>

              <div className="w-full max-w-[720px]">{InputBox}</div>
            </div>
          ) : (
            <div className="mx-auto flex max-w-[720px] flex-col gap-5 px-5 py-5">
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
          <div className="border-t border-white/70 bg-white/35 px-5 py-3.5 backdrop-blur-xl">
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
    <Pill tone={route.auto ? 'brand' : 'neutral'} title={route.reason} className="hidden md:inline-flex">
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
        <div className="max-w-[82%] whitespace-pre-wrap break-words rounded-2xl rounded-br-md bg-gradient-to-br from-[#4a9bff] via-brand to-[#1769e0] px-3.5 py-2.5 text-[13px] leading-relaxed text-white shadow-[0_10px_24px_-16px_rgba(47,134,246,0.85)]">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex items-start gap-2.5">
      <img
        src="./juyuan-logo.png"
        alt=""
        className="mt-0.5 size-7 shrink-0 rounded-lg border border-line/70 bg-white object-contain p-0.5 shadow-sm"
      />
      <div className="min-w-0 flex-1">
        <div className="rounded-2xl rounded-tl-md border border-line/70 bg-white/85 px-3.5 py-2.5 shadow-[0_8px_26px_-22px_rgba(18,54,105,0.4)] backdrop-blur-sm">
          <div className="md text-ink">
            {message.content ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            ) : message.streaming ? (
              <span className="inline-flex items-center gap-1 py-1">
                <span className="typing-dot size-1.5 rounded-full bg-brand" />
                <span className="typing-dot size-1.5 rounded-full bg-brand" />
                <span className="typing-dot size-1.5 rounded-full bg-brand" />
              </span>
            ) : (
              <span className="text-ink-3">（空响应）</span>
            )}
          </div>
        </div>
        {!message.streaming && message.content ? (
          <div className="mt-1 flex items-center gap-1 text-ink-3">
            <button
              onClick={copy}
              className="ui-press flex items-center gap-1 rounded-md px-1.5 py-1 text-[10px] transition-colors hover:bg-white hover:text-ink-2"
              title="复制"
            >
              {copied ? <CheckIcon size={12} /> : <CopyIcon size={12} />}
              {copied ? '已复制' : '复制'}
            </button>
          </div>
        ) : null}
      </div>
    </div>
  )
}
