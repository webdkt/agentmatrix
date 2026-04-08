<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  minWidth: {
    type: Number,
    default: 300
  },
  maxWidth: {
    type: Number,
    default: 600
  },
  currentWidth: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['update:width'])

const isDragging = ref(false)
const startX = ref(0)
const startWidth = ref(0)

function onMouseDown(e) {
  isDragging.value = true
  startX.value = e.clientX
  startWidth.value = props.currentWidth
  document.addEventListener('mousemove', onMouseMove)
  document.addEventListener('mouseup', onMouseUp)
  // Prevent text selection during drag
  e.preventDefault()
}

function onMouseMove(e) {
  if (!isDragging.value) return
  const deltaX = e.clientX - startX.value
  // Panel is on the right side, so:
  // - Drag left (deltaX < 0) = panel gets wider = subtract negative
  // - Drag right (deltaX > 0) = panel gets narrower = subtract positive
  const newWidth = Math.min(props.maxWidth, Math.max(props.minWidth, startWidth.value - deltaX))
  emit('update:width', newWidth)
}

function onMouseUp() {
  isDragging.value = false
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
}

// Cleanup on unmount
onUnmounted(() => {
  document.removeEventListener('mousemove', onMouseMove)
  document.removeEventListener('mouseup', onMouseUp)
})
</script>

<template>
  <div
    class="resizable-divider"
    :class="{ 'resizable-divider--dragging': isDragging }"
    @mousedown="onMouseDown"
  >
    <div class="resizable-divider__handle"></div>
  </div>
</template>

<style scoped>
.resizable-divider {
  position: relative;
  width: 4px;
  background: var(--neutral-200, #e5e0d8);
  cursor: col-resize;
  transition: background 0.15s ease;
  flex-shrink: 0;
  user-select: none;
}

.resizable-divider:hover {
  background: var(--neutral-300, #d4cfc7);
}

.resizable-divider--dragging {
  background: var(--accent-500, #6b4c3b);
}

.resizable-divider__handle {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 20px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.15s ease;
}

.resizable-divider:hover .resizable-divider__handle,
.resizable-divider--dragging .resizable-divider__handle {
  opacity: 1;
}

.resizable-divider__handle::before,
.resizable-divider__handle::after {
  content: '';
  position: absolute;
  width: 2px;
  height: 12px;
  background: var(--ink-400, #9a9590);
  border-radius: 1px;
}

.resizable-divider:hover .resizable-divider__handle::before,
.resizable-divider:hover .resizable-divider__handle::after {
  background: var(--ink-600, #4a4642);
}

.resizable-divider--dragging .resizable-divider__handle::before,
.resizable-divider--dragging .resizable-divider__handle::after {
  background: white;
}

.resizable-divider__handle::before {
  left: 5px;
}

.resizable-divider__handle::after {
  right: 5px;
}
</style>
