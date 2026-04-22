<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useTerminal } from '@/composables/useTerminal'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: { type: String, default: null },
  minimized: { type: Boolean, default: true },
  parentWidth: { type: Number, default: 800 },
  parentHeight: { type: Number, default: 600 },
})

const emit = defineEmits(['toggle-minimize', 'close', 'update:position', 'update:size'])

const {
  terminalLines,
  terminalContainer,
  userInput,
  isExecuting,
  handleTerminalSubmit,
} = useTerminal({ agentName: () => props.agentName })

// ---- Position & Size ----
const pos = ref({ x: 0, y: 0 })
const size = ref({ w: 400, h: 300 })

// Initialize default positions
const updateDefaults = () => {
  const pw = props.parentWidth
  const ph = props.parentHeight
  if (props.minimized) {
    size.value = { w: Math.min(280, pw * 0.4), h: 60 }
    pos.value = { x: pw - size.value.w - 16, y: ph - size.value.h - 16 }
  } else {
    size.value = { w: Math.round(pw * 0.5), h: Math.round(ph * 0.5) }
    pos.value = { x: Math.round((pw - size.value.w) / 2), y: Math.round((ph - size.value.h) / 2) }
  }
}

// Reset position when toggling minimized/expanded
watch(() => props.minimized, () => updateDefaults())
watch([() => props.parentWidth, () => props.parentHeight], () => {
  // Clamp position to new bounds
  clampPosition()
})

onMounted(() => updateDefaults())

// ---- Drag ----
const isDragging = ref(false)
let dragStartX = 0, dragStartY = 0, dragOrigX = 0, dragOrigY = 0

const startDrag = (e) => {
  isDragging.value = true
  dragStartX = e.clientX
  dragStartY = e.clientY
  dragOrigX = pos.value.x
  dragOrigY = pos.value.y
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  e.preventDefault()
}

const onDrag = (e) => {
  if (!isDragging.value) return
  pos.value.x = dragOrigX + (e.clientX - dragStartX)
  pos.value.y = dragOrigY + (e.clientY - dragStartY)
  clampPosition()
}

const stopDrag = () => {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
}

// ---- Resize (expanded only) ----
const isResizing = ref(false)
let resizeStartX = 0, resizeStartY = 0, resizeOrigW = 0, resizeOrigH = 0

const startResize = (e) => {
  if (props.minimized) return
  isResizing.value = true
  resizeStartX = e.clientX
  resizeStartY = e.clientY
  resizeOrigW = size.value.w
  resizeOrigH = size.value.h
  document.addEventListener('mousemove', onResize)
  document.addEventListener('mouseup', stopResize)
  e.preventDefault()
  e.stopPropagation()
}

const onResize = (e) => {
  if (!isResizing.value) return
  size.value.w = Math.max(200, resizeOrigW + (e.clientX - resizeStartX))
  size.value.h = Math.max(100, resizeOrigH + (e.clientY - resizeStartY))
  clampPosition()
}

const stopResize = () => {
  isResizing.value = false
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
}

const clampPosition = () => {
  const pw = props.parentWidth
  const ph = props.parentHeight
  pos.value.x = Math.max(0, Math.min(pos.value.x, pw - size.value.w))
  pos.value.y = Math.max(0, Math.min(pos.value.y, ph - size.value.h))
}

const style = computed(() => ({
  position: 'absolute',
  left: `${pos.value.x}px`,
  top: `${pos.value.y}px`,
  width: `${size.value.w}px`,
  height: `${size.value.h}px`,
}))

onUnmounted(() => {
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.removeEventListener('mousemove', onResize)
  document.removeEventListener('mouseup', stopResize)
})
</script>

<template>
  <div
    class="agent-terminal"
    :class="{ 'agent-terminal--minimized': minimized, 'agent-terminal--dragging': isDragging }"
    :style="style"
  >
    <!-- Header / Drag handle -->
    <div class="agent-terminal__header" @mousedown="startDrag">
      <MIcon name="terminal" />
      <span class="agent-terminal__title">Terminal</span>
      <button class="agent-terminal__btn" @click.stop="$emit('toggle-minimize')" :title="minimized ? 'Expand' : 'Minimize'">
        <MIcon :name="minimized ? 'arrows-maximize' : 'arrows-minimize'" />
      </button>
      <button class="agent-terminal__btn" @click.stop="$emit('close')" title="Close">
        <MIcon name="x" />
      </button>
    </div>

    <!-- Output -->
    <div ref="terminalContainer" class="agent-terminal__output">
      <div v-if="terminalLines.length > 0" class="agent-terminal__pre">
        <div
          v-for="(entry, i) in terminalLines"
          :key="i"
          :class="['terminal-line', `terminal-line--${entry.type}`]"
        >
          <template v-if="entry.type === 'stdin' && entry.truncated">
            <span class="terminal-line__typewriter">{{ entry.collapsed ? entry.shortText : entry.text }}</span>
            <span class="terminal-line__toggle" @click="entry.collapsed = !entry.collapsed">
              {{ entry.collapsed ? '[show more]' : '[collapse]' }}
            </span>
          </template>
          <span v-else-if="entry.type === 'stdin'" class="terminal-line__typewriter">{{ entry.text }}</span>
          <template v-else-if="entry.truncated">
            {{ entry.collapsed ? entry.shortText : entry.text }}
            <span class="terminal-line__toggle" @click="entry.collapsed = !entry.collapsed">
              {{ entry.collapsed ? `[+${entry.hiddenLines} more lines]` : '[collapse]' }}
            </span>
          </template>
          <template v-else>{{ entry.text }}</template>
        </div>
        <div v-if="!isExecuting" class="terminal-line terminal-line--prompt">
          <span class="terminal-prompt-cursor">$&nbsp;<span class="terminal-cursor"></span></span>
        </div>
      </div>
      <div v-else class="agent-terminal__empty">
        <span class="terminal-prompt-cursor">$&nbsp;<span class="terminal-cursor"></span></span>
      </div>
    </div>

    <!-- Input (hidden when minimized) -->
    <div v-if="!minimized" class="agent-terminal__input">
      <span class="agent-terminal__prompt">$</span>
      <input
        v-model="userInput"
        type="text"
        :disabled="isExecuting"
        :placeholder="isExecuting ? 'Agent is running...' : 'Type a command...'"
        class="agent-terminal__field"
        @keydown.enter="handleTerminalSubmit"
      />
    </div>

    <!-- Resize handle (expanded only) -->
    <div v-if="!minimized" class="agent-terminal__resize-handle" @mousedown="startResize" />
  </div>
