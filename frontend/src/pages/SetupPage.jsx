/**
 * SetupPage.jsx - 模型与账号合一配置页。
 *
 * 上半部分：模型配置（平台状态、同步底座模型）
 * 下半部分：账号管理（账号池、登录导入）
 */

import { useState } from 'react'
import ModelsPage from './ModelsPage.jsx'
import AccountsPage from './AccountsPage.jsx'
import { ModelsIcon, AccountsIcon } from '../components/icons.jsx'

const SUB_TABS = [
  { id: 'accounts', label: '账号管理', icon: AccountsIcon },
  { id: 'models', label: '模型配置', icon: ModelsIcon },
]

export default function SetupPage({ onToast }) {
  const [subTab, setSubTab] = useState('accounts')

  return (
    <div className="flex h-full flex-col">
      {/* 子标签栏 */}
      <div className="flex items-center gap-2 border-b border-white/70 bg-white/40 px-5 py-2.5 backdrop-blur-xl">
        <div className="flex items-center gap-1 rounded-xl border border-line/70 bg-white/70 p-1 shadow-[0_1px_2px_rgba(18,54,105,0.03)]">
          {SUB_TABS.map((t) => {
            const Icon = t.icon
            const active = subTab === t.id
            return (
              <button
                key={t.id}
                onClick={() => setSubTab(t.id)}
                className={`ui-press flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-[12px] font-medium transition-all ${
                  active
                    ? 'bg-gradient-to-br from-[#eaf4ff] to-[#f7fbff] text-brand-ink shadow-[inset_0_0_0_1px_rgba(47,134,246,0.12)]'
                    : 'text-ink-3 hover:text-ink-2'
                }`}
              >
                <Icon size={14} className={active ? 'text-brand' : ''} />
                {t.label}
              </button>
            )
          })}
        </div>
        <span className="ml-1 hidden text-[11px] text-ink-3 sm:inline">
          管理聚元的账号池与模型接入
        </span>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-hidden">
        {subTab === 'accounts' && <AccountsPage onToast={onToast} />}
        {subTab === 'models' && <ModelsPage onToast={onToast} />}
      </div>
    </div>
  )
}
