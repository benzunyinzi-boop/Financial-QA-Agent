import { Moon, Sun, Database, MessageSquare, Menu } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { useTheme } from '../../hooks/useTheme'
import { useUIStore } from '../../stores/uiStore'

export function Header() {
  const { theme, toggleTheme } = useTheme()
  const location = useLocation()
  const { setSidebarMobileOpen } = useUIStore()

  return (
    <header className="h-16 flex items-center justify-between px-4 md:px-6 border-b dark:border-dark-border light:border-gray-200 theme-transition dark:bg-dark-bg light:bg-gray-50">
      <div className="flex items-center gap-3 md:gap-6 min-w-0">
        <button
          onClick={() => setSidebarMobileOpen(true)}
          className="md:hidden p-2 rounded-lg dark:hover:bg-dark-card light:hover:bg-gray-200 transition-colors"
          title="打开菜单"
        >
          <Menu className="w-5 h-5 dark:text-gray-300 light:text-gray-700" />
        </button>

        <div className="flex items-center gap-2 md:gap-3 min-w-0">
          <div className="w-8 h-8 rounded-lg gradient-bg flex items-center justify-center logo-pulse flex-shrink-0">
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
          </div>
          <h1 className="text-lg font-semibold dark:text-white light:text-gray-900 truncate">安心问答</h1>
          <span className="hidden sm:inline text-xs dark:text-gray-500 light:text-gray-400 dark:bg-dark-card light:bg-gray-100 px-2 py-0.5 rounded-full">
            保险智答
          </span>
        </div>

        {/* 导航链接 */}
        <nav className="flex items-center gap-1 md:gap-2">
          <Link
            to="/"
            className={`flex items-center gap-1.5 md:gap-2 px-2 md:px-3 py-1.5 rounded-lg text-sm transition-colors ${
              location.pathname === '/'
                ? 'dark:bg-dark-card light:bg-gray-100 dark:text-white light:text-gray-900'
                : 'dark:text-gray-400 light:text-gray-600 dark:hover:bg-dark-card light:hover:bg-gray-100'
            }`}
          >
            <MessageSquare className="w-4 h-4" />
            <span className="hidden sm:inline">聊天</span>
          </Link>
          <Link
            to="/knowledge"
            className={`flex items-center gap-1.5 md:gap-2 px-2 md:px-3 py-1.5 rounded-lg text-sm transition-colors ${
              location.pathname === '/knowledge'
                ? 'dark:bg-dark-card light:bg-gray-100 dark:text-white light:text-gray-900'
                : 'dark:text-gray-400 light:text-gray-600 dark:hover:bg-dark-card light:hover:bg-gray-100'
            }`}
          >
            <Database className="w-4 h-4" />
            <span className="hidden sm:inline">知识库</span>
          </Link>
        </nav>
      </div>

      <button
        onClick={toggleTheme}
        className="p-2 rounded-lg dark:hover:bg-dark-card light:hover:bg-gray-200 transition-colors flex-shrink-0"
        title="切换主题"
      >
        {theme === 'dark' ? (
          <Moon className="w-5 h-5 text-gray-400" />
        ) : (
          <Sun className="w-5 h-5 text-gray-600" />
        )}
      </button>
    </header>
  )
}
