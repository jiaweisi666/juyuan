/**
 * ui.jsx - 通用 UI 原语。
 *
 * 浅色云白底 + 聚元蓝主色；用轻阴影、渐变和按压反馈提升质感。
 * 正文 13px，标题 16-18px。
 */

import { CloseIcon, AlertIcon, InfoIcon, CheckIcon } from './icons.jsx'

/* -------------------------------- 按钮 ---------------------------------- */
const BTN_VARIANTS = {
  primary: 'btn-primary text-white border-transparent hover:-translate-y-px',
  ghost: 'bg-transparent text-ink-2 hover:bg-surface-2 hover:text-ink border-transparent',
  subtle:
    'bg-white/80 text-ink hover:bg-surface-2 border-line hover:border-line-strong shadow-[0_1px_2px_rgba(18,54,105,0.03)]',
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
    sm: 'h-7 px-2.5 text-[12px] gap-1.5 rounded-lg',
    md: 'h-8 px-3 text-[13px] gap-1.5 rounded-lg',
    lg: 'h-9 px-4 text-[13px] gap-2 rounded-xl',
  }
  return (
    <button
      className={`ui-press inline-flex items-center justify-center border font-medium
        transition-all duration-200 disabled:opacity-45 disabled:cursor-not-allowed
        disabled:hover:translate-y-0 disabled:hover:shadow-none
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
    <div className={`ui-card rounded-xl ${className}`} {...rest}>
      {children}
    </div>
  )
}

/* ------------------------------ 状态标签 -------------------------------- */
const PILL_TONES = {
  neutral: 'bg-surface-2/90 text-ink-2 border-line/80',
  brand: 'bg-brand-soft text-brand-ink border-brand/15',
  emerald: 'bg-func-emerald-soft text-func-emerald border-func-emerald/15',
  orange: 'bg-func-orange-soft text-func-orange border-func-orange/15',
  rose: 'bg-func-rose-soft text-func-rose border-func-rose/15',
  violet: 'bg-func-violet-soft text-func-violet border-func-violet/15',
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
export function Field({ label, hint, required = false, children, className = '' }) {
  return (
    <label className={`flex flex-col gap-1 ${className}`}>
      {label ? (
        <span className="text-[12px] font-medium text-ink-2">
          {label}
          {required ? <span className="ml-0.5 text-func-rose">*</span> : null}
        </span>
      ) : null}
      {children}
      {hint ? <span className="text-[11px] text-ink-3">{hint}</span> : null}
    </label>
  )
}

const INPUT_CLASS =
  'glass-input h-8 w-full rounded-lg border border-line px-2.5 text-[13px] text-ink ' +
  'outline-none transition-all placeholder:text-ink-3 ' +
  'hover:border-line-strong focus:border-brand'

export function Input({ className = '', ...rest }) {
  return <input className={`${INPUT_CLASS} ${className}`} {...rest} />
}

export function Textarea({ className = '', ...rest }) {
  return (
    <textarea
      className={`glass-input w-full resize-none rounded-lg border border-line px-2.5 py-2
        text-[13px] leading-relaxed text-ink outline-none transition-all
        placeholder:text-ink-3 hover:border-line-strong focus:border-brand ${className}`}
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
        className={`relative h-[20px] w-[36px] rounded-full border transition-all duration-200
          ${checked ? 'border-brand bg-brand shadow-[0_2px_8px_-2px_rgba(47,134,246,0.7)]' : 'border-line-strong bg-surface-2'}`}
      >
        <span
          className={`absolute top-[2px] size-[14px] rounded-full bg-white shadow-sm transition-all duration-200
            ${checked ? 'left-[19px]' : 'left-[2px]'}`}
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
      className={`ring-spin inline-block rounded-full border-2 border-brand/20 border-t-brand ${className}`}
      style={{ width: size, height: size }}
    />
  )
}

export function Empty({ icon: Icon = InfoIcon, title, desc }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
      <span className="flex size-12 items-center justify-center rounded-2xl bg-brand-soft/80 text-brand-ink shadow-[inset_0_1px_0_rgba(255,255,255,0.8)]">
        <Icon size={24} />
      </span>
      <div className="text-[13px] font-medium text-ink-2">{title}</div>
      {desc ? <div className="max-w-[340px] text-[12px] leading-relaxed text-ink-3">{desc}</div> : null}
    </div>
  )
}

/* ------------------------------ 提示条 ---------------------------------- */
export function Banner({ tone = 'info', children, onClose }) {
  const tones = {
    info: { cls: 'bg-brand-soft/80 text-brand-ink border border-brand/10', Icon: InfoIcon },
    error: { cls: 'bg-func-rose-soft text-func-rose border border-func-rose/10', Icon: AlertIcon },
    success: {
      cls: 'bg-func-emerald-soft text-func-emerald border border-func-emerald/10',
      Icon: CheckIcon,
    },
  }
  const { cls, Icon } = tones[tone] || tones.info
  return (
    <div className={`flex items-start gap-2 rounded-lg px-3 py-2 text-[12px] ${cls}`}>
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
    <div className="absolute inset-0 z-50 flex items-center justify-center bg-[#0b1f3a]/25 p-4 backdrop-blur-[3px]">
      <div
        className="pop-in flex max-h-full w-full flex-col overflow-hidden rounded-2xl border border-white/80 bg-surface shadow-[0_30px_80px_-30px_rgba(10,44,96,0.45)]"
        style={{ maxWidth: width }}
      >
        <div className="flex items-center justify-between border-b border-line/80 bg-surface-2/50 px-4 py-3">
          <h2 className="text-[15px] font-semibold text-ink">{title}</h2>
          <button
            onClick={onClose}
            className="ui-press rounded-lg p-1 text-ink-3 transition-colors hover:bg-surface-2 hover:text-ink"
          >
            <CloseIcon size={16} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-3.5">{children}</div>
        {footer ? (
          <div className="flex items-center justify-end gap-2 border-t border-line/80 bg-surface-2/40 px-4 py-3">
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
    <div className="flex items-start justify-between gap-4 pb-3.5">
      <div className="min-w-0">
        <div className="mb-1 flex items-center gap-2">
          <span className="h-1.5 w-1.5 rounded-full bg-brand shadow-[0_0_0_3px_rgba(47,134,246,0.14)]" />
          <span className="text-[10px] font-medium uppercase tracking-[0.16em] text-brand-ink/70">
            Juyuan Console
          </span>
        </div>
        <h1 className="text-[18px] font-semibold leading-tight tracking-[-0.01em] text-ink">{title}</h1>
        {desc ? <p className="mt-0.5 max-w-[760px] text-[12px] leading-relaxed text-ink-3">{desc}</p> : null}
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
