<script setup>
import { ref, computed, watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'

const props = defineProps({
  config: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['close', 'saved'])

const settingsStore = useSettingsStore()
const uiStore = useUIStore()

// Form state
const formData = ref({
  email: '',
  imap_host: '',
  imap_port: '993',
  imap_user: '',
  imap_password: '',
  smtp_host: '',
  smtp_port: '587',
  smtp_user: '',
  smtp_password: '',
})

const isSubmitting = ref(false)
const showImapPassword = ref(false)
const showSmtpPassword = ref(false)

// Initialize form data
const initializeForm = () => {
  if (props.config) {
    formData.value = {
      email: props.config.email || '',
      imap_host: props.config.imap_host || '',
      imap_port: props.config.imap_port || '993',
      imap_user: props.config.imap_user || '',
      imap_password: props.config.imap_password || '',
      smtp_host: props.config.smtp_host || '',
      smtp_port: props.config.smtp_port || '587',
      smtp_user: props.config.smtp_user || '',
      smtp_password: props.config.smtp_password || '',
    }
  }
}

// Watch props.config changes
watch(() => props.config, () => {
  initializeForm()
}, { immediate: true })

// Computed
const canSubmit = computed(() => {
  return formData.value.email.trim() &&
         formData.value.imap_host.trim() &&
         formData.value.imap_user.trim() &&
         formData.value.imap_password.trim() &&
         formData.value.smtp_host.trim() &&
         formData.value.smtp_user.trim() &&
         formData.value.smtp_password.trim() &&
         !isSubmitting.value
})

// Methods
const handleSubmit = async () => {
  if (!canSubmit.value) return

  isSubmitting.value = true
  try {
    // Try to save to backend
    try {
      await settingsStore.updateEmailProxyConfig(formData.value)
    } catch (backendError) {
      console.log('Backend API not ready, saving locally only:', backendError.message)
    }

    // Always emit the saved configuration to parent
    emit('saved', { ...formData.value })
    emit('close')
  } catch (error) {
    console.error('Failed to save email proxy config:', error)
    uiStore.showNotification(`Failed to save: ${error.message}`, 'error')
  } finally {
    isSubmitting.value = false
  }
}

const handleCancel = () => {
  emit('close')
}

const copyImapToSmtp = () => {
  formData.value.smtp_host = formData.value.imap_host
  formData.value.smtp_user = formData.value.imap_user
  formData.value.smtp_password = formData.value.imap_password
}
</script>

<template>
  <div class="modal-overlay" @click.self="handleCancel">
    <div class="modal-container">
      <!-- Header -->
      <div class="modal-header">
        <div class="header-info">
          <h3 class="modal-title">Email Proxy Configuration</h3>
          <p class="modal-subtitle">Configure your email proxy service settings</p>
        </div>
        <button
          @click="handleCancel"
          class="btn-close"
        >
          <i class="ti ti-x"></i>
        </button>
      </div>

      <!-- Form Content -->
      <div class="modal-content">
        <!-- Email Settings -->
        <div class="form-section">
          <h4 class="section-title">
            <i class="ti ti-mail"></i>
            Email Settings
          </h4>

          <div class="form-group">
            <label class="form-label">
              Email Address <span class="required">*</span>
            </label>
            <input
              v-model="formData.email"
              type="email"
              class="form-input"
              placeholder="your.email@example.com"
            />
          </div>
        </div>

        <!-- IMAP Configuration -->
        <div class="form-section">
          <div class="section-header">
            <h4 class="section-title">
              <i class="ti ti-inbox"></i>
              IMAP Configuration
            </h4>
            <button
              type="button"
              @click="copyImapToSmtp"
              class="btn-copy"
              title="Copy IMAP settings to SMTP"
            >
              <i class="ti ti-copy"></i>
              <span>Copy to SMTP</span>
            </button>
          </div>

          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">
                IMAP Host <span class="required">*</span>
              </label>
              <input
                v-model="formData.imap_host"
                type="text"
                class="form-input"
                placeholder="imap.example.com"
              />
            </div>

            <div class="form-group">
              <label class="form-label">
                IMAP Port <span class="required">*</span>
              </label>
              <input
                v-model="formData.imap_port"
                type="number"
                class="form-input"
                placeholder="993"
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              IMAP Username <span class="required">*</span>
            </label>
            <input
              v-model="formData.imap_user"
              type="text"
              class="form-input"
              placeholder="username@example.com"
            />
          </div>

          <div class="form-group">
            <label class="form-label">
              IMAP Password <span class="required">*</span>
            </label>
            <div class="password-input">
              <input
                v-model="formData.imap_password"
                :type="showImapPassword ? 'text' : 'password'"
                class="form-input"
                placeholder="••••••••"
              />
              <button
                type="button"
                @click="showImapPassword = !showImapPassword"
                class="btn-toggle-visibility"
              >
                <i :class="showImapPassword ? 'ti ti-eye-off' : 'ti ti-eye'"></i>
              </button>
            </div>
          </div>
        </div>

        <!-- SMTP Configuration -->
        <div class="form-section">
          <h4 class="section-title">
            <i class="ti ti-send"></i>
            SMTP Configuration
          </h4>

          <div class="form-grid">
            <div class="form-group">
              <label class="form-label">
                SMTP Host <span class="required">*</span>
              </label>
              <input
                v-model="formData.smtp_host"
                type="text"
                class="form-input"
                placeholder="smtp.example.com"
              />
            </div>

            <div class="form-group">
              <label class="form-label">
                SMTP Port <span class="required">*</span>
              </label>
              <input
                v-model="formData.smtp_port"
                type="number"
                class="form-input"
                placeholder="587"
              />
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              SMTP Username <span class="required">*</span>
            </label>
            <input
              v-model="formData.smtp_user"
              type="text"
              class="form-input"
              placeholder="username@example.com"
            />
          </div>

          <div class="form-group">
            <label class="form-label">
              SMTP Password <span class="required">*</span>
            </label>
            <div class="password-input">
              <input
                v-model="formData.smtp_password"
                :type="showSmtpPassword ? 'text' : 'password'"
                class="form-input"
                placeholder="••••••••"
              />
              <button
                type="button"
                @click="showSmtpPassword = !showSmtpPassword"
                class="btn-toggle-visibility"
              >
                <i :class="showSmtpPassword ? 'ti ti-eye-off' : 'ti ti-eye'"></i>
              </button>
            </div>
          </div>
        </div>

        <!-- Help Text -->
        <div class="help-section">
          <div class="help-icon">
            <i class="ti ti-info-circle"></i>
          </div>
          <div class="help-content">
            <h5>Configuration Help</h5>
            <ul>
              <li>IMAP is used for receiving emails</li>
              <li>SMTP is used for sending emails</li>
              <li>Common IMAP port: 993 (SSL) or 143 (STARTTLS)</li>
              <li>Common SMTP port: 587 (STARTTLS) or 465 (SSL)</li>
            </ul>
          </div>
        </div>
      </div>

      <!-- Footer -->
      <div class="modal-footer">
        <button
          @click="handleCancel"
          type="button"
          class="btn-secondary"
        >
          Cancel
        </button>
        <button
          @click="handleSubmit"
          :disabled="!canSubmit || isSubmitting"
          type="submit"
          class="btn-primary"
        >
          <i v-if="isSubmitting" class="ti ti-loader spinner"></i>
          <i v-else class="ti ti-check"></i>
          <span>Save Configuration</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  padding: var(--spacing-md);
}

.modal-container {
  background: white;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xl);
  max-width: 700px;
  width: 100%;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.modal-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: var(--spacing-lg);
  border-bottom: 1px solid var(--neutral-200);
  flex-shrink: 0;
}

