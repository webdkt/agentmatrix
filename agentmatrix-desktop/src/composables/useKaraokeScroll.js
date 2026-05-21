import { ref, computed, watch, onUnmounted } from 'vue'

/**
 * Karaoke-style scrolling event display logic.
 *
 * Shows 3 events at a time: previous (fading), current (full), coming (hint/placeholder).
 *
 * Modes:
 *   - Auto-scroll (default): tracks latest event, new messages animate in
 *   - Paused (hover): freezes display, accumulates unread count
 *   - Detail open: pauses without unread accumulation
 */
export function useKaraokeScroll(events) {
  const isAutoScrolling = ref(true)
  const isDetailOpen = ref(false)
  const unreadCount = ref(0)

  // The index of the "current" event — auto-scrolling always tracks the latest
  const currentIndex = computed(() => Math.max(0, events.value.length - 1))

  // The frozen index when paused
  const frozenIndex = ref(currentIndex.value)

  const activeIndex = computed(() => {
    return isAutoScrolling.value ? currentIndex.value : frozenIndex.value
  })

  // Track new events while paused
  watch(currentIndex, (newIdx, oldIdx) => {
    if (!isAutoScrolling.value && !isDetailOpen.value && newIdx > oldIdx) {
      unreadCount.value += (newIdx - oldIdx)
    }
  })

  // Extract 3 events around the active index
  const karaokeTriple = computed(() => {
    const idx = activeIndex.value
    const list = events.value
    if (list.length === 0) return []

    const result = []
    // previous
    if (idx > 0) {
      result.push({ ...list[idx - 1], _slot: 'previous' })
    }
    // current
    result.push({ ...list[idx], _slot: 'current' })
    // coming — the actual next message if it exists
    if (idx < list.length - 1) {
      result.push({ ...list[idx + 1], _slot: 'coming' })
    } else {
      // No next message yet — show a placeholder "coming" slot
      result.push({ _slot: 'coming', _placeholder: true, id: '__coming__' })
    }

    return result
  })

  /** Pause auto-scroll (called on mouseenter) */
  function pauseAutoScroll() {
    if (isDetailOpen.value) return
    isAutoScrolling.value = false
    frozenIndex.value = currentIndex.value
  }

  /** Resume auto-scroll (called on mouseleave) */
  function resumeAutoScroll() {
    if (isDetailOpen.value) return
    isAutoScrolling.value = true
    unreadCount.value = 0
  }

  function onDetailOpen() {
    isDetailOpen.value = true
    isAutoScrolling.value = false
    frozenIndex.value = currentIndex.value
  }

  function onDetailClose() {
    isDetailOpen.value = false
    isAutoScrolling.value = true
    unreadCount.value = 0
  }

  onUnmounted(() => {
  })

  return {
    karaokeTriple,
    isAutoScrolling,
    isDetailOpen,
    unreadCount,
    pauseAutoScroll,
    resumeAutoScroll,
    onDetailOpen,
    onDetailClose,
  }
}
