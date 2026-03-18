<script setup>
import { ref, computed, watch } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'

const props = defineProps({
  config: {
    type: Object,
    default: null
  },
  mode: {
    type: String,
    default: 'create', // 'create' or 'edit'
  }
})

const emit = defineEmits(['close', 'saved'])

const settingsStore = useSettingsStore()
const uiStore = useUIStore()

// 表单状态
const formData = ref({
  name: '',
  description: '',
  model_name: '',
  api_key: '',
  url: '',
  is_required: false,
})

const isSubmitting = ref(false)
const showApiKey = ref(false)

// 初始化表单数据
const initializeForm = () => {
  if (props.config && props.mode === 'edit') {
    formData.value = {
      name: props.config.name || '',
      description: props.config.description || '',
      model_name: props.config.model_name || '',
      api_key: props.config.api_key || '',
      url: props.config.url || '',
      is_required: props.config.is_required || false,
    }
  } else {
    // 创建模式，清空表单
    formData.value = {
      name: '',
      description: '',
      model_name: '',
      api_key: '',
      url: '',
      is_required: false,
    }
  }
}

// 监听 props.config 变化
watch(() => props.config, () => {
  initializeForm()
}, { immediate: true })

// 计算属性
const isEditMode = computed(() => props.mode === 'edit')

const formTitle = computed(() => {
  return isEditMode.value ? `Edit LLM Config: ${props.config?.name}` : 'Create New LLM Config'
})

const canSubmit = computed(() => {
  return formData.value.name.trim() &&
         formData.value.model_name.trim() &&
         formData.value.api_key.trim() &&
         !isSubmitting.value
})

