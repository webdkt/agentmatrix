import { ref, computed, watch, nextTick, toValue } from 'vue'
import { useSessionStore } from '@/stores/session'
import { sessionAPI } from '@/api/session'

/**
 * Chat timeline composable — extracted from ChatHistory.vue
 * Handles event loading, parsing, classification, WebSocket incremental append,
 * optimistic send placeholders, ask-user logic, and auto-scroll.
 */
export function useChatTimeline({ userAgentName = ref('User') } = {}) {
  const sessionStore = useSessionStore()

  // ---- State ----
  const events = ref([])
  const isLoading = ref(false)
  const isLoadingMore = ref(false)
  const isAutoFilling = ref(false)
  const hasMoreOlder = ref(true)
  const error = ref(null)
  const messagesContainer = ref(null)
  const answer = ref('')
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
    hasMoreOlder.value = true

    try {
      const result = await sessionAPI.getSessionEvents(agentName, agentSessionId, 200)
      events.value = (result.events || []).map(parseEvent).filter(e => e.renderType !== 'skip')
      totalEventCount.value = result.total || 0
      sessionStore.updateCheckTimeLocal(session.session_id)
    } catch (err) {
      error.value = err.message
      console.error('Failed to load session events:', err)
    } finally {
      isLoading.value = false
      await nextTick()
      scrollToBottom()

      // If content doesn't fill the viewport, keep loading older
      isAutoFilling.value = true
      try {
        while (true) {
          const container = messagesContainer.value
          if (!container) break
          if (container.scrollHeight > container.clientHeight) break
          const loaded = await loadOlderEvents()
          if (!loaded) break
          await nextTick()
        }
      } finally {
        isAutoFilling.value = false
      }
    }
  }

  const loadOlderEvents = async () => {
    if (isLoadingMore.value || !hasMoreOlder.value || !currentSession.value) return false

    const session = currentSession.value
    const agentName = session.agent_name || session.name
    const agentSessionId = session.agent_session_id
    if (!agentName || !agentSessionId || events.value.length === 0) return false

    // Find the oldest loaded event's timestamp as cursor
    const oldest = events.value.reduce((min, e) =>
      e.timestamp < min ? e.timestamp : min, events.value[0].timestamp)

    isLoadingMore.value = true

    const container = messagesContainer.value
    const prevScrollHeight = container ? container.scrollHeight : 0

    try {
      const result = await sessionAPI.getSessionEvents(agentName, agentSessionId, 200, 'older', oldest)
      const olderEvents = (result.events || []).map(parseEvent).filter(e => e.renderType !== 'skip')

      if (olderEvents.length === 0) {
        hasMoreOlder.value = false
        return false
      }

      events.value = [...olderEvents, ...events.value]

      // Preserve scroll position (double nextTick for browser layout reflow)
      await nextTick()
      await nextTick()
      if (container) {
        container.scrollTop = container.scrollHeight - prevScrollHeight
      }

      return true
    } catch (err) {
      console.error('Failed to load older events:', err)
      return false
    } finally {
      isLoadingMore.value = false
    }
  }

  let _scrollRaf = null
  const onScroll = () => {
    if (_scrollRaf) return
    _scrollRaf = requestAnimationFrame(() => {
      _scrollRaf = null
      const container = messagesContainer.value
      if (!container) return
      if (container.scrollTop <= 50 && !isLoadingMore.value && !isAutoFilling.value && hasMoreOlder.value) {
        loadOlderEvents()
      }
    })
  }

  // ---- Scroll ----

  const scrollToBottom = () => {
    if (messagesContainer.value) {
      messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
    }
  }

  // ---- Session watcher ----

  watch(currentSession, async (newSession) => {
    events.value = []
    totalEventCount.value = 0
    hasMoreOlder.value = true

    if (newSession) {
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

    // exit_msg: mutate the last thought event's display mode instead of appending a new event
    if (evt.data.event_type === 'session' && evt.data.event_name === 'exit_msg') {
      const exitMsgType = evt.data.event_detail?.exit_msg_type
      if (exitMsgType) {
        for (let i = events.value.length - 1; i >= 0; i--) {
          if (events.value[i].renderType === 'thought') {
            events.value[i].renderType = 'bubble-agent'
            events.value[i].exitMsgType = exitMsgType
            break
          }
        }
      }
      return
    }

    const parsed = parseEvent(evt.data)
    if (parsed.renderType === 'skip') return

    // User messages are always sent from the frontend with a placeholder,
    // no need to append the backend echo — loadEvents() handles historical data on session switch
    if (parsed.renderType === 'bubble-user') return

    events.value.push(parsed)
    totalEventCount.value++
    nextTick(() => scrollToBottom())
  })

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

  return {
    // State
    events,
    isLoading,
    isLoadingMore,
    isAutoFilling,
    error,
    messagesContainer,
    answer,
    totalEventCount,
    // Computed
    currentSession,
    chatTimeline,
    hasContent,
    primaryAgentName,
    // Actions
    loadEvents,
    loadOlderEvents,
    onScroll,
    scrollToBottom,
    handleEmailSendStarted,
    handleEmailSendFailed,
    handleEmailSent,
  }
}
