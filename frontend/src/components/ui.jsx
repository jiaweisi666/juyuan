/**
 * ui.jsx - 通用 UI 原语。
 *
 * 遵循设计规格：无渐变、无阴影、无多余边框；以留白与分组线组织信息。
 * 正文 13px，标题 16-18px，主色 Sky Blue。
 */

import { CloseIcon, AlertIcon, InfoIcon, CheckIcon } from './icons.jsx'

/* -------------------------------- 按钮 ---------------------------------- */
const BTN_VARIANTS = {
  primary: 'bg-brand text-white hover:bg-brand-ink border-brand',
  ghost: 'bg-transparent text-ink-2 hover:bg-surface-2 border-transparent',
  subtle: 'bg-surface text-ink hover:bg-surface-2 border-line',
  danger: 'bg-transparent text-func-rose hover:bg-func-rose-soft border-line',
}

export function Button({
  children,
  variant = 'subtle',
  size = 'md',
  icon: Icon,
  loading = false,
  className = '',
  ...rest
}) {
  const sizes = {
    sm: 'h-7 px-2.5 text-[12px] gap-1.5',
    md: 'h-8 px-3 text-[13px] gap-1.5',
    lg: 'h-9 px-4 text-[13px] gap-2',
  }
  return (
    <button
      className={`inline-flex items-center justify-center rounded-md border font-medium
        transition-colors disabled:opacity-45 disabled:cursor-not-allowed
        ${BTN_VARIANTS[variant] || BTN_VARIANTS.subtle} ${sizes[size]} ${className}`}
      disabled={loading || rest.disabled}
      {...rest}
    >
      {loading ? <Spinner size={14} /> : Icon ? <Icon size={15} /> : null}
      {children}
    </button>
  )
}

/* -------------------------------- 卡片 ---------------------------------- */
export function Card({ children, className = '', ...rest }) {
  return (
    <div className={`rounded-lg border border-line bg-surface ${className}`} {...rest}>
      {children}
    </div>
  )
}

/* ------------------------------ 状态标签 -------------------------------- */
const PILL_TONES = {
  neutral: 'bg-surface-2 text-ink-2 border-line',
  brand: 'bg-brand-soft text-brand-ink border-brand-soft',
  emerald: 'bg-func-emerald-soft text-func-emerald border-transparent',
  orange: 'bg-func-orange-soft text-func-orange border-transparent',
  rose: 'bg-func-rose-soft text-func-rose border-transparent',
  violet: 'bg-func-violet-soft text-func-violet border-transparent',
}

