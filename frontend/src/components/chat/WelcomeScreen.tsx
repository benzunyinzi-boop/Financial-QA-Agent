import { useChat } from '../../hooks/useChat'
import { useUIStore } from '../../stores/uiStore'
import { Info, AlertTriangle, ShoppingCart, FileBarChart, Shield, Users } from 'lucide-react'
import { RoleSwitch } from '../layout/RoleSwitch'

const customerQuestions = [
  {
    icon: Info,
    iconBg: 'dark:bg-blue-500/10 light:bg-blue-50',
    iconColor: 'dark:text-blue-400 light:text-blue-500',
    title: '产品对比',
    question: '百万医疗险和重疾险有什么区别？',
  },
  {
    icon: AlertTriangle,
    iconBg: 'dark:bg-amber-500/10 light:bg-amber-50',
    iconColor: 'dark:text-amber-400 light:text-amber-500',
    title: '保单查询',
    question: '我的保单什么时候到期？',
  },
  {
    icon: ShoppingCart,
    iconBg: 'dark:bg-green-500/10 light:bg-green-50',
    iconColor: 'dark:text-green-400 light:text-green-500',
    title: '投保咨询',
    question: '重疾险的等待期是多久？',
  },
  {
    icon: FileBarChart,
    iconBg: 'dark:bg-purple-500/10 light:bg-purple-50',
    iconColor: 'dark:text-purple-400 light:text-purple-500',
    title: '理赔指引',
    question: '如何申请理赔？',
  },
]

const agentQuestions = [
  {
    icon: Shield,
    iconBg: 'dark:bg-red-500/10 light:bg-red-50',
    iconColor: 'dark:text-red-400 light:text-red-500',
    title: '合规检查',
    question: '重疾险销售有哪些合规红线？',
  },
  {
    icon: Users,
    iconBg: 'dark:bg-blue-500/10 light:bg-blue-50',
    iconColor: 'dark:text-blue-400 light:text-blue-500',
    title: '客户查询',
    question: '查询保单 P20240005',
  },
  {
    icon: FileBarChart,
    iconBg: 'dark:bg-green-500/10 light:bg-green-50',
    iconColor: 'dark:text-green-400 light:text-green-500',
    title: '产品对比',
    question: '对比产品 CI-DEMO-001,MED-DEMO-001',
  },
  {
    icon: AlertTriangle,
    iconBg: 'dark:bg-amber-500/10 light:bg-amber-50',
    iconColor: 'dark:text-amber-400 light:text-amber-500',
    title: '投诉处理',
    question: '客户投诉理赔慢的标准话术是什么？',
  },
]

export function WelcomeScreen() {
  const { sendMessage } = useChat()
  const { role } = useUIStore()

  const quickQuestions = role === 'customer' ? customerQuestions : agentQuestions
  const title = role === 'customer' ? '你好，我是安心保险智能助手' : '你好，我是安心保险内部助手'
  const subtitle = role === 'customer'
    ? '专注于重疾险和医疗险的咨询服务，有什么可以帮你？'
    : '为客服坐席提供产品查询、话术建议、合规检查等支持'

  return (
    <div className="flex-1 flex items-center justify-center overflow-y-auto">
      <div className="max-w-2xl mx-auto px-6 text-center">
        {/* 角色切换器 */}
        <div className="mb-6 flex justify-center">
          <RoleSwitch />
        </div>

        <div className={`w-20 h-20 rounded-2xl flex items-center justify-center mx-auto mb-6 logo-pulse ${
          role === 'customer' ? 'bg-blue-500' : 'bg-orange-500'
        }`}>
          <svg className="w-10 h-10 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
          </svg>
        </div>

        <h2 className="text-2xl font-semibold dark:text-white light:text-gray-900 mb-2">
          {title}
        </h2>
        <p className="dark:text-gray-400 light:text-gray-500 mb-8">
          {subtitle}
        </p>

        <div className="grid grid-cols-2 gap-3">
          {quickQuestions.map((item) => (
            <div
              key={item.title}
              onClick={() => sendMessage(item.question)}
              className="quick-card rounded-xl p-4 cursor-pointer text-left"
            >
              <div className="flex items-start gap-3">
                <div className={`w-8 h-8 rounded-lg ${item.iconBg} flex items-center justify-center flex-shrink-0`}>
                  <item.icon className={`w-4 h-4 ${item.iconColor}`} />
                </div>
                <div>
                  <p className="text-sm font-medium dark:text-gray-200 light:text-gray-800">{item.title}</p>
                  <p className="text-xs dark:text-gray-400 light:text-gray-500 mt-1">{item.question}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