</template>

<style scoped>
.agent-terminal {
  z-index: 10;
  display: flex;
  flex-direction: column;
  background: #1e1e1e;
  border-radius: var(--radius-sm);
  box-shadow: 0 4px 24px rgba(0, 0, 0, 0.3);
  overflow: hidden;
  user-select: none;
}

.agent-terminal--dragging {
  opacity: 0.9;
}

.agent-terminal__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  padding: 4px var(--spacing-sm);
  background: #2d2d2d;
  cursor: grab;
  flex-shrink: 0;
  border-bottom: 1px solid #333;
}

.agent-terminal--dragging .agent-terminal__header {
  cursor: grabbing;
}

.agent-terminal__header .m-icon {
  font-size: var(--font-xs);
  color: #888;
}

.agent-terminal__title {
  flex: 1;
  font-size: 11px;
  font-weight: var(--font-medium);
  color: #aaa;
  letter-spacing: 0.03em;
}

.agent-terminal__btn {
  width: 22px;
  height: 22px;
  border: none;
  background: transparent;
  color: #888;
  cursor: pointer;
  border-radius: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-xs);
  transition: all 0.15s ease;
}

.agent-terminal__btn:hover {
  background: #444;
  color: #ddd;
}

.agent-terminal__output {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-xs) var(--spacing-sm);
  min-height: 0;
}

.agent-terminal__pre {
  margin: 0;
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.agent-terminal__empty {
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  color: #d4d4d4;
  padding: var(--spacing-xs);
}

.terminal-line {
  color: #d4d4d4;
}

.terminal-line--stdin {
  color: #6a9955;
  font-weight: var(--font-semibold);
}

.terminal-line--stderr {
  color: #f44747;
}

.terminal-line__toggle {
  color: #569cd6;
  cursor: pointer;
  font-size: 10px;
  margin-left: 4px;
}

.terminal-line__toggle:hover {
  text-decoration: underline;
}

.terminal-line__typewriter {
  display: inline-block;
  overflow: hidden;
  white-space: nowrap;
  animation: typewriter 0.4s steps(30, end) forwards;
  max-width: 0;
}

@keyframes typewriter {
  from { max-width: 0 }
  to { max-width: 100% }
}

.terminal-line--prompt {
  color: #d4d4d4;
}

.terminal-prompt-cursor {
  color: #6a9955;
}

.terminal-cursor {
  display: inline-block;
  width: 8px;
  height: 14px;
  background: #d4d4d4;
  vertical-align: text-bottom;
  animation: blink-cursor 1s step-end infinite;
}

@keyframes blink-cursor {
  50% { opacity: 0 }
}

.agent-terminal__input {
  display: flex;
  align-items: center;
  background: #1e1e1e;
  border-top: 1px solid #333;
  flex-shrink: 0;
}

.agent-terminal__prompt {
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  color: #6a9955;
  padding: 6px 0 6px var(--spacing-sm);
  flex-shrink: 0;
  user-select: none;
}

.agent-terminal__field {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: #d4d4d4;
  font-family: 'SF Mono', 'Menlo', 'Monaco', 'Consolas', monospace;
  font-size: 11px;
  padding: 6px var(--spacing-sm);
  caret-color: #d4d4d4;
}

.agent-terminal__field::placeholder {
  color: #555;
}

.agent-terminal__field:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.agent-terminal__resize-handle {
  position: absolute;
  right: 0;
  bottom: 0;
  width: 14px;
  height: 14px;
  cursor: nwse-resize;
  z-index: 1;
}

.agent-terminal__resize-handle::after {
  content: '';
  position: absolute;
  right: 3px;
  bottom: 3px;
  width: 8px;
  height: 8px;
  border-right: 2px solid #555;
  border-bottom: 2px solid #555;
}

.agent-terminal__resize-handle:hover::after {
  border-color: #888;
}
</style>
