<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useSessionStore } from '@/stores/session'
import { agentAPI } from '@/api/agent'
import MIcon from '@/components/icons/MIcon.vue'
import DesignWelcome from '@/components/design/DesignWelcome.vue'
import DesignTabsPanel from '@/components/design/DesignTabsPanel.vue'

const DESIGNER_AGENT = 'Designer'

const sessionStore = useSessionStore()

// ---- currentSession：直接从 store 读，不再走 useChatTimeline ----
const currentSession = computed(() => sessionStore.currentSession)
const isCurrentDesigner = computed(() => {
  const s = currentSession.value
  return !!s && (s.agent_name === DESIGNER_AGENT || s.name === DESIGNER_AGENT)
})

// ---- preview port（DesignCollabAgent 单例内置 server）----
const previewPort = ref(null)
const iframeKey = ref(0)
// 当前预览入口（相对 task 目录的路径，如 'output/index.html'）。
// 由 agent 调 refresh_preview(entry_path=...) 显式指定；在此之前不渲染 iframe。
const entryPath = ref('')

// welcome 屏显隐 —— 用本地 state 而不是从 currentSession 派生。
// 原因：从 ViewSelector 进入 Design View 时，currentSession 可能仍是上次在
// Collab View 选过的 Designer session，若用 isCurrentDesigner 控制欢迎屏会直接
// 跳过入口。本地 state 在 onMounted 重置为 true，保证每次进 Design View 都先
// 让用户选「新建 / 继续」。
const showWelcome = ref(true)

async function fetchPreviewPort() {
  try {
    const status = await agentAPI.getAgentStatus(DESIGNER_AGENT)
    if (status?.preview_port) {
      previewPort.value = status.preview_port
    }
  } catch (e) {
    console.warn('Failed to fetch Designer status:', e)
  }
}

// task_id = 当前 session 的 task_id；缺失时 previewUrl 留空，模板兜底分支处理
const currentTaskId = computed(() => currentSession.value?.task_id || '')

const previewUrl = computed(() => {
  if (!previewPort.value || !currentTaskId.value || !entryPath.value) return ''
  const rel = entryPath.value.replace(/^\/+/, '')
  return `http://127.0.0.1:${previewPort.value}/${currentTaskId.value}/${rel}`
})

function reloadIframe() {
  iframeKey.value++
}

// 切到旧 Designer session 时，后端 agent 还没 activate（用户没发消息），
// 不会有 refresh event 来恢复 preview 入口。这种情况下从磁盘 history.json 读
// 上次 refresh_preview 持久化的 metadata.preview_entry_path 兜底一次。
//
// 时机：只在 entryPath 为空时读 —— 一旦后端 activate 回放 refresh event，
// 或 agent 调了新的 refresh_preview，上面的 watch 会覆盖 entryPath，这里就不再回填。
async function loadPreviewEntryFromDisk() {
  if (entryPath.value) return  // 已有值（事件驱动设置），跳过
  const s = currentSession.value
  if (!s) return
  const agentSessionId = s.agent_session_id
  if (!agentSessionId) return

  // 直接从 Tauri Rust 端拿 matrix_world_path —— 重启后 pinia config store 还没 hydrate，
  // 但 Rust 端 config 是启动时就读好的，立即可用（参考 useTodo.js:20）
  let worldPath
  try {
    const config = await invoke('get_config')
    worldPath = config?.matrix_world_path
  } catch (e) {
    console.warn('[DesignView] get_config failed:', e)
    return
  }
  if (!worldPath) return

  const path = `${worldPath}/.matrix/sessions/${DESIGNER_AGENT}/${agentSessionId}/history.json`
  try {
    // 用自定义 Tauri command 读文件 —— @tauri-apps/plugin-fs 的 readFile 受 capability
    // scope 限制（.matrix/sessions 不在 allow-read-file scope 里）。read_text_file 是
    // 后端自定义 command，无 scope 限制（参考 useTodo.js:38 用法）
    const text = await invoke('read_text_file', { path })
    // 异步期间 currentSession 可能已切换（用户快速 A→B→C），或事件驱动已设置 entryPath
    // —— 两种情况都不能填，否则会把 A 的 entry 错塞到 C 的 view
    if (currentSession.value?.agent_session_id !== agentSessionId) return
    if (entryPath.value) return
    // history.json 含完整 chat history 可能很大，跳过 JSON.parse 整个对象，
    // 直接 regex 抓 metadata.preview_entry_path 一行（json.dumps 出来的格式固定）
    const m = text.match(/"preview_entry_path"\s*:\s*"([^"]*)"/)
    const ep = m ? m[1] : null
    if (ep) entryPath.value = ep
  } catch (e) {
    // 文件不存在 / 解析失败 → 留空，等 agent refresh_preview
  }
}

