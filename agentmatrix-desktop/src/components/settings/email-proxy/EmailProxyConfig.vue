<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'
import EmailProxyForm from './EmailProxyForm.vue'
import MIcon from '@/components/icons/MIcon.vue'

const settingsStore = useSettingsStore()
const uiStore = useUIStore()

// State
const showForm = ref(false)
const isEnabled = ref(false)
const config = ref(null)
const isLoading = ref(false)
const isTesting = ref(false)

// Local config storage (flattened format for form)
const localConfig = ref(null)

// Computed
const hasConfig = computed(() => {
  return !!localConfig.value
})

const configSummary = computed(() => {
  if (!localConfig.value) return null

  return {
    email: localConfig.value.email || 'Not configured',
    imapHost: localConfig.value.imap_host || 'Not configured',
    imapPort: localConfig.value.imap_port || '993',
    smtpHost: localConfig.value.smtp_host || 'Not configured',
    smtpPort: localConfig.value.smtp_port || '587'
  }
})

// Convert backend config format to frontend format
const convertBackendToFrontend = (backendConfig) => {
  if (!backendConfig) return null

  // Backend format (from YAML):
  // {
  //   email_proxy: {
  //     enabled: false,
  //     matrix_mailbox: "...",
  //     imap: { host: "...", port: 993, user: "...", password: "..." },
  //     smtp: { host: "...", port: 587, user: "...", password: "..." }
  //   }
  // }

  // Frontend format (flat):
  // {
  //   email: "...",
  //   imap_host: "...",
  //   imap_port: "...",
  //   imap_user: "...",
  //   imap_password: "...",
  //   smtp_host: "...",
  //   smtp_port: "...",
  //   smtp_user: "...",
  //   smtp_password: "..."
  // }

  const emailProxy = backendConfig.email_proxy || backendConfig

  return {
    email: emailProxy.matrix_mailbox || emailProxy.user_mailbox || '',
    imap_host: emailProxy.imap?.host || '',
    imap_port: emailProxy.imap?.port?.toString() || '993',
    imap_user: emailProxy.imap?.user || '',
    imap_password: emailProxy.imap?.password || '',
    smtp_host: emailProxy.smtp?.host || '',
    smtp_port: emailProxy.smtp?.port?.toString() || '587',
    smtp_user: emailProxy.smtp?.user || '',
    smtp_password: emailProxy.smtp?.password || ''
  }
}

// Convert frontend config format to backend format
const convertFrontendToBackend = (frontendConfig) => {
  // Frontend format -> Backend format
  return {
    email_proxy: {
      enabled: isEnabled.value,
      matrix_mailbox: frontendConfig.email,
      imap: {
        host: frontendConfig.imap_host,
        port: parseInt(frontendConfig.imap_port) || 993,
        user: frontendConfig.imap_user,
        password: frontendConfig.imap_password
      },
      smtp: {
        host: frontendConfig.smtp_host,
        port: parseInt(frontendConfig.smtp_port) || 587,
        user: frontendConfig.smtp_user,
        password: frontendConfig.smtp_password
      }
    }
  }
}

// Methods
const loadConfig = async () => {
  isLoading.value = true
  try {
    const backendConfig = await settingsStore.loadEmailProxyConfig()
    if (backendConfig) {
      // Convert backend format to frontend format
      const frontendConfig = convertBackendToFrontend(backendConfig)
      localConfig.value = frontendConfig
      isEnabled.value = backendConfig.email_proxy?.enabled || backendConfig.enabled || false
    }
  } catch (error) {
    console.log('Failed to load email proxy config:', error.message)
    // Don't show error for expected failures
  } finally {
    isLoading.value = false
  }
}

