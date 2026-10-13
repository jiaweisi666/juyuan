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

export default function SetupPage({ onToast }) {
  const [subTab, setSubTab] = useState('accounts')

  return (
    <div className="flex h-full flex-col">
      {/* 子标签栏 */}
      <div className="flex items-center gap-1 border-b border-line bg-surface-2/40 px-4 py-2">
        <button
          onClick={() => setSubTab('accounts')}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors ${
            subTab === 'accounts'
              ? 'bg-brand-soft text-brand-ink'
              : 'text-ink-3 hover:bg-surface hover:text-ink-2'
          }`}
        >
          <AccountsIcon size={14} />
          账号管理
        </button>
        <button
          onClick={() => setSubTab('models')}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12px] font-medium transition-colors ${
            subTab === 'models'
              ? 'bg-brand-soft text-brand-ink'
              : 'text-ink-3 hover:bg-surface hover:text-ink-2'
          }`}
        >
          <ModelsIcon size={14} />
          模型配置
        </button>
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-hidden">
        {subTab === 'accounts' && <AccountsPage onToast={onToast} />}
        {subTab === 'models' && <ModelsPage onToast={onToast} />}
      </div>
    </div>
  )
}
