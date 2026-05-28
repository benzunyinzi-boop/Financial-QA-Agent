import type { Theme } from '../types'

const API_BASE = '/api/v1'

export interface StreamChunk {
  type: 'token' | 'tool' | 'done' | 'error'
  content?: string
  toolName?: string
  toolPhase?: 'start' | 'end'
  message?: string
}

/**
 * 真实流式聊天 API（SSE）
 * 后端返回带事件类型的 SSE：event: token / tool / done / error
 */
export async function* streamChat(
  conversationId: string,
  message: string,
  role: 'customer' | 'agent' = 'customer',
  signal?: AbortSignal
): AsyncGenerator<StreamChunk> {
  const response = await fetch(`${API_BASE}/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ conversation_id: conversationId, message, role }),
    signal,
  })

  if (!response.ok) {
    throw new Error(`HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })

    // SSE 事件以两个换行符分隔
    let eventEndIdx
    while ((eventEndIdx = buffer.indexOf('\n\n')) !== -1) {
      const rawEvent = buffer.slice(0, eventEndIdx)
      buffer = buffer.slice(eventEndIdx + 2)

      const event = parseSseEvent(rawEvent)
      if (event) yield event
    }
  }
}

function parseSseEvent(raw: string): StreamChunk | null {
  let eventType = 'message'
  let dataStr = ''

  for (const line of raw.split('\n')) {
    if (line.startsWith('event: ')) {
      eventType = line.slice(7).trim()
    } else if (line.startsWith('data: ')) {
      dataStr += line.slice(6)
    }
  }

  if (!dataStr) return null

  try {
    const data = JSON.parse(dataStr)
    if (eventType === 'token') {
      return { type: 'token', content: data.content || '' }
    }
    if (eventType === 'tool') {
      return { type: 'tool', toolName: data.name, toolPhase: data.phase }
    }
    if (eventType === 'done') {
      return { type: 'done' }
    }
    if (eventType === 'error') {
      return { type: 'error', message: data.message }
    }
  } catch {
    return null
  }

  return null
}

// Mock stream for development（保留作为离线 fallback）
export async function* mockStreamChat(message: string): AsyncGenerator<string> {
  const responses: Record<string, string> = {
    default: '根据知识库的信息，我来为您解答这个问题。扫地机器人是一种智能家居设备，能够自动清扫地面灰尘和碎屑。如果您有更具体的问题，欢迎继续提问。',
    回充: '扫地机器人无法正常回充通常有以下原因：\n\n**常见原因：**\n- 充电座周围有障碍物，影响红外信号接收\n- 充电触片脏污或氧化\n- 机器人距离充电座过远\n\n**解决步骤：**\n1. 清理充电座周围 1.5 米内的障碍物\n2. 用干布擦拭充电触片\n3. 确保充电座两侧各留出 0.5 米空间\n4. 将机器人放在距充电座 2 米内重新尝试',
    功能: '扫地机器人的主要功能包括：\n\n1. **自动清扫** - 智能规划路径，覆盖全屋\n2. **避障功能** - 红外/激光传感器避开障碍物\n3. **自动回充** - 电量低时自动返回充电座\n4. **定时清扫** - 设置每日清扫计划\n5. **APP 远程控制** - 手机端实时查看和操控\n6. **多种清扫模式** - 标准/强力/静音模式切换',
    选购: '选购扫地机器人建议关注以下几点：\n\n1. **导航方式** - 激光导航 > 视觉导航 > 随机碰撞\n2. **吸力大小** - 建议 2000Pa 以上\n3. **续航时间** - 大户型选 150 分钟以上\n4. **噪音水平** - 65dB 以下较为安静\n5. **是否带拖地** - 扫拖一体更省事\n6. **预算范围** - 1500-3000 元性价比最高',
    报告: '正在为您生成本月使用报告...\n\n📊 **2025年5月使用报告**\n\n| 指标 | 数据 |\n|------|------|\n| 清扫次数 | 28 次 |\n| 总清扫面积 | 2,450 m² |\n| 平均每次时长 | 45 分钟 |\n| 耗电量 | 12.5 kWh |\n\n**使用建议：** 本月使用频率良好，建议每周清理一次尘盒和滤网以保持最佳吸力。',
  }

  let response = responses.default
  for (const [key, value] of Object.entries(responses)) {
    if (key !== 'default' && message.includes(key)) {
      response = value
      break
    }
  }

  const chars = response.split('')
  for (const char of chars) {
    await new Promise((resolve) => setTimeout(resolve, 20 + Math.random() * 30))
    yield char
  }
}

export function getStoredTheme(): Theme {
  return (localStorage.getItem('theme') as Theme) || 'dark'
}

export function setStoredTheme(theme: Theme) {
  localStorage.setItem('theme', theme)
}
