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
const expanded = ref(false)
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
    expanded.value = false
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
        expanded.value = true
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
    <div v-if="isLoading" class="loading-state"><MIcon name="loader" class="spinner" /> 加载中...</div>
    <div v-else-if="loadError" class="error-state">{{ loadError }}</div>

    <template v-else>
      <div :class="['card', { expanded }]">
        <div class="card-header" @click="expanded = !expanded">
          <div class="card-title-row">
            <span class="card-key">http_proxy</span>
            <span class="card-display">HTTP Proxy</span>
            <button
              class="toggle-chip"
              :class="{ on: isEnabled }"
              @click.stop="toggleEnable"
            >
              {{ isEnabled ? 'On' : 'Off' }}
            </button>
          </div>
          <div v-if="!expanded" class="card-summary">
            <template v-if="form.host">
              {{ form.host }}:{{ form.port || '0' }}
            </template>
            <template v-else>
              <span class="placeholder">{{ isEnabled ? '已配置' : '未配置' }}</span>
            </template>
          </div>
          <span class="expand-icon" :class="{ rotated: expanded }"><MIcon name="chevron-down" /></span>
        </div>

        <div v-if="expanded" class="card-form" @click.stop>
          <div class="field-row">
            <div class="field flex-2">
              <label>Host</label>
              <input v-model="form.host" class="input" placeholder="proxy.example.com" @input="trackChange" />
            </div>
            <div class="field flex-0">
              <label>Port</label>
              <input v-model="form.port" class="input" placeholder="8080" @input="trackChange" />
            </div>
          </div>

          <div class="card-actions">
            <button class="btn-text" @click="testConnection" :disabled="isTesting || !isEnabled">
              <MIcon name="plug-connected" style="font-size:12px;margin-right:4px" />
              {{ isTesting ? '测试中...' : '测试连接' }}
            </button>
            <div style="flex:1" />
            <button class="btn-text" @click="expanded = false">取消</button>
            <button class="btn-text primary" @click="save" :disabled="isSaving">{{ isSaving ? '保存中...' : '保存' }}</button>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.config-section {
  display: flex;
  flex-direction: column;
}

.loading-state, .error-state {
  padding: var(--spacing-8);
  text-align: center;
  color: var(--text-tertiary);
  font-size: var(--font-sm);
}

.spinner { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.card {
  background: white;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--duration-base) var(--ease-out);
}

.card.expanded {
  box-shadow: var(--shadow-md);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  cursor: pointer;
  min-height: 48px;
  border-radius: 10px;
  transition: background-color var(--duration-base) var(--ease-out);
}

.card:not(.expanded) .card-header:hover {
  background-color: var(--surface-secondary);
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  flex: 1;
  min-width: 0;
}

.card-key {
  font-family: 'SF Mono', 'Menlo', monospace;
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.card-display {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
}

.toggle-chip {
  margin-left: auto;
  padding: 2px 10px;
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

.card-summary {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: right;
  margin-left: var(--spacing-3);
  margin-right: var(--spacing-1);
}

.placeholder { color: var(--text-quaternary); font-style: italic; }

.expand-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  color: var(--text-quaternary);
  font-size: 14px;
  flex-shrink: 0;
  transition: transform var(--duration-base) var(--ease-out);
  pointer-events: none;
}

.expand-icon.rotated {
  transform: rotate(180deg);
}

.card-form {
  padding: 16px 18px 18px;
  border-top: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field-row {
  display: flex;
  gap: var(--spacing-3);
}

.flex-2 { flex: 2; }
.flex-0 { width: 100px; flex-shrink: 0; }

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.field-row {
  display: flex;
  gap: var(--spacing-3);
}

.flex-2 { flex: 2; }
.flex-0 { width: 100px; flex-shrink: 0; }

.input {
  width: 100%;
  padding: var(--spacing-2) var(--spacing-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
  font-size: var(--font-sm);
  color: var(--text-primary);
  outline: none;
  transition: border-color var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out);
}

.input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
  background: var(--surface-base);
}
.input::placeholder { color: var(--text-quaternary); }

.card-actions {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding-top: var(--spacing-2);
}

.btn-text {
  display: inline-flex;
  align-items: center;
  padding: var(--spacing-1) var(--spacing-2);
  background: none; border: none;
  font-size: var(--font-sm); color: var(--text-secondary);
  cursor: pointer; border-radius: var(--radius-md);
}

.btn-text:hover { background: var(--surface-hover); color: var(--text-primary); }
.btn-text.primary { color: var(--accent); font-weight: var(--font-medium); }
.btn-text.primary:hover { color: var(--accent-hover); }
.btn-text:disabled { opacity: 0.5; cursor: not-allowed; }
</style>