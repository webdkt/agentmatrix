import { ref, computed } from 'vue'
import { API } from '@/api/client'
import { sessionAPI } from '@/api/session'
import { useSessionStore } from '@/stores/session'
import { useAutomationSpec } from '@/composables/useAutomationSpec'
import i18n from '@/i18n'

// Task ID generator matching Python format: {YYMMDDHHMM}-{subject}-{4char_rand}
function generateAutomationTaskId(system, process) {
  const now = new Date()
  const pad = (n, l = 2) => String(n).padStart(l, '0')
  const timeStr = [
    String(now.getFullYear()).slice(-2),
    pad(now.getMonth() + 1),
    pad(now.getDate()),
    pad(now.getHours()),
    pad(now.getMinutes()),
  ].join('')
  const subject = `auto-${system}-${process}`
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .slice(0, 10)
  const chars = 'abcdefghijklmnopqrstuvwxyz0123456789'
  const rand = Array.from({ length: 4 }, () => chars[Math.floor(Math.random() * chars.length)]).join('')
  return `${timeStr}-${subject}-${rand}`
}

export function useAutomationView() {
  const sessionStore = useSessionStore()

  // State machine: 'system-select' | 'process-select' | 'sending' | 'session'
  const state = ref('system-select')
  const selectedSystem = ref(null)
  const selectedProcess = ref(null)
  const targetAgentName = ref('Frank')

  // Automation tasks from DB
  const automationTasks = ref([])
  const tasksLoading = ref(false)

  // Filesystem access
  const spec = useAutomationSpec({ agentName: () => targetAgentName.value })

  // Load automation tasks from API
  let _taskLoadGen = 0

  async function loadAutomationTasks() {
    const gen = ++_taskLoadGen
    tasksLoading.value = true
    try {
      const data = await API.get('/api/automation/tasks', {
        params: { agent_name: targetAgentName.value }
      })
      if (gen !== _taskLoadGen) return
      automationTasks.value = data.tasks || []
    } catch (e) {
      if (gen !== _taskLoadGen) return
      console.error('[AutomationView] Failed to load tasks:', e)
      automationTasks.value = []
    } finally {
      if (gen === _taskLoadGen) tasksLoading.value = false
    }
  }

  // Enrich systems with task status
  const systemsWithStatus = computed(() => {
    return spec.systems.value.map(sys => {
      const tasks = automationTasks.value.filter(t => t.system_name === sys.name)
      const activeTask = tasks.find(t =>
        t.project_status === 'IN_PROGRESS' || t.project_status === 'WAITING_FOR_USER'
      )
      const latestTask = tasks.length > 0 ? tasks[0] : null
      return {
        ...sys,
        activeTask,
        latestTask,
        hasActive: !!activeTask,
        taskCount: tasks.length,
      }
    })
  })

  // Processes with status (lazy-loaded per system)
  const processes = ref([])
  const processesLoading = ref(false)

  const processesWithStatus = computed(() => {
    return processes.value.map(proc => {
      const tasks = automationTasks.value.filter(
        t => t.system_name === selectedSystem.value && t.process_name === proc.name
      )
      const activeTask = tasks.find(t =>
        t.project_status === 'IN_PROGRESS' || t.project_status === 'WAITING_FOR_USER'
      )
      const latestTask = tasks.length > 0 ? tasks[0] : null
      const terminalTask = tasks.find(t =>
        ['COMPLETED', 'STOPPED', 'FAILED'].includes(t.project_status)
      )
      return {
        ...proc,
        activeTask,
        latestTask,
        terminalTask,
        hasActive: !!activeTask,
        hasHistory: tasks.length > 0,
        taskCount: tasks.length,
      }
    })
  })

  // Search
  const systemSearch = ref('')
  const processSearch = ref('')

  const filteredSystems = computed(() => {
    const q = systemSearch.value.toLowerCase().trim()
    if (!q) return systemsWithStatus.value
    return systemsWithStatus.value.filter(s => s.name.toLowerCase().includes(q))
  })

  const filteredProcesses = computed(() => {
    const q = processSearch.value.toLowerCase().trim()
    if (!q) return processesWithStatus.value
    return processesWithStatus.value.filter(p => p.name.toLowerCase().includes(q))
  })

  // Abort flag for sending-state navigation
  let _sendingAbort = null
  // Generation counter for selectSystem race condition
  let _systemLoadGen = 0
  // Error message from last send attempt
  const sendError = ref('')

  // Actions
  async function init() {
    // loadSystems is called automatically by useAutomationSpec's watch(immediate)
    await loadAutomationTasks()
  }

  async function selectSystem(systemName) {
    selectedSystem.value = systemName
    state.value = 'process-select'
    processSearch.value = ''
    processesLoading.value = true
    const gen = ++_systemLoadGen
    try {
      const result = await spec.loadSystemProcesses(systemName)
      if (gen !== _systemLoadGen) return  // stale, discard
      processes.value = result
      await loadAutomationTasks()
    } catch (e) {
      if (gen !== _systemLoadGen) return
      console.error('[AutomationView] Failed to load processes:', e)
      processes.value = []
    } finally {
      if (gen === _systemLoadGen) processesLoading.value = false
    }
  }

  // Navigate directly to process list (skip system-select state)
  function navigateToProcessList(systemName) {
    // Abort any in-flight send
    if (_sendingAbort) {
      _sendingAbort.aborted = true
      _sendingAbort = null
    }
    selectedProcess.value = null
    selectedSystem.value = systemName
    state.value = 'process-select'
    processSearch.value = ''
    processesLoading.value = true
    const gen = ++_systemLoadGen
    spec.loadSystemProcesses(systemName)
      .then(result => {
        if (gen !== _systemLoadGen) return
        processes.value = result
      })
      .catch(e => {
        if (gen !== _systemLoadGen) return
        processes.value = []
        console.error(e)
      })
      .finally(() => {
        if (gen === _systemLoadGen) processesLoading.value = false
      })
    loadAutomationTasks()
  }

  async function selectProcess(processName) {
    // Abort any in-flight send and invalidate in-flight process loads
    if (_sendingAbort) {
      _sendingAbort.aborted = true
      _sendingAbort = null
    }
    _systemLoadGen++
    sendError.value = ''
    selectedProcess.value = processName
    state.value = 'sending'
    await startAutomation(selectedSystem.value, processName)
  }

  async function startAutomation(systemName, processName) {
    const taskId = generateAutomationTaskId(systemName, processName)
    const emailData = {
      recipient: targetAgentName.value,
      subject: `auto-${systemName}-${processName}`,
      body: i18n.global.t('automation.emailBody', { system: systemName, process: processName }),
      task_id: taskId,
    }

    // Record current session count before creating new one
    const prevCount = sessionStore.sessions.length

    // Create abort token for this send operation
    const abortToken = { aborted: false }
    _sendingAbort = abortToken

    try {
      const response = await sessionAPI.sendEmail('new', emailData)
      // Wait for the new session to appear (abortable)
      await waitForSession(response, prevCount, abortToken)
    } catch (e) {
      if (abortToken.aborted) return
      console.error('[AutomationView] Failed to start automation:', e)
      state.value = 'process-select'
    }
  }

  async function waitForSession(sendResponse, prevSessionCount, abortToken) {
    const maxWait = 15000
    const startTime = Date.now()

    // Backend returns { success, email: { task_id, ... } }
    const task_id = sendResponse?.email?.task_id

    while (Date.now() - startTime < maxWait) {
      if (abortToken.aborted) return

      await sessionStore.fetchSessions()

      const match = task_id
        ? sessionStore.sessions.find(s => s.session_id === task_id || s.readable_id === task_id)
        : null

      // Fallback: detect any new session appeared
      const newSession = !match && sessionStore.sessions.length > prevSessionCount
        ? sessionStore.sessions[0]
        : null

      const found = match || newSession
      if (found) {
        sessionStore.selectSession(found)
        state.value = 'session'
        await loadAutomationTasks()
        return
      }
      await new Promise(r => setTimeout(r, 500))
    }

    if (!abortToken.aborted) {
      console.warn('[AutomationView] Timeout waiting for session')
      sendError.value = i18n.global.t('automation.error.sessionTimeout')
      state.value = 'process-select'
    }
  }

  async function resumeTask(task) {
    let session = sessionStore.sessions.find(s => s.session_id === task.session_id)
    if (!session) {
      // Sessions may not be loaded yet; try fetching
      try {
        await sessionStore.fetchSessions()
        session = sessionStore.sessions.find(s => s.session_id === task.session_id)
      } catch {}
    }
    if (session) {
      sessionStore.selectSession(session)
      selectedSystem.value = task.system_name
      selectedProcess.value = task.process_name
      state.value = 'session'
    } else {
      console.warn(`[AutomationView] Session not found for task ${task.session_id}`)
    }
  }

  async function goBack() {
    // Abort any in-flight send operation
    if (_sendingAbort) {
      _sendingAbort.aborted = true
      _sendingAbort = null
    }
    sendError.value = ''

    if (state.value === 'process-select') {
      state.value = 'system-select'
      selectedSystem.value = null
      processes.value = []
      await loadAutomationTasks()
    } else if (state.value === 'session' || state.value === 'sending') {
      state.value = 'system-select'
      selectedSystem.value = null
      selectedProcess.value = null
      processes.value = []
      sessionStore.clearCurrentSession()
      await loadAutomationTasks()
    }
  }

  async function reset() {
    if (_sendingAbort) {
      _sendingAbort.aborted = true
      _sendingAbort = null
    }
    sendError.value = ''
    state.value = 'system-select'
    selectedSystem.value = null
    selectedProcess.value = null
    processes.value = []
    systemSearch.value = ''
    processSearch.value = ''
    sessionStore.clearCurrentSession()
    await loadAutomationTasks()
  }

  return {
    // State
    state,
    selectedSystem,
    selectedProcess,
    targetAgentName,
    // Data
    systemsWithStatus,
    filteredSystems,
    filteredProcesses,
    processesLoading,
    tasksLoading,
    automationTasks,
    isInitialLoad: spec.isInitialLoad,
    loadError: spec.error,
    sendError,
    // Search
    systemSearch,
    processSearch,
    // Filesystem
    rootDir: computed(() => spec.rootDir.value),
    // Actions
    init,
    selectSystem,
    selectProcess,
    navigateToProcessList,
    resumeTask,
    goBack,
    reset,
    loadAutomationTasks,
  }
}
