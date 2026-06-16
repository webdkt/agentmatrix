import { defineStore } from 'pinia'
import { ref } from 'vue'
import { serviceAPI } from '@/api/service'

export const useServiceStore = defineStore('service', () => {
  // ==================== State ====================

  // Service list view
  const services = ref([])
  const currentService = ref(null)       // {status, workers, actions}
  const loading = ref(false)
  const error = ref(null)

  // Event panel: null = activity mode, workerId = worker mode
  const selectedWorkerId = ref(null)

  // Activity feed (service-level events)
  const serviceEvents = ref([])

  // Per-worker events cache: {workerId: events[]}
  const workerEvents = ref({})
  const loadedWorkers = ref(new Set())

  // ==================== Actions: list & detail ====================

  async function fetchServices() {
    loading.value = true
    error.value = null
    try {
      const data = await serviceAPI.getServices()
      services.value = data.services || []
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function selectService(name) {
    loading.value = true
    error.value = null
    selectedWorkerId.value = null
    serviceEvents.value = []
    workerEvents.value = {}
    loadedWorkers.value = new Set()
    try {
      const data = await serviceAPI.getServiceDetail(name)
      currentService.value = data
      fetchServiceEvents(name)
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  function selectWorker(workerId) {
    selectedWorkerId.value = workerId
    if (workerId && !loadedWorkers.value.has(workerId)) {
      const svcName = currentService.value?.status?.name
      if (svcName) fetchWorkerEvents(svcName, workerId)
    }
  }

  function goBack() {
    selectedWorkerId.value = null
  }

  function reset() {
    currentService.value = null
    selectedWorkerId.value = null
    serviceEvents.value = []
    workerEvents.value = {}
    loadedWorkers.value = new Set()
  }

  // ==================== Actions: event fetching ====================

  async function fetchServiceEvents(name) {
    try {
      const data = await serviceAPI.getServiceEvents(name)
      serviceEvents.value = data.events || []
    } catch (e) {
      console.error('Failed to fetch service events:', e)
    }
  }

  async function fetchWorkerEvents(name, workerId) {
    try {
      const data = await serviceAPI.getWorkerEvents(name, workerId)
      workerEvents.value[workerId] = data.events || []
      loadedWorkers.value.add(workerId)
    } catch (e) {
      console.error('Failed to fetch worker events:', e)
    }
  }

  // ==================== Real-time event handler ====================

  // service-level 事件名 → scanning 状态
  const SCAN_START_EVENTS = new Set(['scan_started'])
  const SCAN_END_EVENTS = new Set(['scan_completed', 'scan_error', 'scan_skipped'])

  function handleServiceEvent(message) {
    const { event_type, event_name, data: eventData, source } = message
    const svcName = currentService.value?.status?.name

    // 先更新 list-side 状态（无论当前是否在 detail 视图）
    _updateListService(message)

    if (message.service !== svcName) return

    if (event_type === 'worker_status') {
      _updateWorkerStatus(eventData)
      return
    }

    const event = {
      event_type,
      event_name,
      event_detail: typeof eventData === 'string' ? eventData : JSON.stringify(eventData),
      timestamp: new Date().toISOString(),
    }

    if (event_type === 'service') {
      // 翻转 detail 的 scanning 标志
      if (SCAN_START_EVENTS.has(event_name)) {
        currentService.value.status.scanning = true
      } else if (SCAN_END_EVENTS.has(event_name)) {
        currentService.value.status.scanning = false
      }
      serviceEvents.value.push(event)
    } else if (source && source !== '__service__') {
      if (!workerEvents.value[source]) {
        workerEvents.value[source] = []
      }
      workerEvents.value[source].push(event)
    }
  }

  function _updateListService(message) {
    const { event_type, event_name, data, service } = message
    const svc = services.value.find(s => s.name === service)
    if (!svc) return

    if (event_type === 'worker_status') {
      if (!svc.workers) svc.workers = []
      const idx = svc.workers.findIndex(w => w.id === data.id)
      if (idx >= 0) {
        svc.workers[idx] = { ...svc.workers[idx], ...data }
      } else {
        svc.workers.push(data)
      }
      svc.working_count = svc.workers.filter(w => w.status === 'working').length
    } else if (event_type === 'service') {
      if (SCAN_START_EVENTS.has(event_name)) svc.scanning = true
      else if (SCAN_END_EVENTS.has(event_name)) svc.scanning = false
    }
  }

  function _updateWorkerStatus(workerInfo) {
    if (!currentService.value) return
    const workers = currentService.value.workers || []
    const idx = workers.findIndex(w => w.id === workerInfo.id)
    if (idx >= 0) {
      workers[idx] = { ...workers[idx], ...workerInfo }
    } else {
      workers.push(workerInfo)
    }
  }

  return {
    services, currentService, selectedWorkerId,
    serviceEvents, workerEvents, loadedWorkers,
    loading, error,
    fetchServices, selectService, selectWorker,
    goBack, reset,
    fetchServiceEvents, fetchWorkerEvents,
    handleServiceEvent,
  }
})
