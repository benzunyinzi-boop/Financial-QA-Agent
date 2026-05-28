import { useCallback, useRef } from 'react'
import { useChatStore } from '../stores/chatStore'
import { useUIStore } from '../stores/uiStore'
import { streamChat, mockStreamChat } from '../lib/api'
import { generateId } from '../lib/utils'
import type { Message } from '../types'

const TOOL_LABELS: Record<string, string> = {
  search_knowledge: '正在检索知识库...',
  get_current_date: '正在获取日期...',
  get_my_policies: '正在查询您的保单...',
  get_my_policy_detail: '正在查询保单详情...',
  get_my_claim_progress: '正在查询理赔进度...',
  query_any_policy: '正在查询保单...',
  query_customer_profile: '正在查询客户档案...',
  compare_products: '正在对比产品...',
  check_compliance: '正在检查合规...',
}

export function useChat() {
  const {
    activeConversationId,
    isStreaming,
    createConversation,
    addMessage,
    updateLastAssistantMessage,
    setStreaming,
    setToolStatus,
  } = useChatStore()

  const { role } = useUIStore()

  const abortRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(
    async (content: string) => {
      if (isStreaming || !content.trim()) return

      let convId = activeConversationId
      if (!convId) {
        convId = createConversation()
      }

      const userMessage: Message = {
        id: generateId(),
        role: 'user',
        content: content.trim(),
        createdAt: new Date(),
      }
      addMessage(convId, userMessage)

      const assistantMessage: Message = {
        id: generateId(),
        role: 'assistant',
        content: '',
        createdAt: new Date(),
      }
      addMessage(convId, assistantMessage)

      setStreaming(true)
      setToolStatus(null)
      let accumulated = ''

      const controller = new AbortController()
      abortRef.current = controller

      try {
        for await (const chunk of streamChat(convId, content, role, controller.signal)) {
          if (chunk.type === 'token' && chunk.content) {
            accumulated += chunk.content
            updateLastAssistantMessage(convId, accumulated)
          } else if (chunk.type === 'tool') {
            if (chunk.toolPhase === 'start' && chunk.toolName) {
              const label = TOOL_LABELS[chunk.toolName] || `正在调用 ${chunk.toolName}...`
              setToolStatus(label)
            } else if (chunk.toolPhase === 'end') {
              setToolStatus(null)
            }
          } else if (chunk.type === 'error') {
            const errMsg = chunk.message || '服务异常'
            accumulated += `\n\n⚠️ ${errMsg}`
            updateLastAssistantMessage(convId, accumulated)
          } else if (chunk.type === 'done') {
            break
          }
        }
      } catch (err) {
        // 真实 API 失败时降级到 mock，确保用户体验
        console.error('[useChat] streaming error, falling back to mock:', err)
        if (!accumulated) {
          for await (const char of mockStreamChat(content)) {
            accumulated += char
            updateLastAssistantMessage(convId, accumulated)
          }
        }
      } finally {
        setStreaming(false)
        setToolStatus(null)
        abortRef.current = null
      }
    },
    [activeConversationId, isStreaming, role, createConversation, addMessage, updateLastAssistantMessage, setStreaming, setToolStatus]
  )

  const stopStreaming = useCallback(() => {
    abortRef.current?.abort()
    setStreaming(false)
    setToolStatus(null)
  }, [setStreaming, setToolStatus])

  return { sendMessage, stopStreaming, isStreaming }
}
