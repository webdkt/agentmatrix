import { ref, computed, watch, nextTick, toValue } from 'vue'
import { useSessionStore } from '@/stores/session'
import { useAgentStore } from '@/stores/agent'
import { sessionAPI } from '@/api/session'

/**
 * Chat timeline composable — extracted from ChatHistory.vue
 * Handles event loading, parsing, classification, WebSocket incremental append,
 * optimistic send placeholders, ask-user logic, and auto-scroll.
 */
export function useChatTimeline({ userAgentName = ref('User') } = {}) {
  const sessionStore = useSessionStore()
  const agentStore = useAgentStore()

  // ---- State ----
  const events = ref([])
  const isLoading = ref(false)
  const isLoadingMore = ref(false)
  const error = ref(null)
  const messagesContainer = ref(null)
  const answer = ref('')
  const currentAgentStatuses = ref({})
  const previousHistoryLengths = ref({})
  const hasMoreEvents = ref(false)
  const totalEventCount = ref(0)

  // ---- Computed ----
  const currentSession = computed(() => sessionStore.currentSession)

  const chatTimeline = computed(() => {
    return events.value
      .map(event => ({
        type: event.renderType,
        id: event.id,
        timestamp: event.timestamp,
        data: event,
      }))
      .sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp))
  })

  const hasContent = computed(() => chatTimeline.value.length > 0)

  const pendingQuestion = computed(() => {
    if (!currentSession.value) return null
    return sessionStore.getPendingQuestion(currentSession.value.session_id)
  })

  const primaryAgentName = computed(() => {
    if (!currentSession.value) return null
    return currentSession.value.agent_name || currentSession.value.name || null
  })

  // ---- Event parsing ----

  function parseEvent(raw) {
    let detail = {}
    if (raw.event_detail) {
      try {
        detail = typeof raw.event_detail === 'string' ? JSON.parse(raw.event_detail) : raw.event_detail
      } catch {
        detail = {}
      }
    }
    return {
      id: raw.id,
      timestamp: raw.timestamp,
      eventType: raw.event_type,
      eventName: raw.event_name,
      detail,
      renderType: classifyEvent(raw.event_type, raw.event_name, detail),
    }
  }

  function classifyEvent(type, name, detail) {
    if (type === 'email') {
      const isReceived = name === 'received'
      const isSent = name === 'sent'
      if (isReceived && detail.sender === toValue(userAgentName)) {
        return 'bubble-user'
      }
      if (isSent && detail.recipient === toValue(userAgentName)) {
        return 'bubble-agent'
      }
      return 'agent-comm'
    }
    if (type === 'think') return 'thought'
    if (type === 'action') {
      if (name === 'detected') return 'skip'
      if (detail.action_name === 'send_internal_mail') return 'skip'
      return 'pill'
    }
    if (type === 'session') {
      if (name === 'activated' || name === 'deactivated') return 'session-time'
      return 'skip'
    }
    return 'system'
  }

  // ---- Event loading ----

  const loadEvents = async (session) => {
    const agentName = session.agent_name || session.name
    const agentSessionId = session.agent_session_id
    if (!agentName || !agentSessionId) {
      console.warn('useChatTimeline: missing agent_name or agent_session_id', session)
      return
    }

    isLoading.value = true
    error.value = null

    try {
      const result = await sessionAPI.getSessionEvents(agentName, agentSessionId, 200, 0, 'latest')
      events.value = (result.events || []).map(parseEvent).filter(e => e.renderType !== 'skip')
      totalEventCount.value = result.total || 0
      hasMoreEvents.value = events.value.length < totalEventCount.value
      sessionStore.markSessionRead(session.session_id)
    } catch (err) {
      error.value = err.message
      console.error('Failed to load session events:', err)
    } finally {
      isLoading.value = false
      await nextTick()
      scrollToBottom()
    }
  }

  const loadOlderEvents = async () => {
    if (isLoadingMore.value || !hasMoreEvents.value || !currentSession.value) return

    const session = currentSession.value
    const agentName = session.agent_name || session.name
    const agentSessionId = session.agent_session_id
    if (!agentName || !agentSessionId || events.value.length === 0) return

    // 用最早的事件时间戳作为 cursor
    const oldestEvent = events.value.reduce((oldest, e) => {
      return new Date(e.timestamp) < new Date(oldest.timestamp) ? e : oldest
    }, events.value[0])
    const before = oldestEvent.timestamp

    isLoadingMore.value = true

    // 记住当前滚动位置和高度
    const container = messagesContainer.value
    const prevScrollHeight = container ? container.scrollHeight : 0

    try {
      const result = await sessionAPI.getSessionEvents(agentName, agentSessionId, 200, 0, 'older', before)
      const olderEvents = (result.events || []).map(parseEvent).filter(e => e.renderType !== 'skip')

      if (olderEvents.length === 0) {
        hasMoreEvents.value = false
      } else {
        // prepend 到头部
        events.value = [...olderEvents, ...events.value]
        totalEventCount.value = result.total || totalEventCount.value
        hasMoreEvents.value = events.value.length < totalEventCount.value

        // 保持滚动位置不变（prepend 后恢复）
        await nextTick()
        if (container) {
          const newScrollHeight = container.scrollHeight
          container.scrollTop = newScrollHeight - prevScrollHeight
        }
      }
    } catch (err) {
      console.error('Failed to load older events:', err)
    } finally {
      isLoadingMore.value = false
    }
  }

  const onScroll = () => {
    const container = messagesContainer.value
    if (!container) return
    if (container.scrollTop <= 0 && hasMoreEvents.value && !isLoadingMore.value) {
      loadOlderEvents()
    }
  }

  // ---- Scroll ----

  const scrollToBottom = () => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  }

  // ---- Session watcher ----

  watch(currentSession, async (newSession, oldSession) => {
    const isPlaceholderToReal = oldSession?._isPlaceholder && newSession && !newSession._isPlaceholder

    if (!isPlaceholderToReal) {
      events.value = []
      currentAgentStatuses.value = {}
      hasMoreEvents.value = false
      totalEventCount.value = 0
    }

    if (newSession) {
      if (newSession._isPlaceholder) {
        isLoading.value = false
        return
      }
      if (isPlaceholderToReal) {
        isLoading.value = false
        return
      }
      await loadEvents(newSession)
    }
    answer.value = ''
  }, { immediate: true })

  // ---- Incremental append via lastSessionEvent ----

  watch(() => sessionStore.lastSessionEvent, (evt) => {
    if (!evt || !currentSession.value) return
    const agentName = currentSession.value.agent_name || currentSession.value.name
    const agentSessionId = currentSession.value.agent_session_id

    const isMatch = agentSessionId
      ? (evt.agent_name === agentName && evt.session_id === agentSessionId)
      : (evt.agent_name === agentName)
    if (!isMatch) return

    const parsed = parseEvent(evt.data)
    if (parsed.renderType === 'skip') return

    if (parsed.eventType === 'email' && parsed.eventName === 'received' && parsed.detail.sender === toValue(userAgentName)) {
      const phIdx = events.value.findIndex(e => e.detail?._isPlaceholder && e.detail.body_preview === parsed.detail.body_preview)
      if (phIdx !== -1) {
        events.value.splice(phIdx, 1, parsed)
      } else {
        events.value.push(parsed)
        totalEventCount.value++
      }
      nextTick(() => scrollToBottom())
      return
    }

    events.value.push(parsed)
    totalEventCount.value++
    nextTick(() => scrollToBottom())
  })

  // ---- Agent status watcher ----

  watch(() => agentStore.agents, (agents) => {
    if (!currentSession.value) return
    const sessionId = currentSession.value.session_id

    Object.entries(agents).forEach(([agentName, agentData]) => {
      const status = agentData.status || 'IDLE'
      if (status === 'IDLE') {
        delete currentAgentStatuses.value[agentName]
        return
      }
      currentAgentStatuses.value[agentName] = {
        status,
        agentName,
        isOnCurrentSession: agentData.current_user_session_id === sessionId,
        otherSessionId: agentData.current_user_session_id && agentData.current_user_session_id !== sessionId
          ? agentData.current_user_session_id
          : null,
      }
      const history = agentData.status_history || []
      previousHistoryLengths.value[agentName] = history.length
    })
  }, { deep: true })

  // ---- Email send handlers ----

  const handleEmailSendStarted = ({ placeholder }) => {
    events.value.push({
      id: placeholder.id || `placeholder-${Date.now()}`,
      timestamp: new Date().toISOString(),
      eventType: 'email',
      eventName: 'received',
      detail: {
        body_preview: placeholder.body || '',
        recipient: placeholder.recipient || '',
        sender: toValue(userAgentName),
        subject: placeholder.subject || '',
        _isPlaceholder: true,
      },
      renderType: 'bubble-user',
    })
    totalEventCount.value++
    nextTick(() => scrollToBottom())
  }

  const handleEmailSendFailed = ({ placeholderId }) => {
    const idx = events.value.findIndex(e => e.id === placeholderId)
    if (idx !== -1) {
      events.value.splice(idx, 1)
      totalEventCount.value = Math.max(0, totalEventCount.value - 1)
    }
  }

  const handleEmailSent = (payload) => {
    // no-op — placeholder stays until backend replaces it
  }

  // ---- Ask user ----

  const handleAgentQuestionSubmit = async () => {
    if (!answer.value.trim() || !currentSession.value) return
    const sessionId = currentSession.value.session_id
    try {
      await sessionStore.submitAskUserAnswer(sessionId, answer.value)
      answer.value = ''
    } catch (err) {
      console.error('Failed to submit answer:', err)
      alert('Failed to submit answer: ' + err.message)
    }
  }

  return {
    // State
    events,
    isLoading,
    isLoadingMore,
    error,
    messagesContainer,
    answer,
    currentAgentStatuses,
    hasMoreEvents,
    totalEventCount,
    // Computed
    currentSession,
    chatTimeline,
    hasContent,
    pendingQuestion,
    primaryAgentName,
    // Actions
    loadEvents,
    loadOlderEvents,
    onScroll,
    scrollToBottom,
    handleEmailSendStarted,
    handleEmailSendFailed,
    handleEmailSent,
    handleAgentQuestionSubmit,
  }
}
