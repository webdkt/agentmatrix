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
  gap: var(--spacing-lg);
  padding-top: var(--spacing-lg);
}

.config-card {
  background: white;
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-lg);
  gap: var(--spacing-md);
}

.card-title-group {
  flex: 1;
}

.card-title {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin: 0;
}

.card-description {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  margin: 2px 0 0 0;
}

.card-actions {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
}

.toggle-button {
  padding: var(--spacing-xs) var(--spacing-md);
  border-radius: var(--radius-base);
  border: 1px solid var(--neutral-300);
  background: var(--neutral-100);
  color: var(--neutral-700);
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
  gap: var(--spacing-xs);
  padding: var(--spacing-xs) var(--spacing-sm);
  border-radius: var(--radius-base);
  border: 1px solid var(--neutral-200);
  background: white;
  color: var(--neutral-600);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.action-button:hover:not(:disabled) {
  background: var(--neutral-50);
  border-color: var(--neutral-300);
}

.action-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.config-details {
  padding: 0 var(--spacing-lg) var(--spacing-lg);
  display: flex;
  gap: var(--spacing-xl);
}

.config-field {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.field-label {
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  color: var(--neutral-500);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.field-value {
  font-size: var(--font-sm);
  color: var(--neutral-800);
  font-family: var(--font-mono);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: var(--spacing-2xl);
  gap: var(--spacing-sm);
  text-align: center;
}

.empty-icon {
  font-size: 48px;
  color: var(--neutral-300);
  margin-bottom: var(--spacing-sm);
}

.empty-state h3 {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--neutral-700);
  margin: 0;
}

.empty-state p {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  margin: 0;
  max-width: 320px;
}

.primary-button {
  margin-top: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-lg);
  border-radius: var(--radius-base);
  border: none;
  background: var(--primary-600);
  color: white;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.primary-button:hover {
  background: var(--primary-700);
}
</style>
