/**
 * api.js - 与后端网关通信的轻量客户端。
 *
 * 所有大模型请求均由后端转发，前端仅通过 REST + SSE 访问本地网关。
 * 若在 localStorage 中配置了 apiKey / adminToken，会自动附加鉴权头。
 */

const LS_API_KEY = 'juyuan.apiKey'
const LS_ADMIN_TOKEN = 'juyuan.adminToken'
const LS_BASE_URL = 'juyuan.baseUrl'

function baseUrl() {
  return (localStorage.getItem(LS_BASE_URL) || '').replace(/\/$/, '')
}

export function getClientConfig() {
  return {
    baseUrl: baseUrl(),
    apiKey: localStorage.getItem(LS_API_KEY) || '',
    adminToken: localStorage.getItem(LS_ADMIN_TOKEN) || '',
  }
}

export function saveClientConfig({ baseUrl: b, apiKey, adminToken }) {
  localStorage.setItem(LS_BASE_URL, b || '')
  localStorage.setItem(LS_API_KEY, apiKey || '')
  localStorage.setItem(LS_ADMIN_TOKEN, adminToken || '')
}

function authHeaders() {
  const headers = {}
  const apiKey = localStorage.getItem(LS_API_KEY)
  const adminToken = localStorage.getItem(LS_ADMIN_TOKEN)
  if (apiKey) headers['Authorization'] = `Bearer ${apiKey}`
  if (adminToken) headers['x-admin-token'] = adminToken
  return headers
}

async function request(path, { method = 'GET', body, headers = {} } = {}) {
  const res = await fetch(baseUrl() + path, {
    method,
    headers: { 'Content-Type': 'application/json', ...authHeaders(), ...headers },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  const text = await res.text()
  let data = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }
  if (!res.ok) {
    const detail = data && (data.detail || data.error || data)
    const msg =
      (detail && (detail.message || detail.msg)) ||
      (typeof detail === 'string' ? detail : '') ||
      `请求失败 (HTTP ${res.status})`
    const err = new Error(msg)
    err.status = res.status
    err.data = data
    throw err
  }
  return data
}

/* ------------------------------ 系统 / 模型 ------------------------------ */
export const getGatewayInfo = () => request('/api/gateway/info')
// 前端管理面板走管理端模型清单（外部第三方请使用 /v1/models 携带 API Key）
export const getModels = () => request('/api/models')
export const getModelCatalog = () => request('/api/models/catalog')
export const refreshModels = () => request('/api/models/refresh', { method: 'POST' })

/* ------------------------------ API 密钥 -------------------------------- */
export const getKeyMeta = () => request('/api/keys/meta')
export const getApiKeys = () => request('/api/keys')
export const createApiKey = (payload) => request('/api/keys', { method: 'POST', body: payload })
export const updateApiKey = (id, payload) => request(`/api/keys/${id}`, { method: 'PUT', body: payload })
export const deleteApiKey = (id) => request(`/api/keys/${id}`, { method: 'DELETE' })
export const revealApiKey = (id) => request(`/api/keys/${id}/reveal`, { method: 'POST' })

/* -------------------------------- 平台 ---------------------------------- */
export const getPlatforms = () => request('/api/platforms')
export const testPlatform = (id) => request(`/api/platforms/${id}/test`, { method: 'POST' })

/* -------------------------------- 账号 ---------------------------------- */
export const getAccounts = () => request('/api/accounts')
export const createAccount = (payload) => request('/api/accounts', { method: 'POST', body: payload })
export const updateAccount = (id, payload) =>
  request(`/api/accounts/${id}`, { method: 'PUT', body: payload })
export const deleteAccount = (id) => request(`/api/accounts/${id}`, { method: 'DELETE' })
export const accountsHealthCheck = () => request('/api/accounts/health-check', { method: 'POST' })
// 从受控浏览器一键读取已登录站点 Cookie 并写入账号池（重复点击即刷新）
export const autoImportAccounts = () => request('/api/accounts/auto-import', { method: 'POST' })
// 在受控浏览器中打开平台官方登录页
export const openLoginPage = (platform) =>
  request('/api/accounts/open-login', { method: 'POST', body: { platform } })
// 读取指定平台登录态并写入账号池（登录导入轮询用）
export const readImportAccount = (platform) =>
  request('/api/accounts/read-import', { method: 'POST', body: { platform } })

/* ------------------------------ 路由配置 -------------------------------- */
export const getRoutingConfig = () => request('/api/routing/config')
export const setRoutingConfig = (payload) =>
  request('/api/routing/config', { method: 'PUT', body: payload })
export const getRoutingWeights = () => request('/api/routing/weights')
export const setRoutingWeights = (payload) =>
  request('/api/routing/weights', { method: 'PUT', body: payload })
export const getProfiles = () => request('/api/routing/profiles')
export const getDecisions = (limit = 50) => request(`/api/routing/decisions?limit=${limit}`)
export const submitFeedback = (payload) => request('/api/feedback', { method: 'POST', body: payload })

/* ------------------------------ 日志 / 统计 ----------------------------- */
export const getLogs = ({ limit = 100, offset = 0, status = '', platform = '' } = {}) =>
  request(
    `/api/logs?limit=${limit}&offset=${offset}&status=${encodeURIComponent(status)}&platform=${encodeURIComponent(platform)}`,
  )
export const getStatsSummary = () => request('/api/stats/summary')
export const getStatsSeries = (hours = 24) => request(`/api/stats/series?hours=${hours}`)

/* -------------------------------- 会话 ---------------------------------- */
export const listConversations = () => request('/api/chat/conversations')
export const createConversation = (title, model) =>
  request('/api/chat/conversations', { method: 'POST', body: { title, model } })
export const getConversation = (id) => request(`/api/chat/conversations/${id}`)
export const deleteConversation = (id) =>
  request(`/api/chat/conversations/${id}`, { method: 'DELETE' })

/**
 * 流式发送消息。回调：
 *   onEvent({ conversation_id })、onEvent({ route })、onEvent({ delta })、onEvent({ done })
 * 返回 AbortController 以便中断。
 */
export function sendChatStream({ conversation_id, model, content }, onEvent, onError) {
  const controller = new AbortController()

  ;(async () => {
    try {
      const res = await fetch(baseUrl() + '/api/chat/send', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({ conversation_id, model, content, stream: true }),
        signal: controller.signal,
      })
      if (!res.ok || !res.body) {
        throw new Error(`发送失败 (HTTP ${res.status})`)
      }
      const reader = res.body.getReader()
      const decoder = new TextDecoder('utf-8')
      let buffer = ''
      for (;;) {
        const { value, done } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        let idx
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const raw = buffer.slice(0, idx).trim()
          buffer = buffer.slice(idx + 2)
          if (!raw.startsWith('data:')) continue
          const payload = raw.slice(5).trim()
          if (!payload) continue
          try {
            onEvent(JSON.parse(payload))
          } catch {
            /* 忽略无法解析的心跳片段 */
          }
        }
      }
    } catch (err) {
      if (err.name !== 'AbortError') onError?.(err)
    }
  })()

  return controller
}
