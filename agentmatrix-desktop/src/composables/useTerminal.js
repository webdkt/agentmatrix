import { ref, nextTick, onMounted, watch, toValue } from 'vue'
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
  const userInput = ref('')
  const isExecuting = ref(false)

  const handleBashOutput = (data) => {
    const stream = data?.data?.stream
    const line = data?.data?.line
    if (!line) return

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
    const cmd = userInput.value.trim()
    if (!cmd || !toValue(agentName) || isExecuting.value) return

    if (isBlacklisted(cmd)) {
      terminalLines.value.push({
        type: 'stderr',
        text: `Command '${cmd.split(/\s+/)[0]}' is not supported (interactive programs require a real terminal)`
      })
      userInput.value = ''
      return
    }

    isExecuting.value = true
    userInput.value = ''

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
    }
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
  })

  return {
    terminalLines,
    terminalContainer,
    userInput,
    isExecuting,
    handleTerminalSubmit,
    scrollTerminalToBottom,
  }
}
