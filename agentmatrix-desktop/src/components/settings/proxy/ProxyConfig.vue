<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'
import ProxyForm from './ProxyForm.vue'
import MIcon from '@/components/icons/MIcon.vue'

const settingsStore = useSettingsStore()
const uiStore = useUIStore()

const showForm = ref(false)
const isEnabled = ref(false)
const localConfig = ref(null)
const isLoading = ref(false)
const isTesting = ref(false)

const hasConfig = computed(() => {
  return !!localConfig.value && (localConfig.value.host || localConfig.value.port)
})

const configSummary = computed(() => {
  if (!localConfig.value) return null
  return {
    host: localConfig.value.host || 'Not configured',
    port: localConfig.value.port || '0'
  }
})

const loadConfig = async () => {
  isLoading.value = true
  try {
    const config = await settingsStore.loadProxyConfig()
    if (config) {
      localConfig.value = {
        host: config.host || '',
        port: config.port || 0
      }
      isEnabled.value = config.enabled || false
    }
  } catch (error) {
    console.log('Failed to load proxy config:', error.message)
  } finally {
    isLoading.value = false
  }
}

const handleToggle = async () => {
  try {
    if (isEnabled.value) {
      await settingsStore.disableProxy()
      isEnabled.value = false
      uiStore.showNotification('HTTP Proxy disabled', 'success')
    } else {
      if (!hasConfig.value) {
        showForm.value = true
        return
      }
      await settingsStore.enableProxy()
      isEnabled.value = true
      uiStore.showNotification('HTTP Proxy enabled', 'success')
    }
  } catch (error) {
    uiStore.showNotification('Failed to toggle proxy: ' + error.message, 'error')
  }
}

const handleTest = async () => {
  isTesting.value = true
  try {
    const result = await settingsStore.testProxyConnection()
    if (result.success) {
      uiStore.showNotification(result.message || 'Proxy connection successful', 'success')
    } else {
      uiStore.showNotification(result.message || 'Proxy connection failed', 'error')
    }
  } catch (error) {
    uiStore.showNotification('Proxy test failed: ' + error.message, 'error')
  } finally {
    isTesting.value = false
  }
}

const handleEdit = () => {
  showForm.value = true
}

const handleFormSave = async (formData) => {
  try {
    await settingsStore.updateProxyConfig({
      enabled: isEnabled.value,
      host: formData.host,
      port: parseInt(formData.port) || 0
    })
    localConfig.value = {
      host: formData.host,
      port: parseInt(formData.port) || 0
    }
    showForm.value = false
    uiStore.showNotification('Proxy config saved', 'success')
  } catch (error) {
    uiStore.showNotification('Failed to save: ' + error.message, 'error')
  }
}

const handleFormClose = () => {
  showForm.value = false
}

onMounted(() => {
  loadConfig()
})
</script>

<template>
  <div class="proxy-config">
    <!-- Status Card -->
    <div class="config-card">
      <div class="card-header">
        <div class="card-title-group">
          <h3 class="card-title">HTTP Proxy</h3>
          <p class="card-description">Route LLM API calls and agent network traffic through a proxy server</p>
        </div>
        <div class="card-actions">
          <button
            class="toggle-button"
            :class="{ active: isEnabled }"
            @click="handleToggle"
            :disabled="isLoading"
          >
            {{ isEnabled ? 'Enabled' : 'Disabled' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Config Display Card -->
    <div class="config-card" v-if="hasConfig">
      <div class="card-header">
        <h3 class="card-title">Configuration</h3>
        <div class="card-actions">
          <button
            class="action-button"
            @click="handleTest"
            :disabled="isTesting || !isEnabled"
            title="Test proxy connection"
          >
            <MIcon name="plug-connected" />
            {{ isTesting ? 'Testing...' : 'Test' }}
          </button>
          <button class="action-button" @click="handleEdit" title="Edit config">
            <MIcon name="pencil" />
            Edit
          </button>
        </div>
      </div>
      <div class="config-details">
        <div class="config-field">
          <span class="field-label">Host</span>
          <span class="field-value">{{ configSummary.host }}</span>
        </div>
        <div class="config-field">
          <span class="field-label">Port</span>
          <span class="field-value">{{ configSummary.port }}</span>
        </div>
      </div>
    </div>

    <!-- Empty State -->
    <div class="config-card" v-else>
      <div class="empty-state">
        <div class="empty-icon">
          <MIcon name="shield-off" />
        </div>
        <h3>No Proxy Configured</h3>
        <p>Configure an HTTP proxy to route network traffic through a proxy server.</p>
        <button class="primary-button" @click="handleEdit">
          Configure Now
        </button>
      </div>
    </div>

    <!-- Form Modal -->
    <ProxyForm
      v-if="showForm"
      :config="localConfig"
      @save="handleFormSave"
      @close="handleFormClose"
    />
  </div>
</template>

<style scoped>
.proxy-config {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-6);
  padding-top: var(--spacing-6);
}

.config-card {
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-6);
  gap: var(--spacing-4);
}

.card-title-group {
  flex: 1;
}

.card-title {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
}

.card-description {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  margin: 2px 0 0 0;
}

.card-actions {
  display: flex;
  gap: var(--spacing-2);
  align-items: center;
}

.toggle-button {
  padding: var(--spacing-1) var(--spacing-4);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: var(--surface-hover);
  color: var(--text-secondary);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.toggle-button.active {
  background: var(--success-50);
  border-color: var(--success-300);
  color: var(--success-700);
}

.toggle-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.action-button {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-1) var(--spacing-2);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
  background: white;
  color: var(--text-secondary);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.action-button:hover:not(:disabled) {
  background: var(--surface-base);
  border-color: var(--border-strong);
}

.action-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.config-details {
  padding: 0 var(--spacing-6) var(--spacing-6);
  display: flex;
  gap: var(--spacing-8);
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.field-label {
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  color: var(--text-tertiary);
}

.field-value {
  font-size: var(--font-sm);
  color: var(--text-primary);
  font-family: var(--font-mono);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-12);
  gap: var(--spacing-2);
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  color: var(--border-strong);
  margin-bottom: var(--spacing-2);
}

.empty-state h3 {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  margin: 0;
}

.empty-state p {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  margin: 0;
  max-width: 320px;
}

.primary-button {
  margin-top: var(--spacing-4);
  padding: var(--spacing-2) var(--spacing-6);
  border-radius: var(--radius-md);
  border: none;
  background: var(--accent);
  color: white;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.primary-button:hover {
  background: var(--accent-hover);
}
</style>