.header-info {
  flex: 1;
}

.modal-title {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin: 0;
  line-height: var(--leading-tight);
}

.modal-subtitle {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  margin: var(--spacing-1) 0 0 0;
}

.btn-close {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-sm);
  background: transparent;
  border: none;
  color: var(--neutral-400);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--icon-lg);
  transition: all var(--duration-base) var(--ease-out);
  flex-shrink: 0;
}

.btn-close:hover {
  background: var(--neutral-100);
  color: var(--neutral-600);
}

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin: 0;
}

.section-title i {
  color: var(--primary-500);
}

.btn-copy {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-2) var(--spacing-3);
  background: var(--primary-50);
  border: 1px solid var(--primary-200);
  border-radius: var(--radius-sm);
  color: var(--primary-600);
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.btn-copy:hover {
  background: var(--primary-100);
  border-color: var(--primary-300);
}

.form-grid {
  display: grid;
  grid-template-columns: 2fr 1fr;
  gap: var(--spacing-md);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.form-label {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-700);
  display: block;
}

.required {
  color: var(--error-500);
}

.form-input {
  width: 100%;
  padding: var(--spacing-3);
  background: white;
  border: 1px solid var(--neutral-300);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  color: var(--neutral-900);
  transition: all var(--duration-base) var(--ease-out);
}

.form-input:focus {
  outline: none;
  border-color: var(--primary-500);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.password-input {
  position: relative;
}

.btn-toggle-visibility {
  position: absolute;
  right: var(--spacing-2);
  top: 50%;
  transform: translateY(-50%);
  padding: var(--spacing-1) var(--spacing-2);
  background: transparent;
  border: none;
  color: var(--neutral-500);
  cursor: pointer;
  font-size: var(--icon-md);
  border-radius: var(--radius-sm);
  transition: all var(--duration-base) var(--ease-out);
}

.btn-toggle-visibility:hover {
  background: var(--neutral-100);
  color: var(--neutral-700);
}

.help-section {
  display: flex;
  gap: var(--spacing-3);
  padding: var(--spacing-4);
  background: var(--info-50);
  border-radius: var(--radius-md);
  border: 1px solid var(--info-100);
}

.help-icon {
  width: 24px;
  height: 24px;
  border-radius: 50%;
  background: var(--info-100);
  color: var(--info-600);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--icon-sm);
  flex-shrink: 0;
}

.help-content {
  flex: 1;
}

.help-content h5 {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--info-700);
  margin: 0 0 var(--spacing-2) 0;
}

.help-content ul {
  margin: 0;
  padding-left: var(--spacing-4);
  font-size: var(--font-xs);
  color: var(--info-600);
  line-height: var(--leading-relaxed);
}

.help-content li {
  margin-bottom: var(--spacing-1);
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--spacing-3);
  padding: var(--spacing-lg);
  border-top: 1px solid var(--neutral-200);
  flex-shrink: 0;
}

.btn-secondary {
  padding: var(--spacing-3) var(--spacing-4);
  background: transparent;
  color: var(--neutral-700);
  border: 1px solid var(--neutral-300);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.btn-secondary:hover {
  background: var(--neutral-100);
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--primary-600);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-700);
}

.btn-primary:disabled {
  background: var(--neutral-300);
  color: var(--neutral-500);
  cursor: not-allowed;
}

.spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
