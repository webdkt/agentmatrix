import { ref, computed, watch, onUnmounted } from 'vue'

/**
 * Karaoke-style scrolling event display logic.
 *
 * Shows 3 events at a time: previous (fading), current (full), coming (typewriter).
 *
 * New messages appear in the "coming" slot with typewriter effect,
 * then scroll up to "current" position when complete.
 */
export function useKaraokeScroll(events, getEventText) {
  const isDetailOpen = ref(false)

  // The index of the "current" event — always tracks the latest
  const currentIndex = computed(() => Math.max(0, events.value.length - 1))

  // ---- Typewriter state ----
  const typewriterQueue = ref([])
  const typewriterEvent = ref(null)
  const isTyping = ref(false)
  const displayedText = ref('')
  let typewriterTimer = null

  const TYPING_SPEED = 30 // ms per character

  // ---- Typewriter queue ----
  function enqueueTypewriter(event) {
    typewriterQueue.value.push(event)
    if (!isTyping.value) {
      processNextInQueue()
    }
  }

  function processNextInQueue() {
    if (typewriterQueue.value.length === 0) {
      typewriterEvent.value = null
      return
    }
    const event = typewriterQueue.value.shift()
    typewriterEvent.value = event
    startTypewriter()
  }

  function startTypewriter() {
    const fullText = getEventText(typewriterEvent.value)
    displayedText.value = ''
    isTyping.value = true

    let i = 0
    typewriterTimer = setInterval(() => {
      if (i < fullText.length) {
        displayedText.value = fullText.slice(0, i + 1)
        i++
      } else {
        clearInterval(typewriterTimer)
        typewriterTimer = null
        onTypewriterComplete()
      }
    }, TYPING_SPEED)
  }

  function onTypewriterComplete() {
    isTyping.value = false

    // Immediately add event to messages and clear typewriter
    // Let TransitionGroup handle the scroll animation
    const completedEvent = typewriterEvent.value
    typewriterEvent.value = null
    events.value.push(completedEvent)

    // Process next in queue after a short delay
    setTimeout(() => {
      processNextInQueue()
    }, 100)
  }

  // Extract 3 events around the current index
  const karaokeTriple = computed(() => {
    const idx = currentIndex.value
    const list = events.value
    const result = []

    // previous
    if (idx > 0) {
      result.push({ ...list[idx - 1], _slot: 'previous' })
    }
    // current
    if (list.length > 0) {
      result.push({ ...list[idx], _slot: 'current' })
    }
    // coming — typewriter or placeholder
    if (typewriterEvent.value) {
      result.push({
        ...typewriterEvent.value,
        _slot: 'coming',
        _typewriter: true,
        _displayedText: displayedText.value,
        _isTyping: isTyping.value,
      })
    } else {
      result.push({ _slot: 'coming', _placeholder: true, id: '__coming__' })
    }

    return result
  })

  // ---- Reset (clear typewriter queue + messages) ----
  function reset() {
    if (typewriterTimer) {
      clearInterval(typewriterTimer)
      typewriterTimer = null
    }
    typewriterQueue.value = []
    typewriterEvent.value = null
    isTyping.value = false
    displayedText.value = ''
    events.value.splice(0)
  }

  // ---- Detail window sync ----
  function onDetailOpen() {
    isDetailOpen.value = true
  }

  function onDetailClose() {
    isDetailOpen.value = false
  }

  // ---- Cleanup ----
  onUnmounted(() => {
    if (typewriterTimer) {
      clearInterval(typewriterTimer)
      typewriterTimer = null
    }
  })

  return {
    karaokeTriple,
    isTyping,
    enqueueTypewriter,
    reset,
    onDetailOpen,
    onDetailClose,
  }
}