// 切换 session 时清空 entryPath（避免上个 session 的入口残留），并触发磁盘兜底
watch(currentSession, () => {
  entryPath.value = ''
  if (isCurrentDesigner.value) loadPreviewEntryFromDisk()
})


// ---- 监听 design 事件（只处理 refresh；screenshot/question 都在后端/DesignTabsPanel 处理）----
watch(() => sessionStore.lastSessionEvent, (evt) => {
  if (!evt || !currentSession.value) return
  if (evt.agent_name !== DESIGNER_AGENT) return
  const agentSessionId = currentSession.value.agent_session_id
  if (agentSessionId && evt.session_id !== agentSessionId) return

  const data = evt.data || {}
  if (data.event_type !== 'design') return

  if (data.event_name === 'refresh') {
    let detail = data.event_detail || {}
    if (typeof detail === 'string') {
      try { detail = JSON.parse(detail) } catch { detail = {} }
    }
    // refresh 事件由 agent 在 server 启动后发出，自带 preview_port —— 直接用，
    // 不再依赖 status 轮询时序（之前 watch(isCurrentDesigner) 抢跑会拿到 null）
    if (detail.preview_port) previewPort.value = detail.preview_port
    const path = detail.entry_path || ''
    if (path) entryPath.value = path
    reloadIframe()
  }
})

// ---- 导出 PPTX（ui_action）----
const exporting = ref(false)
const exportToast = ref(null)

async function handleExportPptx() {
  if (exporting.value) return
  exporting.value = true
  exportToast.value = null
  try {
    const result = await agentAPI.invokeAgentUIAction(DESIGNER_AGENT, 'export_pptx', {
      entryPath: entryPath.value,
      task_id: currentTaskId.value,
    })
    const r = result?.result || {}
    if (r.ok) {
      exportToast.value = {
        type: 'ok',
        text: `导出成功：${r.file || 'output/'}（${r.slides ?? '?'} slides, ${r.bytes ?? '?'} bytes）`,
      }
    } else {
      exportToast.value = { type: 'err', text: `导出失败：${r.error || '未知错误'}` }
    }
  } catch (e) {
    exportToast.value = { type: 'err', text: `导出失败：${e.message || e}` }
  } finally {
    exporting.value = false
    setTimeout(() => { exportToast.value = null }, 5000)
  }
}

// ---- welcome callbacks ----
function onWelcomeContinue(session) {
  sessionStore.selectSession(session)
  showWelcome.value = false  // 兜底：selectSession 同 session 不触发 watch
}

// 从 split view 回到 welcome 入口（「新建设计」按钮）—— 清掉 currentSession，
// 让 isCurrentDesigner 变 false，下次再选 session 时是干净状态
function backToWelcome() {
  sessionStore.clearCurrentSession()
  showWelcome.value = true
}

// ---- 生命周期 ----
onMounted(async () => {
  // 每次进 Design View 都强制重置到 welcome 屏（无论 currentSession 状态）
  showWelcome.value = true
  await fetchPreviewPort()
})

// 进入 Designer session 时：
//  - 关掉 welcome 屏（用户从 welcome 里选了 session，或 sendAndWaitForSession 完成）
//  - 顺带 fetch preview_port（agent 首次 activate 时才启动 server）
watch(isCurrentDesigner, (cur) => {
  if (cur) {
    if (showWelcome.value) showWelcome.value = false
    if (!previewPort.value) fetchPreviewPort()
  }
})
</script>