// 方法
const handleSubmit = async () => {
  if (!canSubmit.value) return

  isSubmitting.value = true
  try {
    if (isEditMode.value) {
      // 更新现有配置
      await settingsStore.saveLLMConfig(props.config.name, formData.value)
      uiStore.showNotification(`LLM config "${formData.value.name}" updated successfully`, 'success')
    } else {
      // 创建新配置
      await settingsStore.createLLMConfig(formData.value)
      uiStore.showNotification(`LLM config "${formData.value.name}" created successfully`, 'success')
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

// 预设模型列表
const commonModels = [
  { name: 'GPT-4', url: 'https://api.openai.com/v1' },
  { name: 'GPT-3.5 Turbo', url: 'https://api.openai.com/v1' },
  { name: 'Claude 3 Opus', url: 'https://api.anthropic.com/v1' },
  { name: 'Claude 3 Sonnet', url: 'https://api.anthropic.com/v1' },
  { name: 'Gemini Pro', url: 'https://generativelanguage.googleapis.com/v1' },
]

const selectModel = (model) => {
  formData.value.model_name = model.name
  formData.value.url = model.url
}
</script>

<template>
  <div class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4">
    <div class="bg-white rounded-2xl shadow-elevated max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
      <!-- Header -->
      <div class="px-6 py-4 border-b border-surface-200 flex items-center justify-between flex-shrink-0">
        <div>
          <h3 class="text-lg font-semibold text-surface-900">{{ formTitle }}</h3>
          <p class="text-sm text-surface-500 mt-1">
            {{ isEditMode ? 'Update your LLM configuration' : 'Add a new language model provider' }}
          </p>
        </div>
        <button
          @click="handleCancel"
          class="w-8 h-8 rounded-lg hover:bg-surface-100 flex items-center justify-center transition-colors"
        >
          <i class="ti ti-x text-surface-400 hover:text-surface-600"></i>
        </button>
      </div>

      <!-- Form Content -->
      <div class="flex-1 overflow-y-auto p-6 space-y-6">
        <!-- Quick Select Models (仅创建模式) -->
        <div v-if="!isEditMode" class="p-4 bg-surface-50 rounded-xl">
          <label class="block text-sm font-medium text-surface-700 mb-3">
            Quick Select Common Models
          </label>
          <div class="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button
              v-for="model in commonModels"
              :key="model.name"
              @click="selectModel(model)"
              type="button"
              class="px-3 py-2 text-left bg-white hover:bg-primary-50 border border-surface-200 hover:border-primary-300 rounded-lg transition-all text-sm"
            >
              <div class="font-medium text-surface-900">{{ model.name }}</div>
              <div class="text-xs text-surface-500 truncate">{{ model.url }}</div>
            </button>
          </div>
        </div>

        <!-- Basic Settings -->
        <div class="space-y-4">
          <div>
            <label class="block text-sm font-medium text-surface-700 mb-1.5">
              Config Name <span class="text-rose-500">*</span>
            </label>
            <input
              v-model="formData.name"
              type="text"
              :disabled="isEditMode"
              class="w-full px-3 py-2 bg-white border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent disabled:bg-surface-100 disabled:text-surface-500"
              placeholder="e.g., openai, anthropic, custom_llm"
            />
            <p v-if="isEditMode" class="mt-1 text-xs text-surface-500">
              Config name cannot be changed after creation
            </p>
          </div>

          <div>
            <label class="block text-sm font-medium text-surface-700 mb-1.5">
              Description
            </label>
            <textarea
              v-model="formData.description"
              rows="2"
              class="w-full px-3 py-2 bg-white border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
              placeholder="Brief description of this LLM configuration"
            ></textarea>
          </div>
        </div>

        <!-- API Settings -->
        <div class="space-y-4">
          <h4 class="text-sm font-semibold text-surface-900 flex items-center gap-2">
            <i class="ti ti-api text-primary-600"></i>
            API Configuration
          </h4>

          <div>
            <label class="block text-sm font-medium text-surface-700 mb-1.5">
              Model Name <span class="text-rose-500">*</span>
            </label>
            <input
              v-model="formData.model_name"
              type="text"
              class="w-full px-3 py-2 bg-white border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="e.g., gpt-4, claude-3-opus-20240229"
            />
          </div>

          <div>
            <label class="block text-sm font-medium text-surface-700 mb-1.5">
              API Key <span class="text-rose-500">*</span>
            </label>
            <div class="relative">
              <input
                v-model="formData.api_key"
                :type="showApiKey ? 'text' : 'password'"
                class="w-full px-3 py-2 pr-20 bg-white border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                placeholder="sk-..."
              />
              <button
                type="button"
                @click="toggleApiKeyVisibility"
                class="absolute right-2 top-1/2 -translate-y-1/2 px-2 py-1 text-xs text-surface-500 hover:text-surface-700 hover:bg-surface-100 rounded transition-colors"
              >
                <i :class="showApiKey ? 'ti ti-eye-off' : 'ti ti-eye'"></i>
                {{ showApiKey ? 'Hide' : 'Show' }}
              </button>
            </div>
          </div>

          <div>
            <label class="block text-sm font-medium text-surface-700 mb-1.5">
              API Base URL
            </label>
            <input
              v-model="formData.url"
              type="url"
              class="w-full px-3 py-2 bg-white border border-surface-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              placeholder="https://api.example.com/v1"
            />
            <p class="mt-1 text-xs text-surface-500">
              Leave empty to use model's default endpoint
            </p>
          </div>
        </div>

        <!-- Advanced Settings -->
        <div class="space-y-4">
          <h4 class="text-sm font-semibold text-surface-900 flex items-center gap-2">
            <i class="ti ti-adjustments text-primary-600"></i>
            Advanced Settings
          </h4>

          <label class="flex items-center gap-3 cursor-pointer">
            <input
              v-model="formData.is_required"
              type="checkbox"
              class="w-4 h-4 rounded border-surface-300 text-primary-600 focus:ring-primary-500"
            />
            <div class="flex-1">
              <div class="text-sm font-medium text-surface-700">Required Configuration</div>
              <div class="text-xs text-surface-500">
                Mark this as a required configuration for the system
              </div>
            </div>
          </label>
        </div>
      </div>

      <!-- Footer -->
      <div class="px-6 py-4 border-t border-surface-200 flex items-center justify-end gap-3 flex-shrink-0">
        <button
          @click="handleCancel"
          type="button"
          class="px-4 py-2 text-surface-700 hover:bg-surface-100 rounded-lg transition-colors font-medium"
        >
          Cancel
        </button>
        <button
          @click="handleSubmit"
          :disabled="!canSubmit || isSubmitting"
          type="submit"
          class="px-4 py-2 bg-primary-600 hover:bg-primary-700 disabled:bg-surface-300 disabled:text-surface-500 text-white rounded-lg transition-colors font-medium flex items-center gap-2"
        >
          <i v-if="isSubmitting" class="ti ti-loader animate-spin"></i>
          <i v-else class="ti ti-check"></i>
          {{ isEditMode ? 'Save Changes' : 'Create Config' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>


</style>