export function Pill({ children, tone = 'neutral', dot = false, className = '' }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5
        text-[11px] font-medium leading-5 ${PILL_TONES[tone] || PILL_TONES.neutral} ${className}`}
    >
      {dot ? <span className="size-1.5 rounded-full bg-current" /> : null}
      {children}
    </span>
  )
}

/* ------------------------------ 表单字段 -------------------------------- */
export function Field({ label, hint, children, className = '' }) {
  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      {label ? <span className="text-[12px] font-medium text-ink-2">{label}</span> : null}
      {children}
      {hint ? <span className="text-[11px] text-ink-3">{hint}</span> : null}
    </label>
  )
}

const INPUT_CLASS =
  'h-8 w-full rounded-md border border-line bg-surface px-2.5 text-[13px] text-ink ' +
  'outline-none transition-colors placeholder:text-ink-3 ' +
  'focus:border-brand focus:ring-2 focus:ring-brand-soft'

export function Input({ className = '', ...rest }) {
  return <input className={`${INPUT_CLASS} ${className}`} {...rest} />
}

export function Textarea({ className = '', ...rest }) {
  return (
    <textarea
      className={`w-full resize-none rounded-md border border-line bg-surface px-2.5 py-2
        text-[13px] leading-relaxed text-ink outline-none transition-colors
        placeholder:text-ink-3 focus:border-brand focus:ring-2 focus:ring-brand-soft ${className}`}
      {...rest}
    />
  )
}

export function Select({ className = '', children, ...rest }) {
  return (
    <select className={`${INPUT_CLASS} cursor-pointer pr-7 ${className}`} {...rest}>
      {children}
    </select>
  )
}

/* -------------------------------- 开关 ---------------------------------- */
export function Toggle({ checked, onChange, disabled = false, label }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onChange?.(!checked)}
      className="inline-flex items-center gap-2 disabled:opacity-45"
    >
      <span
        className={`relative h-[18px] w-[32px] rounded-full border transition-colors
          ${checked ? 'border-brand bg-brand' : 'border-line-strong bg-surface-2'}`}
      >
        <span
          className={`absolute top-[1px] size-[14px] rounded-full bg-white transition-all
            ${checked ? 'left-[15px]' : 'left-[1px]'}`}
        />
      </span>
      {label ? <span className="text-[13px] text-ink-2">{label}</span> : null}
    </button>
  )
}

/* ------------------------------ 空/加载 --------------------------------- */
export function Spinner({ size = 16, className = '' }) {
  return (
    <span
      className={`inline-block animate-spin rounded-full border-2 border-line-strong border-t-brand ${className}`}
      style={{ width: size, height: size }}
    />
  )
}

export function Empty({ icon: Icon = InfoIcon, title, desc }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-2 px-6 py-10 text-center">
      <Icon size={26} className="text-ink-3" />
      <div className="text-[13px] font-medium text-ink-2">{title}</div>
      {desc ? <div className="max-w-[320px] text-[12px] text-ink-3">{desc}</div> : null}
    </div>
  )
}

/* ------------------------------ 提示条 ---------------------------------- */
export function Banner({ tone = 'info', children, onClose }) {
  const tones = {
    info: { cls: 'bg-brand-soft text-brand-ink', Icon: InfoIcon },
    error: { cls: 'bg-func-rose-soft text-func-rose', Icon: AlertIcon },
    success: { cls: 'bg-func-emerald-soft text-func-emerald', Icon: CheckIcon },
  }
  const { cls, Icon } = tones[tone] || tones.info
  return (
    <div className={`flex items-start gap-2 rounded-md px-3 py-2 text-[12px] ${cls}`}>
      <Icon size={15} className="mt-0.5 shrink-0" />
      <div className="flex-1">{children}</div>
      {onClose ? (
        <button onClick={onClose} className="shrink-0 opacity-70 hover:opacity-100">
          <CloseIcon size={14} />
        </button>
      ) : null}
    </div>
  )
}

/* ------------------------------ 弹窗 ------------------------------------ */
export function Modal({ open, title, onClose, children, footer, width = '460px' }) {
  if (!open) return null
  return (
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-black/25 p-4">
      <div
        className="flex max-h-full w-full flex-col overflow-hidden rounded-lg border border-line bg-surface"
        style={{ maxWidth: width }}
      >
        <div className="flex items-center justify-between border-b border-line px-4 py-3">
          <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
          <button onClick={onClose} className="text-ink-3 hover:text-ink">
            <CloseIcon size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3">{children}</div>
        {footer ? (
          <div className="flex items-center justify-end gap-2 border-t border-line px-4 py-3">
            {footer}
          </div>
        ) : null}
      </div>
    </div>
  )
}

/* --------------------------- 页面头部（标题区） -------------------------- */
export function PageHeader({ title, desc, actions }) {
  return (
    <div className="flex items-start justify-between gap-4 pb-3">
      <div className="min-w-0">
        <h1 className="text-[17px] font-semibold leading-tight text-ink">{title}</h1>
        {desc ? <p className="mt-0.5 text-[12px] text-ink-3">{desc}</p> : null}
      </div>
      {actions ? <div className="flex shrink-0 items-center gap-2">{actions}</div> : null}
    </div>
  )
}

/* ------------------------------ 键值行 ---------------------------------- */
export function KV({ k, children, mono = false }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-1.5">
      <span className="shrink-0 text-[12px] text-ink-3">{k}</span>
      <span className={`min-w-0 text-right text-[12px] text-ink-2 ${mono ? 'font-mono' : ''}`}>
        {children}
      </span>
    </div>
  )
}