<template>
  <div class="design-view">
    <!-- welcome 屏（新 vs 继续）—— 显隐由本地 showWelcome 控制，不依赖 currentSession -->
    <DesignWelcome
      v-if="showWelcome"
      @continue="onWelcomeContinue"
    />

    <!-- split view（左 preview，右 tabs） -->
    <div v-else class="design-view__split">
      <!-- Left: Preview iframe -->
      <div class="design-view__preview-panel">
        <div class="design-view__preview-header">
          <button
            class="design-view__new-btn"
            @click="backToWelcome"
            title="新建设计（回到入口）"
          >
            <MIcon name="plus" />
          </button>
          <h3>预览</h3>
          <span v-if="previewUrl" class="design-view__preview-url">{{ previewUrl }}</span>
          <button
            class="design-view__export-btn"
            :disabled="exporting"
            @click="handleExportPptx"
            :title="exporting ? '导出中...' : '导出 PPTX'"
          >
            <MIcon name="file-down" />
            <span>{{ exporting ? '导出中...' : '导出 PPTX' }}</span>
          </button>
          <button class="design-view__reload-btn" @click="reloadIframe" title="刷新">
            <MIcon name="refresh-cw" />
          </button>
        </div>
        <div class="design-view__preview-body">
          <iframe
            v-if="previewUrl"
            :key="iframeKey"
            :src="previewUrl"
            class="design-view__iframe"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
          ></iframe>
          <div v-else class="design-view__preview-empty">
            <MIcon name="palette" />
            <span v-if="!previewPort">预览服务器未启动</span>
            <span v-else>等待 Designer 产出并调用 refresh_preview...</span>
          </div>
        </div>
      </div>

      <!-- Right: Multi-tab panel -->
      <div class="design-view__tabs-panel">
        <DesignTabsPanel />
      </div>
    </div>

    <!-- Export PPTX 结果 toast -->
    <div v-if="exportToast" class="design-view__toast" :class="`design-view__toast--${exportToast.type}`">
      {{ exportToast.text }}
    </div>
  </div>
</template>

<style scoped>
.design-view {
  width: 100%;
  height: 100%;
  display: flex;
  overflow: hidden;
}

/* Split view */
.design-view__split {
  flex: 1;
  display: flex;
  overflow: hidden;
}

/* Preview panel */
.design-view__preview-panel {
  width: 50%;
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.design-view__preview-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.design-view__preview-header h3 {
  font-size: var(--font-md);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  margin: 0;
}

.design-view__preview-url {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  margin-left: auto;
  font-family: monospace;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 200px;
}

.design-view__reload-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: transparent;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-secondary);
  cursor: pointer;
  flex-shrink: 0;
}

.design-view__reload-btn:hover {
  color: var(--text-primary);
  border-color: var(--accent);
}

.design-view__new-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  background: var(--accent);
  border: none;
  border-radius: var(--radius-sm);
  color: white;
  cursor: pointer;
  flex-shrink: 0;
  transition: opacity var(--duration-fast);
}

.design-view__new-btn:hover {
  opacity: 0.9;
}

.design-view__export-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-1) var(--spacing-3);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--font-xs);
  flex-shrink: 0;
  transition: opacity var(--duration-fast);
}

.design-view__export-btn:hover:not(:disabled) {
  opacity: 0.9;
}

.design-view__export-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.design-view__preview-body {
  flex: 1;
  background: var(--surface-secondary);
  overflow: hidden;
  position: relative;
}

.design-view__iframe {
  width: 100%;
  height: 100%;
  border: none;
  background: white;
}

.design-view__preview-empty {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-3);
  color: var(--text-tertiary);
  font-size: var(--font-sm);
}

/* Tabs panel (right) */
.design-view__tabs-panel {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  padding-left: var(--spacing-1);
}

/* Toast */
.design-view__toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  padding: var(--spacing-2) var(--spacing-4);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  z-index: 1100;
  max-width: 560px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  animation: toastSlide 0.25s var(--ease-out);
}

.design-view__toast--ok {
  background: var(--success, #10b981);
  color: white;
}

.design-view__toast--err {
  background: var(--error, #ef4444);
  color: white;
}

@keyframes toastSlide {
  from { opacity: 0; transform: translate(-50%, 8px); }
  to { opacity: 1; transform: translate(-50%, 0); }
}
</style>
