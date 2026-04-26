import { ref, nextTick, onMounted, onUnmounted, watch, toValue } from 'vue'
import { useWebSocketStore } from '@/stores/websocket'
import { agentAPI } from '@/api/agent'

const MAX_TERMINAL_LINES = 500
const STDIN_MAX_CHARS = 200
const OUTPUT_MAX_LINES = 15

const INTERACTIVE_BLACKLIST = [
  'vi', 'vim', 'nvim', 'nano', 'emacs',
  'top', 'htop', 'btop', 'iotop',
  'less', 'more', 'man',
  'watch', 'tail -f',
  'python', 'python3', 'node', 'irb', 'php -a',
  'ssh', 'telnet', 'ftp', 'sftp',
]

/**
 * Terminal composable — extracted from CollabPanel.vue
 * Manages terminal output lines, user input, bash output handling, and WebSocket listener.
 */
export function useTerminal({ agentName } = {}) {
  const websocketStore = useWebSocketStore()

  const terminalLines = ref([])
  const terminalContainer = ref(null)
  const currentInput = ref('')  // 用户正在输入的内容（用于显示）
  const isExecuting = ref(false)
  const inputSpan = ref(null)    // contenteditable span 的引用

  const handleBashOutput = (data) => {
    const stream = data?.data?.stream
    const line = data?.data?.line
    if (!line) return

    // 关键：如果是 stdin，说明是后端执行的命令
    if (stream === 'stdin' && line) {
      // 清空用户正在输入的内容
      currentInput.value = ''

      // 将命令作为 stdin 行添加到输出
      terminalLines.value.push({
        type: 'stdin',
        text: line,
        truncated: false,
        collapsed: false
      })

      nextTick(() => {
        scrollTerminalToBottom()
      })
      return
    }

    // 其他输出（stdout/stderr）正常处理
    const entry = { type: stream || 'stdout', text: line, truncated: false, collapsed: true }

    if (entry.type === 'stdin' && line.length > STDIN_MAX_CHARS) {
      entry.truncated = true
      entry.shortText = line.slice(0, STDIN_MAX_CHARS) + '...'
    }

    if (entry.type !== 'stdin' && line.split('\n').length > 1) {
      const lines = line.split('\n')
      if (lines.length > OUTPUT_MAX_LINES) {
        entry.truncated = true
        entry.shortText = lines.slice(0, OUTPUT_MAX_LINES).join('\n')
        entry.hiddenLines = lines.length - OUTPUT_MAX_LINES
      }
    }

    terminalLines.value.push(entry)
    if (terminalLines.value.length > MAX_TERMINAL_LINES) {
      terminalLines.value = terminalLines.value.slice(-MAX_TERMINAL_LINES)
    }
    nextTick(scrollTerminalToBottom)
  }

  const isBlacklisted = (cmd) => {
    const first = cmd.trim().split(/\s+/)[0].toLowerCase()
    return INTERACTIVE_BLACKLIST.includes(first)
  }

  const handleTerminalSubmit = async () => {
    const cmd = currentInput.value.trim()
    if (!cmd || !toValue(agentName) || isExecuting.value) return

    if (isBlacklisted(cmd)) {
      terminalLines.value.push({
        type: 'stderr',
        text: `Command '${cmd.split(/\s+/)[0]}' is not supported (interactive programs require a real terminal)`
      })
      currentInput.value = ''
      // 同步到 contenteditable
      syncInputToDOM()
      return
    }

    isExecuting.value = true
    currentInput.value = ''  // 清空输入（但后端会发送 stdin 回来）
    syncInputToDOM()

    try {
      const result = await agentAPI.terminalExec(toValue(agentName), cmd)
      if (result.timeout) {
        terminalLines.value.push({
          type: 'stderr',
          text: '[Command timed out after 10s]'
        })
      }
    } catch (err) {
      terminalLines.value.push({
        type: 'stderr',
        text: `[Error: ${err.message}]`
      })
    } finally {
      isExecuting.value = false
      nextTick(() => {
        focusInput()
        scrollTerminalToBottom()
      })
    }
  }

  // 新增：按键处理
  const handleKeyDown = (event) => {
    if (event.key === 'Enter') {
      event.preventDefault()
      handleTerminalSubmit()
    } else if (event.key === 'c' && event.ctrlKey) {
      // Ctrl+C 中断命令（可选功能）
      event.preventDefault()
      // TODO: 实现中断逻辑
    }
    // 其他按键（字母、数字、符号）由 contenteditable 自动处理
  }

  // 新增：同步输入内容到 contenteditable
  const syncInputToDOM = () => {
    if (inputSpan.value && document.activeElement === inputSpan.value) {
      if (inputSpan.value.textContent !== currentInput.value) {
        // 保存光标位置
        const selection = window.getSelection()
        const range = selection.getRangeAt(0)
        const cursorOffset = range ? range.startOffset : 0

        inputSpan.value.textContent = currentInput.value

        // 恢复光标位置
        if (currentInput.value) {
          range.setStart(inputSpan.value, Math.min(cursorOffset, currentInput.value.length))
          range.setEnd(inputSpan.value, Math.min(cursorOffset, currentInput.value.length))
        } else {
          range.setStart(inputSpan.value, 0)
          range.setEnd(inputSpan.value, 0)
        }
        selection.removeAllRanges()
        selection.addRange(range)
      }
    }
  }

  // 监听 currentInput 变化，同步到 DOM
  watch(currentInput, () => {
    syncInputToDOM()
  })

  // 新增：聚焦输入区域
  const focusInput = () => {
    if (inputSpan.value && document.activeElement !== inputSpan.value) {
      inputSpan.value.focus()
      // 将光标移动到末尾
      const range = document.createRange()
      const selection = window.getSelection()
      range.selectNodeContents(inputSpan.value)
      range.collapse(false)
      selection.removeAllRanges()
      selection.addRange(range)
    }
  }

  // 新增：处理 contenteditable 输入
  const handleInput = (event) => {
    const text = event.target.textContent
    currentInput.value = text
  }

  function scrollTerminalToBottom() {
    if (terminalContainer.value) {
      terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight
    }
  }

  // Clear terminal when agent changes
  watch(() => toValue(agentName), (newName, oldName) => {
    if (newName !== oldName) {
      terminalLines.value = []
    }
  })

  onMounted(() => {
    websocketStore.registerListener('COLLAB_BASH_OUTPUT', handleBashOutput)
    // 自动聚焦输入框
    nextTick(() => {
      focusInput()
    })
  })

  return {
    terminalLines,
    terminalContainer,
    currentInput,
    isExecuting,
    inputSpan,
    handleKeyDown,
    handleInput,
    handleTerminalSubmit,
    focusInput,
    scrollTerminalToBottom,
  }
}
