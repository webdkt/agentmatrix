<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'
import MIcon from '@/components/icons/MIcon.vue'

const settingsStore = useSettingsStore()
const uiStore = useUIStore()

const isLoading = ref(false)
const isSaving = ref(false)
const isEnabled = ref(false)
const hasChanges = ref(false)
const loadError = ref(null)
const expanded = ref(false)

const form = reactive({
  matrix_mailbox: '',
  user_mailbox: '',
  imap_host: '',
  imap_port: '993',
  imap_user: '',
  imap_password: '',
  smtp_host: '',
  smtp_port: '587',
  smtp_user: '',
  smtp_password: '',
})

function toFrontend(backend) {
  if (!backend) return null
  const ep = backend.email_proxy || backend
  const userMb = ep.user_mailbox
  const userMailboxStr = Array.isArray(userMb) ? userMb.join(', ') : (userMb || '')
  return {
    matrix_mailbox: ep.matrix_mailbox || '',
    user_mailbox: userMailboxStr,
    imap_host: ep.imap?.host || '',
    imap_port: ep.imap?.port?.toString() || '993',
    imap_user: ep.imap?.user || '',
    imap_password: ep.imap?.password || '',
    smtp_host: ep.smtp?.host || '',
    smtp_port: ep.smtp?.port?.toString() || '587',
    smtp_user: ep.smtp?.user || '',
    smtp_password: ep.smtp?.password || '',
  }
}

function toBackend() {
  let userMailbox = form.user_mailbox.trim()
  if (userMailbox.includes(',')) {
    userMailbox = userMailbox.split(',').map(s => s.trim()).filter(Boolean)
  }
  return {
    email_proxy: {
      enabled: isEnabled.value,
      matrix_mailbox: form.matrix_mailbox.trim(),
      user_mailbox: userMailbox,
      imap: {
        host: form.imap_host.trim(),
        port: parseInt(form.imap_port) || 993,
        user: form.imap_user.trim(),
        password: form.imap_password,
      },
      smtp: {
        host: form.smtp_host.trim(),
        port: parseInt(form.smtp_port) || 587,
        user: form.smtp_user.trim(),
        password: form.smtp_password,
      },
    },
  }
}

async function load() {
  isLoading.value = true
  loadError.value = null
  try {
    const backendConfig = await settingsStore.loadEmailProxyConfig()
    if (backendConfig) {
      const fe = toFrontend(backendConfig)
      if (fe) {
        Object.assign(form, fe)
      }
      isEnabled.value = backendConfig.email_proxy?.enabled || backendConfig.enabled || false
    }
  } catch (e) {
    console.error('Failed to load email proxy config:', e)
    loadError.value = e.message
  } finally {
    isLoading.value = false
  }
}

async function save() {
  if (!hasChanges.value) return
  isSaving.value = true
  try {
    await settingsStore.updateEmailProxyConfig(toBackend())
    hasChanges.value = false
    expanded.value = false
    uiStore.showNotification('Email proxy saved', 'success')
  } catch (e) {
    uiStore.showNotification('Save failed: ' + e.message, 'error')
  } finally {
    isSaving.value = false
  }
}

async function toggleEnable() {
  try {
    if (isEnabled.value) {
      await settingsStore.disableEmailProxy()
      isEnabled.value = false
    } else {
      await settingsStore.enableEmailProxy()
      isEnabled.value = true
    }
  } catch (e) {
    uiStore.showNotification('Failed to toggle', 'error')
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
      <!-- Main card -->
      <div :class="['card', { expanded }]">
        <div class="card-header" @click="expanded = !expanded">
          <div class="card-title-row">
            <span class="card-key">email_proxy</span>
            <span class="card-display">Email Proxy</span>
            <button
              class="toggle-chip"
              :class="{ on: isEnabled }"
              @click.stop="toggleEnable"
            >
              {{ isEnabled ? 'On' : 'Off' }}
            </button>
          </div>
          <div v-if="!expanded" class="card-summary">
            <template v-if="form.matrix_mailbox">
              {{ form.matrix_mailbox }}
            </template>
            <template v-else>
              <span class="placeholder">{{ isEnabled ? '已配置' : '未配置' }}</span>
            </template>
          </div>
          <span class="expand-icon" :class="{ rotated: expanded }"><MIcon name="chevron-down" /></span>
        </div>

        <div v-if="expanded" class="card-form" @click.stop>
          <div class="field">
            <label>System Mailbox</label>
            <input v-model="form.matrix_mailbox" class="input" placeholder="agent@mymatrix.com" @input="trackChange" />
            <span class="field-hint">AgentMatrix uses this mailbox to send and receive emails</span>
          </div>
          <div class="field">
            <label>User Mailbox</label>
            <input v-model="form.user_mailbox" class="input" placeholder="you@gmail.com" @input="trackChange" />
            <span class="field-hint">Emails from this address are recognized as user messages (comma-separated for multiple)</span>
          </div>

          <div class="field-group-label">IMAP</div>
          <div class="field-row">
            <div class="field flex-2">
              <label>Host</label>
              <input v-model="form.imap_host" class="input" placeholder="imap.gmail.com" @input="trackChange" />
            </div>
            <div class="field flex-0">
              <label>Port</label>
              <input v-model="form.imap_port" class="input" placeholder="993" @input="trackChange" />
            </div>
          </div>
          <div class="field-row">
            <div class="field flex-1">
              <label>User</label>
              <input v-model="form.imap_user" class="input" placeholder="user@gmail.com" @input="trackChange" />
            </div>
            <div class="field flex-1">
              <label>Password</label>
              <input v-model="form.imap_password" class="input" type="password" placeholder="••••••••" @input="trackChange" />
            </div>
          </div>

          <div class="field-group-label">SMTP</div>
          <div class="field-row">
            <div class="field flex-2">
              <label>Host</label>
              <input v-model="form.smtp_host" class="input" placeholder="smtp.gmail.com" @input="trackChange" />
            </div>
            <div class="field flex-0">
              <label>Port</label>
              <input v-model="form.smtp_port" class="input" placeholder="587" @input="trackChange" />
            </div>
          </div>
          <div class="field-row">
            <div class="field flex-1">
              <label>User</label>
              <input v-model="form.smtp_user" class="input" placeholder="user@gmail.com" @input="trackChange" />
            </div>
            <div class="field flex-1">
              <label>Password</label>
              <input v-model="form.smtp_password" class="input" type="password" placeholder="••••••••" @input="trackChange" />
            </div>
          </div>

          <div class="card-actions">
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

.field-hint {
  font-size: 11px;
  color: var(--text-tertiary);
}

.field-group-label {
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  color: var(--accent);
  padding-top: var(--spacing-2);
}

.field-row {
  display: flex;
  gap: var(--spacing-3);
}

.flex-1 { flex: 1; }
.flex-2 { flex: 2; }
.flex-0 { width: 80px; flex-shrink: 0; }

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
  justify-content: flex-end;
  gap: var(--spacing-2);
  padding-top: var(--spacing-2);
}

.btn-text {
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