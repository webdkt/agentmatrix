<script setup>
import { ref, computed, watch } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'
import { isSystemConfig, isRequiredConfig, getSystemDisplayName } from '@/utils/llmConfigFs'

const props = defineProps({
  config: {
    type: Object,
    default: null
  },
  mode: {
    type: String,
    default: 'create'
  }
})

const emit = defineEmits(['close', 'saved'])

const settingsStore = useSettingsStore()
const uiStore = useUIStore()

const formData = ref({
  name: '',
  description: '',
  model_name: '',
  api_key: '',
  url: '',
})

const isSubmitting = ref(false)
const showApiKey = ref(false)

const isSystemConfigEdit = computed(() => {
  return props.mode === 'edit' && props.config && isSystemConfig(props.config.name)
})

const isRequiredConfigEdit = computed(() => {
  return props.mode === 'edit' && props.config && isRequiredConfig(props.config.name)
})

const isVisionConfig = computed(() => {
  return props.config && props.config.name === 'default_vision'
})

const displayName = computed(() => {
  if (isSystemConfigEdit.value) {
    return getSystemDisplayName(props.config.name)
  }
  return formData.value.name || 'New Config'
})

const formTitle = computed(() => {
  if (isSystemConfigEdit.value) {
    return `Edit ${getSystemDisplayName(props.config.name)}`
  }
  if (props.mode === 'edit') {
    return `Edit Config: ${props.config?.name}`
  }
  return 'Create New LLM Config'
})

const canSubmit = computed(() => {
  const hasName = formData.value.name.trim()
  const hasModel = formData.value.model_name.trim()
  const hasApiKey = formData.value.api_key.trim()
  const hasUrl = formData.value.url.trim()

  if (isRequiredConfigEdit.value) {
    return hasModel && hasApiKey && hasUrl && !isSubmitting.value
  }

  if (isVisionConfig.value && !hasModel && !hasApiKey && !hasUrl) {
    return true
  }

  return hasName && hasModel && hasApiKey && hasUrl && !isSubmitting.value
})

const initializeForm = () => {
  if (props.config && props.mode === 'edit') {
    formData.value = {
      name: props.config.name || '',
      description: props.config.description || '',
      model_name: props.config.model_name || '',
      api_key: props.config.api_key || '',
      url: props.config.url || '',
    }
  } else {
    formData.value = {
      name: '',
      description: '',
      model_name: '',
      api_key: '',
      url: '',
    }
  }
}

watch(() => props.config, () => {
  initializeForm()
}, { immediate: true })

const handleSubmit = async () => {
  if (!canSubmit.value) return

  isSubmitting.value = true
  try {
    if (props.mode === 'edit') {
      await settingsStore.saveLLMConfig(props.config.name, formData.value)
      uiStore.showNotification(`Config "${displayName.value}" updated`, 'success')
    } else {
      await settingsStore.createLLMConfig(formData.value)
      uiStore.showNotification(`Config "${formData.value.name}" created`, 'success')
    }

    emit('saved')
    emit('close')
  } catch (error) {
    console.error('Failed to save LLM config:', error)
    uiStore.showNotification(`Failed to save: ${error.message}`, 'error')
  } finally {
    isSubmitting.value = false
  }
}

const handleCancel = () => {
  emit('close')
}

const toggleApiKeyVisibility = () => {
  showApiKey.value = !showApiKey.value
}

const commonModels = [
  { name: 'GPT-4o', model: 'gpt-4o', url: 'https://api.openai.com/v1/chat/completions' },
  { name: 'GPT-4', model: 'gpt-4', url: 'https://api.openai.com/v1/chat/completions' },
  { name: 'GPT-3.5 Turbo', model: 'gpt-3.5-turbo', url: 'https://api.openai.com/v1/chat/completions' },
  { name: 'Claude 3.5 Sonnet', model: 'claude-3-5-sonnet-20241022', url: 'https://api.anthropic.com/v1/messages' },
  { name: 'Gemini Pro', model: 'gemini-pro', url: 'https://generativelanguage.googleapis.com/v1beta' },
  { name: 'DeepSeek Chat', model: 'deepseek-chat', url: 'https://api.deepseek.com/v1/chat/completions' },
]

const selectModel = (model) => {
  formData.value.model_name = model.model
  formData.value.url = model.url
}
</script>

