import { useUIStore } from '../../stores/uiStore'
import { useChatStore } from '../../stores/chatStore'

export function RoleSwitch() {
  const { role, setRole } = useUIStore()
  const { createConversation, setActiveConversation } = useChatStore()

  const handleRoleChange = (newRole: 'customer' | 'agent') => {
    if (newRole === role) return

    // 切换角色时创建新会话，避免上下文混淆
    setRole(newRole)
    const newConvId = createConversation()
    setActiveConversation(newConvId)
  }

  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800 rounded-lg">
      <span className="text-sm text-gray-600 dark:text-gray-400">视角：</span>
      <div className="flex gap-1">
        <button
          onClick={() => handleRoleChange('customer')}
          className={`px-3 py-1 text-sm rounded transition-colors ${
            role === 'customer'
              ? 'bg-blue-500 text-white'
              : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600'
          }`}
        >
          客户视角
        </button>
        <button
          onClick={() => handleRoleChange('agent')}
          className={`px-3 py-1 text-sm rounded transition-colors ${
            role === 'agent'
              ? 'bg-orange-500 text-white'
              : 'bg-white dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-600'
          }`}
        >
          客服视角
        </button>
      </div>
    </div>
  )
}
