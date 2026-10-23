/**
 * icons.jsx - 线性图标集合（HugeIcons Free 风格：24x24、1.6 描边、圆角端点）。
 *
 * 集中定义，页面按名引用；如需替换为其它图标库，仅需改动本文件。
 */

function Icon({ children, size = 20, strokeWidth = 1.6, className = '', fill = 'none', ...rest }) {
  return (
    <svg
      viewBox="0 0 24 24"
      width={size}
      height={size}
      fill={fill}
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  )
}

export const ChatIcon = (p) => (
  <Icon {...p}>
    <path d="M20 14.5a2 2 0 0 1-2 2H8l-4 3.5V6a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2z" />
  </Icon>
)

export const ModelsIcon = (p) => (
  <Icon {...p}>
    <path d="M12 3 3 8l9 5 9-5-9-5Z" />
    <path d="m3 13 9 5 9-5" />
  </Icon>
)

export const AccountsIcon = (p) => (
  <Icon {...p}>
    <path d="M15 20v-1.5a3.5 3.5 0 0 0-3.5-3.5h-4A3.5 3.5 0 0 0 4 18.5V20" />
    <circle cx="9.5" cy="8" r="3.2" />
    <path d="M20 20v-1.5a3.5 3.5 0 0 0-2.6-3.36" />
    <path d="M15.2 5.1a3.2 3.2 0 0 1 0 5.8" />
  </Icon>
)

export const RoutingIcon = (p) => (
  <Icon {...p}>
    <path d="M4 19h4a4 4 0 0 0 4-4V9a4 4 0 0 1 4-4h4" />
    <circle cx="4" cy="19" r="1.6" />
    <circle cx="20" cy="5" r="1.6" />
  </Icon>
)

export const LogsIcon = (p) => (
  <Icon {...p}>
    <path d="M4 19V5" />
    <path d="M4 19h16" />
    <path d="m7 15 3-3.5 3 2.5 4-6" />
  </Icon>
)

export const PlusIcon = (p) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
)

export const SendIcon = (p) => (
  <Icon {...p}>
    <path d="M21 3 10.5 13.5" />
    <path d="M21 3 14.6 20.4l-4.1-6.9L3.6 9.4z" />
  </Icon>
)

export const RefreshIcon = (p) => (
  <Icon {...p}>
    <path d="M20 12a8 8 0 1 1-2.34-5.66" />
    <path d="M20 4v4h-4" />
  </Icon>
)

export const TrashIcon = (p) => (
  <Icon {...p}>
    <path d="M4 7h16" />
    <path d="M9.5 7V4.8h5V7" />
    <path d="M6.5 7 7.5 20h9L17.5 7" />
  </Icon>
)

export const UploadIcon = (p) => (
  <Icon {...p}>
    <path d="M12 16V4" />
    <path d="m7.5 8.5 4.5-4.5 4.5 4.5" />
    <path d="M4 20h16" />
  </Icon>
)

export const CloseIcon = (p) => (
  <Icon {...p}>
    <path d="m6 6 12 12M18 6 6 18" />
  </Icon>
)

export const ChevronDownIcon = (p) => (
  <Icon {...p}>
    <path d="m6 9 6 6 6-6" />
  </Icon>
)

export const ChevronRightIcon = (p) => (
  <Icon {...p}>
    <path d="m9 6 6 6-6 6" />
  </Icon>
)

export const ChevronLeftIcon = (p) => (
  <Icon {...p}>
    <path d="m15 6-6 6 6 6" />
  </Icon>
)

export const SettingsIcon = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 13.5a1.7 1.7 0 0 0 .34 1.87l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.7 1.7 0 0 0-1.87-.34 1.7 1.7 0 0 0-1.04 1.56V21a2 2 0 1 1-4 0v-.1A1.7 1.7 0 0 0 8.9 19.3a1.7 1.7 0 0 0-1.87.34l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.7 1.7 0 0 0 .34-1.87 1.7 1.7 0 0 0-1.56-1.04H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.7 8.9a1.7 1.7 0 0 0-.34-1.87l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.7 1.7 0 0 0 1.87.34H9.1A1.7 1.7 0 0 0 10.14 2.98V2.9a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1.04 1.56 1.7 1.7 0 0 0 1.87-.34l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.7 1.7 0 0 0-.34 1.87v.08A1.7 1.7 0 0 0 21 10.14h.1a2 2 0 1 1 0 4H21a1.7 1.7 0 0 0-1.56 1.04z" />
  </Icon>
)

export const SearchIcon = (p) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="m20 20-3.5-3.5" />
  </Icon>
)

export const DownloadIcon = (p) => (
  <Icon {...p}>
    <path d="M12 4v12" />
    <path d="m7.5 11.5 4.5 4.5 4.5-4.5" />
    <path d="M4 20h16" />
  </Icon>
)