<template>
  <div class="modal-overlay" @click.self="handleCancel">
    <div class="modal-container">
      <!-- Header -->
      <div class="modal-header">
        <div class="header-info">
          <div class="header-title-section">
            <h3 class="modal-title">{{ formTitle }}</h3>
            <div v-if="isRequiredConfigEdit" class="config-badge required">
              <MIcon name="shield" />
              <span>Required</span>
            </div>
            <div v-else-if="isSystemConfigEdit" class="config-badge system">
              <MIcon name="shield-check" />
              <span>System</span>
            </div>
          </div>
          <p class="modal-subtitle">
            <template v-if="isVisionConfig">
              Optional vision model. Leave all fields empty to disable.
            </template>
            <template v-else-if="isSystemConfigEdit">
              {{ getSystemDisplayName(props.config.name) }} is a core system model
            </template>
            <template v-else>
              Add a new language model provider
            </template>
          </p>
        </div>
        <button @click="handleCancel" class="btn-close">
          <MIcon name="x" />
        </button>
      </div>

      <!-- Form Content -->
      <div class="modal-content">
        <!-- Quick Select Models (create mode only) -->
        <div v-if="!isSystemConfigEdit" class="form-section">
          <label class="section-label">Quick Select Common Models</label>
          <div class="model-grid">
            <button
              v-for="model in commonModels"
              :key="model.name"
              @click="selectModel(model)"
              type="button"
              class="model-card"
            >
              <div class="model-name">{{ model.name }}</div>
              <div class="model-url">{{ model.url }}</div>
            </button>
          </div>
        </div>

        <!-- Basic Settings -->
        <div class="form-section">
          <h4 class="section-title">
            <MIcon name="settings" />
            Basic Settings
          </h4>

          <div v-if="!isSystemConfigEdit" class="form-group">
            <label class="form-label">
              Config Name <span class="required">*</span>
            </label>
            <input
              v-model="formData.name"
              type="text"
              :disabled="mode === 'edit'"
              class="form-input"
              placeholder="e.g., my_custom_llm, analysis_model"
            />
            <p v-if="mode === 'edit'" class="form-hint">
              Config name cannot be changed after creation
            </p>
            <p v-else class="form-hint">
              Choose a unique name for this configuration
            </p>
          </div>

          <div class="form-group">
            <label class="form-label">Description</label>
            <textarea
              v-model="formData.description"
              rows="2"
              class="form-textarea"
              placeholder="Brief description of this LLM configuration"
            ></textarea>
          </div>
        </div>

        <!-- API Settings -->
        <div class="form-section">
          <h4 class="section-title">
            <MIcon name="api" />
            API Configuration
          </h4>

          <div class="form-group">
            <label class="form-label">
              Model Name <span class="required">*</span>
            </label>
            <input
              v-model="formData.model_name"
              type="text"
              class="form-input"
              placeholder="e.g., gpt-4, claude-3-5-sonnet-20241022"
            />
          </div>

          <div class="form-group">
            <label class="form-label">
              API Key <span v-if="!isVisionConfig" class="required">*</span>
            </label>
            <div class="password-input">
              <input
                v-model="formData.api_key"
                :type="showApiKey ? 'text' : 'password'"
                class="form-input"
                placeholder="sk-..."
              />
              <button
                type="button"
                @click="toggleApiKeyVisibility"
                class="btn-toggle-visibility"
              >
                <MIcon :name="showApiKey ? 'eye-off' : 'eye'" />
              </button>
            </div>
          </div>

          <div class="form-group">
            <label class="form-label">
              API Base URL <span v-if="!isVisionConfig" class="required">*</span>
            </label>
            <input
              v-model="formData.url"
              type="url"
              class="form-input"
              placeholder="https://api.openai.com/v1/chat/completions"
            />
            <p v-if="isVisionConfig" class="form-hint">
              Leave empty to disable vision model
            </p>
            <p v-else class="form-hint">
              Full endpoint URL for the model API
            </p>
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
          <MIcon v-if="isSubmitting" name="loader" class="spinner" />
          <MIcon v-else name="check" />
          <span>{{ isVisionConfig && !formData.model_name.trim() ? 'Disable Vision' : (mode === 'edit' ? 'Save Changes' : 'Create Config') }}</span>
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(26, 26, 26, 0.3);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: var(--z-modal);
  padding: var(--spacing-4);
}

.modal-container {
  background: white;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  max-width: 560px;
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
  padding: var(--spacing-5) var(--spacing-6);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.header-info {
  flex: 1;
  min-width: 0;
}

.header-title-section {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  flex-wrap: wrap;
}

.modal-title {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
  line-height: var(--leading-tight);
}

.config-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: 2px var(--spacing-2);
  border-radius: var(--radius-sm);
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  line-height: 1.4;
}

.config-badge i {
  font-size: 12px;
}

.config-badge.required {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  color: var(--accent);
}

.config-badge.system {
  background: var(--surface-hover);
  color: var(--text-tertiary);
}

.modal-subtitle {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  margin: var(--spacing-1) 0 0 0;
}

.btn-close {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: transparent;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--icon-lg);
  transition: all var(--duration-base) var(--ease-out);
  flex-shrink: 0;
}

.btn-close:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.modal-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-6);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-5);
}

.form-section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.section-label {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  display: block;
  margin-bottom: var(--spacing-1);
}

.section-title {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
}

.section-title i {
  color: var(--accent);
}

.model-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: var(--spacing-2);
}

.model-card {
  padding: var(--spacing-2) var(--spacing-3);
  background: white;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  text-align: left;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.model-card:hover {
  background: var(--surface-base);
  border-color: var(--accent);
}

.model-name {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--text-primary);
  margin-bottom: 2px;
}

.model-url {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.form-label {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  display: block;
}

.required {
  color: var(--error-500);
}

.form-input,
.form-textarea {
  width: 100%;
  padding: var(--spacing-2) var(--spacing-3);
  background: white;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  color: var(--text-primary);
  transition: border-color var(--duration-base) var(--ease-out);
}

.form-input:focus,
.form-textarea:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--accent) 15%, transparent);
}

.form-input:disabled {
  background: var(--surface-hover);
  color: var(--text-tertiary);
  cursor: not-allowed;
}

.form-textarea {
  resize: none;
  font-family: inherit;
}

.form-hint {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  margin: 0;
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
  color: var(--text-tertiary);
  cursor: pointer;
  font-size: var(--icon-md);
  border-radius: var(--radius-md);
  transition: all var(--duration-base) var(--ease-out);
}

.btn-toggle-visibility:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: var(--spacing-3);
  padding: var(--spacing-5) var(--spacing-6);
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.btn-secondary {
  padding: var(--spacing-2) var(--spacing-4);
  background: transparent;
  color: var(--text-secondary);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.btn-secondary:hover {
  background: var(--surface-hover);
}

.btn-primary {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-hover);
}

.btn-primary:disabled {
  background: var(--border-strong);
  color: var(--text-tertiary);
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