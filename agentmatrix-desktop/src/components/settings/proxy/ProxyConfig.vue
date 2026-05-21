<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'
import MIcon from '@/components/icons/MIcon.vue'

const settingsStore = useSettingsStore()
const uiStore = useUIStore()

const isLoading = ref(false)
const isSaving = ref(false)
const isTesting = ref(false)
const loadError = ref(null)
const isEnabled = ref(false)
const hasChanges = ref(false)

const form = reactive({
  host: '',
  port: '',
})

const hasConfig = computed(() => !!(form.host || form.port))

async function load() {
  isLoading.value = true
  loadError.value = null
  try {
    const config = await settingsStore.loadProxyConfig()
    if (config) {
      form.host = config.host || ''
      form.port = (config.port || config.port === 0) ? String(config.port) : ''
      isEnabled.value = config.enabled || false
    }
  } catch (e) {
    console.error('Failed to load proxy config:', e)
    loadError.value = e.message
  } finally {
    isLoading.value = false
  }
}

async function save() {
  if (!hasChanges.value) return
  isSaving.value = true
  try {
    await settingsStore.updateProxyConfig({
      enabled: isEnabled.value,
      host: form.host,
      port: parseInt(form.port) || 0,
    })
    hasChanges.value = false
    uiStore.showNotification('Proxy config saved', 'success')
  } catch (e) {
    uiStore.showNotification('Save failed: ' + e.message, 'error')
  } finally {
    isSaving.value = false
  }
}

async function toggleEnable() {
  try {
    if (isEnabled.value) {
      await settingsStore.disableProxy()
      isEnabled.value = false
    } else {
      if (!hasConfig.value) {
        return
      }
      await settingsStore.enableProxy()
      isEnabled.value = true
    }
  } catch (e) {
    uiStore.showNotification('Failed to toggle proxy', 'error')
  }
}

async function testConnection() {
  isTesting.value = true
  try {
    const result = await settingsStore.testProxyConnection()
    uiStore.showNotification(result.message || (result.success ? 'Connection OK' : 'Connection failed'), result.success ? 'success' : 'error')
  } catch (e) {
    uiStore.showNotification('Test failed: ' + e.message, 'error')
  } finally {
    isTesting.value = false
  }
}

function trackChange() { hasChanges.value = true }

onMounted(load)

defineExpose({ save: () => { if (hasChanges.value) save() } })
</script>

<template>
  <div class="config-section">
    <div v-if="isLoading" class="loading-state">
      <MIcon name="loader" class="spinner" />
      <span>Loading...</span>
    </div>
    <div v-else-if="loadError" class="error-state">
      <p>{{ loadError }}</p>
      <button class="retry-btn" @click="load">Retry</button>
    </div>

    <template v-else>
      <div class="section-group">
        <div class="section-group-header">
          <div class="group-header-left">
            <MIcon name="shield" :size="14" class="group-icon" />
            <span>网络代理</span>
          </div>
          <button
            class="toggle-chip"
            :class="{ on: isEnabled }"
            @click="toggleEnable"
          >
            {{ isEnabled ? 'On' : 'Off' }}
          </button>
        </div>

        <div class="sec">
          <div class="sec-side">
            <div class="sec-icon">
              <MIcon name="shield" :size="16" />
            </div>
            <div class="sec-text">
              <div class="sec-title">HTTP Proxy</div>
              <div class="sec-desc">配置 HTTP 代理服务器，用于网络请求转发。启用后所有外部请求将通过此代理。</div>
            </div>
          </div>

          <div class="sec-main">
            <div class="sec-row">
              <div class="fi flex-2">
                <label class="fi-lbl">Host</label>
                <input v-model="form.host" class="fi-inp" placeholder="proxy.example.com" @input="trackChange" />
              </div>
              <div class="fi flex-0">
                <label class="fi-lbl">Port</label>
                <input v-model="form.port" class="fi-inp" placeholder="8080" @input="trackChange" />
              </div>
            </div>

            <div class="sec-actions">
              <button
                class="btn-text secondary"
                :disabled="isTesting || !isEnabled"
                @click="testConnection"
              >
                <MIcon name="plug-connected" :size="12" />
                {{ isTesting ? 'Testing...' : 'Test Connection' }}
              </button>
              <button
                class="btn-text"
                :disabled="isSaving || !hasChanges"
                @click="save"
              >
                {{ isSaving ? 'Saving...' : 'Save' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
/* ═══════════════════════════════════════
   STATES
   ═══════════════════════════════════════ */
.loading-state, .error-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-12);
  color: var(--text-tertiary);
  font-size: var(--font-sm);
}

