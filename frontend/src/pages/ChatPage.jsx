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
  submitFeedback,
} from '../api.js'
import {
  ChatIcon,
  PlusIcon,
  SendIcon,
  StopIcon,
  TrashIcon,
  HistoryIcon,
  ThumbUpIcon,
  ThumbDownIcon,
  ZapIcon,
  CheckIcon,
  CopyIcon,
} from '../components/icons.jsx'
import { Button, Empty, Pill, Spinner, Textarea } from '../components/ui.jsx'

const MODEL_LABELS = {
  auto: 'AUTO · 智能路由',
}

export default function ChatPage({ onToast }) {
  const [models, setModels] = useState(['auto'])
  const [model, setModel] = useState('auto')
  const [conversations, setConversations] = useState([])
  const [activeId, setActiveId] = useState(null)
  const [messages, setMessages] = useState([])
  const [route, setRoute] = useState(null)
  const [input, setInput] = useState('')
  const [streaming, setStreaming] = useState(false)
  const [loadingConv, setLoadingConv] = useState(false)

  const abortRef = useRef(null)
  const scrollRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    getModels()
      .then((res) => {
        const ids = (res?.data || []).map((m) => m.id)
        setModels(ids.length ? ids : ['auto'])
      })
      .catch(() => {})
    refreshConversations()
  }, [])

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

  function handleFeedback(msg, rating) {
    if (!route) return
    submitFeedback({
      call_log_id: route.call_log_id || '',
      platform: route.platform,
      variant: route.variant || 'default',
      rating,
      task_type: 'general',
    })
      .then(() => onToast?.(rating === 'up' ? '已记录好评，将优化路由' : '已记录反馈，将调整路由', 'success'))
      .catch((err) => onToast?.(err.message, 'error'))
  }

  const modelOptions = useMemo(() => {
    const list = models.filter((m) => m !== 'auto')
    return ['auto', ...list]
  }, [models])

  return (
    <div className="flex h-full">
      {/* 会话历史 */}
      <aside className="flex w-[212px] shrink-0 flex-col border-r border-line bg-surface-2/60">
        <div className="flex items-center justify-between px-3 py-2.5">
          <span className="flex items-center gap-1.5 text-[12px] font-medium text-ink-2">
            <HistoryIcon size={14} /> 会话历史
          </span>
          <button
            onClick={newConversation}
            className="rounded-md p-1 text-ink-3 transition-colors hover:bg-surface hover:text-brand"
            title="新建对话"
          >
            <PlusIcon size={16} />
          </button>
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
              outline-none focus:border-brand"
          >
            {modelOptions.map((m) => (
              <option key={m} value={m}>
                {MODEL_LABELS[m] || m}
              </option>
            ))}
          </select>
          {route ? <RouteBadge route={route} /> : null}
          <div className="flex-1" />
          <Button variant="ghost" size="sm" icon={PlusIcon} onClick={newConversation} disabled={streaming}>
            新对话
          </Button>
        </div>

        {/* 消息流 */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-3">
          {loadingConv ? (
            <div className="flex h-full items-center justify-center">
              <Spinner size={20} />
            </div>
          ) : messages.length === 0 ? (
            <Empty
              icon={ChatIcon}
              title="开始与聚元网关对话"
              desc="AUTO 模式会根据问题复杂度、延迟与成本，自动选择最合适的模型平台。"
            />
          ) : (
            <div className="mx-auto flex max-w-[620px] flex-col gap-4">
              {messages.map((m, i) => (
                <MessageBubble key={i} message={m} onFeedback={handleFeedback} />
              ))}
            </div>
          )}
        </div>

        {/* 输入区 */}
        <div className="border-t border-line px-4 py-3">
          <div className="mx-auto flex max-w-[620px] items-end gap-2">
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
        </div>
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

function MessageBubble({ message, onFeedback }) {
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
          <button
            onClick={() => onFeedback(message, 'up')}
            className="rounded p-1 hover:text-func-emerald"
            title="回答有帮助"
          >
            <ThumbUpIcon size={13} />
          </button>
          <button
            onClick={() => onFeedback(message, 'down')}
            className="rounded p-1 hover:text-func-rose"
            title="回答不理想"
          >
            <ThumbDownIcon size={13} />
          </button>
        </div>
      ) : null}
    </div>
  )
}
