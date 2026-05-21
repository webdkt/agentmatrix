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
const showImapPassword = ref(false)
const showSmtpPassword = ref(false)

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
            <MIcon name="mail" :size="14" class="group-icon" />
            <span>邮件代理</span>
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
              <MIcon name="mail" :size="16" />
            </div>
            <div class="sec-text">
              <div class="sec-title">Email Proxy</div>
              <div class="sec-desc">配置系统邮箱，实现邮件收发代理功能。AgentMatrix 将通过此邮箱接收用户指令并发送回复。</div>
            </div>
          </div>

          <div class="sec-main">
            <!-- Mailbox -->
            <div class="sec-row">
              <div class="fi fi--full">
                <label class="fi-lbl">System Mailbox</label>
                <input v-model="form.matrix_mailbox" class="fi-inp" placeholder="agent@mymatrix.com" @input="trackChange" />
                <span class="field-hint">AgentMatrix uses this mailbox to send and receive emails</span>
              </div>
            </div>
            <div class="sec-row">
              <div class="fi fi--full">
                <label class="fi-lbl">User Mailbox</label>
                <input v-model="form.user_mailbox" class="fi-inp" placeholder="you@gmail.com" @input="trackChange" />
                <span class="field-hint">Emails from this address are recognized as user messages (comma-separated for multiple)</span>
              </div>
            </div>

            <!-- IMAP -->
            <div class="sec-subtitle">IMAP</div>
            <div class="sec-row">
              <div class="fi flex-2">
                <label class="fi-lbl">Host</label>
                <input v-model="form.imap_host" class="fi-inp" placeholder="imap.gmail.com" @input="trackChange" />
              </div>
              <div class="fi flex-0">
                <label class="fi-lbl">Port</label>
                <input v-model="form.imap_port" class="fi-inp" placeholder="993" @input="trackChange" />
              </div>
            </div>
            <div class="sec-row">
              <div class="fi flex-1">
                <label class="fi-lbl">User</label>
                <input v-model="form.imap_user" class="fi-inp" placeholder="user@gmail.com" @input="trackChange" />
              </div>
              <div class="fi flex-1">
                <label class="fi-lbl">Password</label>
                <div class="pw-wrap">
                  <input
                    v-model="form.imap_password"
                    :type="showImapPassword ? 'text' : 'password'"
                    class="fi-inp"
                    placeholder="••••••••"
                    @input="trackChange"
                  />
                  <button class="eye-btn" @click="showImapPassword = !showImapPassword" type="button">
                    <MIcon :name="showImapPassword ? 'eye-off' : 'eye'" :size="14" />
                  </button>
                </div>
              </div>
            </div>

            <!-- SMTP -->
            <div class="sec-subtitle">SMTP</div>
            <div class="sec-row">
              <div class="fi flex-2">
                <label class="fi-lbl">Host</label>
                <input v-model="form.smtp_host" class="fi-inp" placeholder="smtp.gmail.com" @input="trackChange" />
              </div>
              <div class="fi flex-0">
                <label class="fi-lbl">Port</label>
                <input v-model="form.smtp_port" class="fi-inp" placeholder="587" @input="trackChange" />
              </div>
            </div>
            <div class="sec-row">
              <div class="fi flex-1">
                <label class="fi-lbl">User</label>
                <input v-model="form.smtp_user" class="fi-inp" placeholder="user@gmail.com" @input="trackChange" />
              </div>
              <div class="fi flex-1">
                <label class="fi-lbl">Password</label>
                <div class="pw-wrap">
                  <input
                    v-model="form.smtp_password"
                    :type="showSmtpPassword ? 'text' : 'password'"
                    class="fi-inp"
                    placeholder="••••••••"
                    @input="trackChange"
                  />
                  <button class="eye-btn" @click="showSmtpPassword = !showSmtpPassword" type="button">
                    <MIcon :name="showSmtpPassword ? 'eye-off' : 'eye'" :size="14" />
                  </button>
                </div>
              </div>
            </div>

            <!-- Actions -->
            <div class="sec-actions">
              <button class="btn-text" @click="save" :disabled="isSaving || !hasChanges">
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

.sec-subtitle {
  font-size: var(--font-xs);
  font-weight: var(--font-bold);
  color: var(--accent);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  padding-top: 6px;
  border-top: 1px solid var(--border-light);
  margin-top: 6px;
}

/* ═══════════════════════════════════════
   FIELDS
   ═══════════════════════════════════════ */
.fi {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.fi--full {
  grid-column: 1 / -1;
}

.fi-lbl {
  font-size: var(--font-sm);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  letter-spacing: 0.04em;
}

.field-hint {
  font-size: 11px;
  color: var(--text-tertiary);
  line-height: 1.4;
  margin-top: 2px;
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

/* ─── Password ─── */
.pw-wrap {
  position: relative;
  width: 100%;
}

.pw-wrap .fi-inp {
  padding-right: 32px;
}

.eye-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-quaternary);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  transition: color var(--duration-base) var(--ease-out);
}

.eye-btn:hover { color: var(--text-tertiary); }

/* ═══════════════════════════════════════
   FLEX UTILITIES
   ═══════════════════════════════════════ */
.flex-1 { flex: 1; }
.flex-2 { flex: 2; }
.flex-0 { width: 100px; flex-shrink: 0; }

/* ═══════════════════════════════════════
   ACTIONS
   ═══════════════════════════════════════ */
.sec-actions {
  display: flex;
  justify-content: flex-end;
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
</style>