const handleToggleEnable = async () => {
  try {
    if (isEnabled.value) {
      await settingsStore.disableEmailProxy()
    } else {
      await settingsStore.enableEmailProxy()
    }
    isEnabled.value = !isEnabled.value
    uiStore.showNotification(
      `Email proxy ${isEnabled.value ? 'enabled' : 'disabled'}`,
      'success'
    )
  } catch (error) {
    console.error('Failed to toggle email proxy:', error)
    uiStore.showNotification('Failed to toggle email proxy', 'error')
  }
}

const handleEditConfig = () => {
  showForm.value = true
}

const handleCloseForm = () => {
  showForm.value = false
}

const handleConfigSaved = async (savedFrontendConfig) => {
  // Convert frontend format to backend format
  const backendConfig = convertFrontendToBackend(savedFrontendConfig)

  // Save to backend
  try {
    await settingsStore.updateEmailProxyConfig(backendConfig)
    localConfig.value = savedFrontendConfig
    showForm.value = false
    uiStore.showNotification('Email proxy configuration saved', 'success')
  } catch (error) {
    console.error('Failed to save email proxy config:', error)
    uiStore.showNotification(`Failed to save: ${error.message}`, 'error')
  }
}

const handleTestConnection = async () => {
  isTesting.value = true
  try {
    await settingsStore.testEmailProxyConnection()
    uiStore.showNotification('Connection test successful', 'success')
  } catch (error) {
    console.error('Connection test failed:', error)
    uiStore.showNotification('Connection test failed', 'error')
  } finally {
    isTesting.value = false
  }
}

// Lifecycle
onMounted(async () => {
  await loadConfig()
})
</script>

<template>
  <div class="email-proxy-config">
    <!-- Status Card -->
    <div class="status-card">
      <div class="status-header">
        <div class="status-info">
          <div class="status-icon" :class="{ enabled: isEnabled }">
            <MIcon name="mail" />
          </div>
          <div>
            <h3 class="status-title">Email Proxy Service</h3>
            <p class="status-description">
              {{ isEnabled ? 'Service is enabled and running' : 'Service is disabled' }}
            </p>
          </div>
        </div>
        <div class="status-actions">
          <button
            @click="handleTestConnection"
            :disabled="!hasConfig || isTesting"
            class="btn-test"
            title="Test connection"
          >
            <MIcon name="flask" :class="{ spinner: isTesting }" />
            <span>{{ isTesting ? 'Testing...' : 'Test' }}</span>
          </button>
          <button
            @click="handleToggleEnable"
            :disabled="!hasConfig"
            class="btn-toggle"
            :class="{ enabled: isEnabled }"
          >
            <MIcon :name="isEnabled ? 'player-pause' : 'player-play'" />
            <span>{{ isEnabled ? 'Disable' : 'Enable' }}</span>
          </button>
        </div>
      </div>
    </div>

    <!-- Configuration Card -->
    <div class="config-card">
      <div class="config-header">
        <div>
          <h3 class="config-title">Configuration</h3>
          <p class="config-description">
            {{ hasConfig ? 'Email proxy is configured' : 'No configuration found' }}
          </p>
        </div>
        <button
          @click="handleEditConfig"
          class="btn-edit"
        >
          <MIcon name="pencil" />
          <span>{{ hasConfig ? 'Edit' : 'Configure' }}</span>
        </button>
      </div>

      <div v-if="hasConfig && configSummary" class="config-details">
        <div class="detail-section">
          <h4 class="detail-section-title">
            <MIcon name="mail" />
            Email Settings
          </h4>
          <div class="detail-item">
            <span class="detail-label">Email Address</span>
            <span class="detail-value">{{ configSummary.email }}</span>
          </div>
        </div>

        <div class="detail-section">
          <h4 class="detail-section-title">
            <MIcon name="inbox" />
            IMAP Configuration
          </h4>
          <div class="detail-item">
            <span class="detail-label">Host</span>
            <span class="detail-value">{{ configSummary.imapHost }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Port</span>
            <span class="detail-value">{{ configSummary.imapPort }}</span>
          </div>
          <div v-if="localConfig?.imap_user" class="detail-item">
            <span class="detail-label">Username</span>
            <span class="detail-value">{{ localConfig.imap_user }}</span>
          </div>
        </div>

        <div class="detail-section">
          <h4 class="detail-section-title">
            <MIcon name="send" />
            SMTP Configuration
          </h4>
          <div class="detail-item">
            <span class="detail-label">Host</span>
            <span class="detail-value">{{ configSummary.smtpHost }}</span>
          </div>
          <div class="detail-item">
            <span class="detail-label">Port</span>
            <span class="detail-value">{{ configSummary.smtpPort }}</span>
          </div>
          <div v-if="localConfig?.smtp_user" class="detail-item">
            <span class="detail-label">Username</span>
            <span class="detail-value">{{ localConfig.smtp_user }}</span>
          </div>
        </div>
      </div>

      <div v-else class="empty-config">
        <div class="empty-icon">
          <MIcon name="mail-off" />
        </div>
        <h4>No Configuration</h4>
        <p>Configure your email proxy settings to enable email services</p>
        <button
          @click="handleEditConfig"
          class="btn-configure"
        >
          <MIcon name="plus" />
          <span>Configure Now</span>
        </button>
      </div>
    </div>

    <!-- Form Modal -->
    <EmailProxyForm
      v-if="showForm"
      :config="localConfig"
      @close="handleCloseForm"
      @saved="handleConfigSaved"
    />
  </div>
</template>

<style scoped>
.email-proxy-config {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-8);
}