export const CheckIcon = (p) => (
  <Icon {...p}>
    <path d="m5 12.5 4.5 4.5L19 7" />
  </Icon>
)

export const AlertIcon = (p) => (
  <Icon {...p}>
    <path d="M10.3 4.3 2.6 18a1.9 1.9 0 0 0 1.7 2.9h15.4a1.9 1.9 0 0 0 1.7-2.9L13.7 4.3a1.9 1.9 0 0 0-3.4 0Z" />
    <path d="M12 9.5v4" />
    <path d="M12 17v.5" />
  </Icon>
)

export const InfoIcon = (p) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11.5V16" />
    <path d="M12 8.2v.4" />
  </Icon>
)

export const ZapIcon = (p) => (
  <Icon {...p}>
    <path d="M13.2 3 5.5 13.2h4.6L10 21l7.7-10.2h-4.6z" />
  </Icon>
)

export const CopyIcon = (p) => (
  <Icon {...p}>
    <rect x="9" y="9" width="11" height="11" rx="2" />
    <path d="M15 9V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v7a2 2 0 0 0 2 2h3" />
  </Icon>
)

export const StopIcon = (p) => (
  <Icon {...p}>
    <rect x="6.5" y="6.5" width="11" height="11" rx="2" />
  </Icon>
)

export const HistoryIcon = (p) => (
  <Icon {...p}>
    <path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1" />
    <path d="M3.5 4.6V9H8" />
    <path d="M12 8v4.5l3 1.8" />
  </Icon>
)

export const LinkIcon = (p) => (
  <Icon {...p}>
    <path d="M10.5 13.5a4 4 0 0 0 5.66 0l2.34-2.34a4 4 0 1 0-5.66-5.66L11.6 6.7" />
    <path d="M13.5 10.5a4 4 0 0 0-5.66 0L5.5 12.84a4 4 0 1 0 5.66 5.66l1.24-1.24" />
  </Icon>
)

export const KeyIcon = (p) => (
  <Icon {...p}>
    <circle cx="7.5" cy="15.5" r="4" />
    <path d="m10.6 12.4 8-8" />
    <path d="m15.2 3.8 4 4" />
    <path d="m17.2 5.8-2 2" />
  </Icon>
)

export const ShieldIcon = (p) => (
  <Icon {...p}>
    <path d="M12 3 5 5.8v5.9c0 4.3 2.9 7.4 7 8.8 4.1-1.4 7-4.5 7-8.8V5.8z" />
    <path d="m9 12 2 2 4-4" />
  </Icon>
)

export const ShieldCheckIcon = (p) => (
  <Icon {...p}>
    <path d="M12 3 5 5.8v5.9c0 4.3 2.9 7.4 7 8.8 4.1-1.4 7-4.5 7-8.8V5.8z" />
    <path d="m8.8 11.8 2.2 2.2 4.2-4.2" />
  </Icon>
)

export const ThumbUpIcon = (p) => (
  <Icon {...p}>
    <path d="M7 21V10.5l3.5-6.2a1.6 1.6 0 0 1 2.9 1.2L12.5 9H19a2 2 0 0 1 1.96 2.4l-1.2 6A2 2 0 0 1 17.8 19H7z" />
    <path d="M7 10.5H4.5A1.5 1.5 0 0 0 3 12v7.5A1.5 1.5 0 0 0 4.5 21H7" />
  </Icon>
)

export const ThumbDownIcon = (p) => (
  <Icon {...p}>
    <path d="M7 3v10.5l3.5 6.2a1.6 1.6 0 0 0 2.9-1.2L12.5 15H19a2 2 0 0 0 1.96-2.4l-1.2-6A2 2 0 0 0 17.8 5H7z" />
    <path d="M7 13.5H4.5A1.5 1.5 0 0 1 3 12V4.5A1.5 1.5 0 0 1 4.5 3H7" />
  </Icon>
)

export const FilterIcon = (p) => (
  <Icon {...p}>
    <path d="M4 6h16" />
    <path d="M7 12h10" />
    <path d="M10 18h4" />
  </Icon>
)

export const SetupIcon = (p) => (
  <Icon {...p}>
    <path d="M4 7h16" />
    <path d="M4 12h16" />
    <path d="M4 17h16" />
  </Icon>
)

export const SparklesIcon = (p) => (
  <Icon {...p}>
    <path d="m12 3 1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1L6.5 8.5l4.1-1.4z" />
    <path d="m18.5 14 .8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8z" />
    <path d="m5 15 .7 1.8L7.5 17.5l-1.8.7L5 20l-.7-1.8L2.5 17.5l1.8-.7z" />
  </Icon>
)

export default Icon
