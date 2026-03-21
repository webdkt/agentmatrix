<script setup>
import { ref, computed } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'
import LLMConfigCard from './LLMConfigCard.vue'
import LLMConfigForm from './LLMConfigForm.vue'
import ConfirmDialog from '../ConfirmDialog.vue'

const settingsStore = useSettingsStore()
const uiStore = useUIStore()

// State
const showForm = ref(false)
const editingConfig = ref(null)
const formMode = ref('create')
const showDeleteConfirm = ref(false)
const configToDelete = ref(null)

// Required LLM configs (not user-configurable)
const REQUIRED_LLM_CONFIGS = ['default_llm', 'default_slm', 'browser-use-llm']

// Computed
const llmConfigs = computed(() => {
  return settingsStore.llmConfigs || []
})

const requiredConfigs = computed(() => {
  return llmConfigs.value.filter(c => REQUIRED_LLM_CONFIGS.includes(c.name))
})

const customConfigs = computed(() => {
  return llmConfigs.value.filter(c => !REQUIRED_LLM_CONFIGS.includes(c.name))
})

// Methods
const openCreateForm = () => {
  editingConfig.value = null
  formMode.value = 'create'
  showForm.value = true
}

const openEditForm = (config) => {
  editingConfig.value = config
  formMode.value = 'edit'
  showForm.value = true
}

const closeForm = () => {
  showForm.value = false
  editingConfig.value = null
}

const handleConfigSaved = async () => {
  try {
    await settingsStore.loadLLMConfig()
  } catch (error) {
    console.error('Failed to reload configs:', error)
  }
}

const handleDeleteConfig = (configName) => {
  configToDelete.value = configName
  showDeleteConfirm.value = true
}

const confirmDelete = async () => {
  const configName = configToDelete.value
  try {
    await settingsStore.deleteLLMConfig(configName)
    uiStore.showNotification(`LLM config "${configName}" deleted`, 'success')
  } catch (error) {
    console.error('Failed to delete config:', error)
    uiStore.showNotification(`Failed to delete: ${error.message}`, 'error')
  } finally {
    showDeleteConfirm.value = false
    configToDelete.value = null
  }
}

const cancelDelete = () => {
  showDeleteConfirm.value = false
  configToDelete.value = null
}
</script>

<template>
  <div class="llm-config-list">
    <!-- Required Configs Section -->
    <div v-if="requiredConfigs.length > 0" class="config-section required-section">
      <div class="section-header">
        <h3 class="section-title">
          <i class="ti ti-shield-check"></i>
          <span>Required Configurations</span>
        </h3>
        <p class="section-description">
          These LLM configurations are required by the system and cannot be deleted
        </p>
      </div>
      <div class="config-grid">
        <LLMConfigCard
          v-for="config in requiredConfigs"
          :key="config.name"
          :config="config"
          :is-required="true"
          @edit="openEditForm"
        />
      </div>
    </div>

    <!-- Custom Configs Section -->
    <div v-if="customConfigs.length > 0" class="config-section custom-section">
      <div class="section-header">
        <div class="section-header-left">
          <h3 class="section-title">
            <i class="ti ti-sliders"></i>
            <span>Custom Configurations</span>
          </h3>
          <p class="section-description">
            Additional LLM configurations you've added
          </p>
        </div>
        <button
          @click="openCreateForm"
          class="btn-add"
        >
          <i class="ti ti-plus"></i>
          <span>Add New</span>
        </button>
      </div>
      <div class="config-grid">
        <LLMConfigCard
          v-for="config in customConfigs"
          :key="config.name"
          :config="config"
          :is-required="false"
          @edit="openEditForm"
          @delete="handleDeleteConfig"
        />
      </div>
    </div>

    <!-- Empty State -->
    <div v-if="llmConfigs.length === 0" class="empty-state">
      <div class="empty-icon">
        <i class="ti ti-brain-off"></i>
      </div>
      <h3>No LLM configurations</h3>
      <p>Add LLM configurations to enable AI capabilities</p>
      <button
        @click="openCreateForm"
        class="btn-primary"
      >
        <i class="ti ti-plus"></i>
        <span>Add Your First Config</span>
      </button>
    </div>

    <!-- Form Modal -->
    <LLMConfigForm
      v-if="showForm"
      :config="editingConfig"
      :mode="formMode"
      @close="closeForm"
      @saved="handleConfigSaved"
    />

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :show="showDeleteConfirm"
      title="Delete LLM Configuration"
      :message='`Are you sure you want to delete the LLM configuration "${configToDelete}"? This action cannot be undone.`'
      confirm-text="Delete"
      cancel-text="Cancel"
      type="danger"
      @confirm="confirmDelete"
      @cancel="cancelDelete"
    />
  </div>
</template>

<style scoped>
.llm-config-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

.config-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.section-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-md);
}

.section-header-left {
  flex: 1;
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin: 0 0 var(--spacing-2) 0;
}

.section-title i {
  color: var(--accent);
}

.section-description {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  margin: 0;
}

.btn-add {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  flex-shrink: 0;
}

.btn-add:hover {
  background: var(--accent-hover);
}

.btn-add:active {
  transform: scale(0.98);
}

.config-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: var(--spacing-md);
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-2xl) var(--spacing-lg);
  gap: var(--spacing-md);
  text-align: center;
}

.empty-icon {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-sm);
  background: var(--neutral-100);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 40px;
  color: var(--neutral-300);
}

.empty-state h3 {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--neutral-700);
  margin: 0;
}

.empty-state p {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  margin: 0;
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-4) var(--spacing-6);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.btn-primary:hover {
  background: var(--accent-hover);
}

.btn-primary:active {
  transform: scale(0.98);
}
</style>