.status-card {
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--spacing-6);
}

.status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-6);
}

.status-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
}

.status-icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  background: var(--surface-hover);
  color: var(--text-tertiary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  transition: all var(--duration-base) var(--ease-out);
}

.status-icon.enabled {
  background: var(--success-50);
  color: var(--success-500);
}

.status-title {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
}

.status-description {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  margin: var(--spacing-1) 0 0 0;
}

.status-actions {
  display: flex;
  gap: var(--spacing-3);
}

.btn-test,
.btn-toggle {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: white;
  color: var(--text-secondary);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.btn-test:hover:not(:disabled),
.btn-toggle:hover:not(:disabled) {
  background: var(--surface-base);
  border-color: var(--text-tertiary);
}

.btn-test:disabled,
.btn-toggle:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-toggle.enabled {
  background: var(--error-50);
  border-color: var(--error-300);
  color: var(--error-700);
}

.btn-toggle.enabled:hover {
  background: var(--error-100);
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

.config-card {
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--spacing-6);
}

.config-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--spacing-6);
  padding-bottom: var(--spacing-6);
  border-bottom: 1px solid var(--surface-hover);
}

.config-title {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
}

.config-description {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  margin: var(--spacing-1) 0 0 0;
}

.btn-edit {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  flex-shrink: 0;
}

.btn-edit:hover {
  background: var(--accent-hover);
}

.config-details {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
}

.detail-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  padding: var(--spacing-4);
  background: var(--surface-base);
  border-radius: var(--radius-md);
}

.detail-section-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  margin: 0;
}

.detail-section-title i {
  color: var(--accent);
  font-size: var(--icon-lg);
}

.detail-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-2) 0;
  border-bottom: 1px solid var(--surface-hover);
}

.detail-item:last-child {
  border-bottom: none;
}

.detail-label {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  font-weight: var(--font-medium);
}

.detail-value {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.empty-config {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-12) var(--spacing-6);
  gap: var(--spacing-4);
  text-align: center;
}

.empty-icon {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-md);
  background: var(--surface-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  color: var(--border-strong);
}

.empty-config h4 {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  margin: 0;
}

.empty-config p {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  margin: 0;
}

.btn-configure {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-4) var(--spacing-6);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  margin-top: var(--spacing-2);
}

.btn-configure:hover {
  background: var(--accent-hover);
}
</style>