.error-state {
  flex-direction: column;
  gap: var(--spacing-3);
}

.error-state p {
  color: var(--error);
  font-size: var(--font-sm);
}

.retry-btn {
  padding: var(--spacing-1) var(--spacing-3);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
  color: var(--text-secondary);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.retry-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.spinner { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* ═══════════════════════════════════════
   SECTION GROUP
   ═══════════════════════════════════════ */
.section-group {
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
}

.section-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  letter-spacing: var(--tracking-wide);
}

.group-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-icon {
  color: var(--text-tertiary);
}

/* ─── Toggle chip ─── */
.toggle-chip {
  padding: 3px 12px;
  border-radius: 10px;
  border: 1px solid var(--border-strong);
  background: var(--surface-hover);
  color: var(--text-tertiary);
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.toggle-chip:hover {
  background: var(--surface-active);
}

.toggle-chip.on {
  background: color-mix(in srgb, var(--success) 10%, transparent);
  border-color: color-mix(in srgb, var(--success) 40%, transparent);
  color: var(--success);
}

.toggle-chip.on:hover {
  background: color-mix(in srgb, var(--success) 18%, transparent);
}

/* ═══════════════════════════════════════
   SECTION
   ═══════════════════════════════════════ */
.sec {
  display: grid;
  grid-template-columns: 200px 1fr;
  padding: 20px 20px;
}

/* ─── Left side ─── */
.sec-side {
  display: flex;
  gap: 12px;
  padding-right: 20px;
}

.sec-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--accent-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  flex-shrink: 0;
}

.sec-text {
  padding-top: 2px;
  min-width: 0;
}

.sec-title {
  font-size: var(--font-base);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin-bottom: 4px;
}

.sec-desc {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  line-height: var(--leading-relaxed);
}

/* ─── Right side: form fields ─── */
.sec-main {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sec-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 14px;
}

/* ═══════════════════════════════════════
   FIELDS
   ═══════════════════════════════════════ */
.fi {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.fi-lbl {
  font-size: var(--font-sm);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  letter-spacing: 0.04em;
}

.fi-inp {
  width: 100%;
  padding: 8px 12px;
  background: var(--surface-secondary);
  border: 1.5px solid #B0B0B4;
  border-radius: var(--radius-sm);
  font-size: var(--font-base);
  color: var(--text-primary);
  transition: all var(--duration-base) var(--ease-out);
  caret-color: var(--accent);
  outline: none;
}

.fi-inp::placeholder { color: var(--text-quaternary); }

.fi-inp:focus {
  outline: none;
  border-color: var(--accent);
  border-width: 3px;
  padding: 7px 11px;
  background: var(--surface-base);
  box-shadow: 0 0 0 3px var(--accent-muted);
}

/* ═══════════════════════════════════════
   FLEX UTILITIES
   ═══════════════════════════════════════ */
.flex-2 { flex: 2; }
.flex-0 { width: 100px; flex-shrink: 0; }

/* ═══════════════════════════════════════
   ACTIONS
   ═══════════════════════════════════════ */
.sec-actions {
  display: flex;
  justify-content: flex-end;
  align-items: center;
  gap: var(--spacing-2);
  padding-top: 6px;
}

.btn-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 6px 14px;
  background: var(--text-primary);
  color: var(--surface-base);
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-bold);
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.btn-text:hover:not(:disabled) { background: var(--accent); }
.btn-text:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-text.secondary {
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-strong);
}

.btn-text.secondary:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
  background: var(--accent-muted);
}
</style>
