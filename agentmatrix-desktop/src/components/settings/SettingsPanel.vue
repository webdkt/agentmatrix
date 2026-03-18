<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'
import LLMConfigForm from './LLMConfigForm.vue'
const emit = defineEmits(['view-change'])

const settingsStore = useSettingsStore()
const uiStore = useUIStore()

// 状态
const currentView = ref('main') // 'main', 'llm', 'agents'
const showLLMForm = ref(false)
const editingConfig = ref(null)
const formMode = ref('create') // 'create' or 'edit'

// 计算属性
const llmConfigs = computed(() => {
  return settingsStore.llmConfigs || []
})

const requiredConfigs = computed(() => {
  return llmConfigs.value.filter(c => c.is_required)
})

const customConfigs = computed(() => {
  return llmConfigs.value.filter(c => !c.is_required)
})

// 生命周期
onMounted(async () => {
  try {
    await Promise.all([
      settingsStore.loadConfigStatus(),
      settingsStore.loadLLMConfig()
    ])
  } catch (error) {
    console.error('Failed to load settings:', error)
    uiStore.showNotification('Failed to load settings', 'error')
  }
})

// 方法
const switchView = (view) => {
  currentView.value = view
}

const formatUrl = (url) => {
  if (!url) return 'Not configured'
  try {
    const urlObj = new URL(url)
    return urlObj.hostname
  } catch {
    return url
  }
}

const openCreateForm = () => {
  editingConfig.value = null
  formMode.value = 'create'
  showLLMForm.value = true
}

const openEditForm = (config) => {
  editingConfig.value = config
  formMode.value = 'edit'
  showLLMForm.value = true
}

const closeForm = () => {
  showLLMForm.value = false
  editingConfig.value = null
}

const handleConfigSaved = async () => {
  // 重新加载配置列表
  try {
    await settingsStore.loadLLMConfig()
  } catch (error) {
    console.error('Failed to reload configs:', error)
  }
}

const handleDeleteConfig = async (configName) => {
  if (!confirm(`Are you sure you want to delete the LLM config "${configName}"?`)) {
    return
  }

  try {
    await settingsStore.deleteLLMConfig(configName)
    uiStore.showNotification(`LLM config "${configName}" deleted`, 'success')
  } catch (error) {
    console.error('Failed to delete config:', error)
    uiStore.showNotification(`Failed to delete: ${error.message}`, 'error')
  }
}
</script>

<template>
    <div class="flex-1 flex flex-col h-full bg-gradient-to-br from-surface-50/50 to-white overflow-hidden">
    <!-- Settings Header -->
    <header class="glass border-b border-surface-200/60 px-8 py-5 flex-shrink-0">
      <div class="flex items-center gap-4">
        <button
          @click="emit('view-change', 'email')"
          class="w-10 h-10 rounded-xl bg-surface-100 hover:bg-surface-200 flex items-center justify-center transition-all duration-200 btn-press"
          title="Back to Email"
        >
          <i class="ti ti-arrow-left text-surface-600"></i>
        </button>
        <div class="w-12 h-12 rounded-2xl bg-gradient-to-br from-surface-100 to-surface-50 flex items-center justify-center shadow-card">
          <i class="ti ti-settings text-2xl text-surface-600"></i>
        </div>
        <div>
          <h1 class="text-xl font-bold text-surface-900 tracking-tight">Settings</h1>
          <p class="text-sm text-surface-500">Manage your AgentMatrix configuration</p>
        </div>
      </div>
    </header>

    <!-- Settings Content -->
    <div class="flex-1 overflow-y-auto p-8">
      <!-- Main Settings View -->
      <div v-show="currentView === 'main'" class="max-w-4xl mx-auto">
        <h2 class="text-lg font-semibold text-surface-900 mb-6">Configuration Categories</h2>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-6">
          <!-- LLM Backend Settings Card -->
          <div @click="switchView('llm')"
               class="group cursor-pointer bg-white rounded-2xl p-6 shadow-card border border-surface-200/60 hover:shadow-elevated hover:border-surface-300 transition-all duration-300">
            <div class="flex items-start gap-5">
              <div class="w-14 h-14 rounded-2xl bg-gradient-to-br from-accent-100 to-accent-50 flex items-center justify-center flex-shrink-0 group-hover:shadow-glow-sm transition-all duration-300">
                <i class="ti ti-brain text-2xl text-accent-600"></i>
              </div>
              <div class="flex-1 min-w-0">
                <h3 class="text-lg font-semibold text-surface-900 mb-1 group-hover:text-accent-600 transition-colors">LLM Backend</h3>
                <p class="text-sm text-surface-500 leading-relaxed">Configure language model providers, API keys, and model settings</p>
                <div class="mt-3 flex items-center gap-2 text-xs text-surface-400">
                  <i class="ti ti-plug"></i>
                  <span>{{ llmConfigs.length }} providers configured</span>
                </div>
              </div>
              <i class="ti ti-chevron-right text-surface-300 group-hover:text-accent-500 group-hover:translate-x-1 transition-all"></i>
            </div>
          </div>
        </div>
      </div>

      <!-- LLM Backend Settings View -->
      <div v-show="currentView === 'llm'" class="max-w-5xl mx-auto">
        <div class="flex items-center justify-between mb-6">
          <div class="flex items-center gap-4">
            <button @click="switchView('main')"
                    class="w-10 h-10 rounded-xl bg-surface-100 hover:bg-surface-200 flex items-center justify-center transition-all duration-200 btn-press">
              <i class="ti ti-arrow-left text-surface-600"></i>
            </button>
            <div>
              <h2 class="text-lg font-semibold text-surface-900">LLM Backend Settings</h2>
              <p class="text-sm text-surface-500">Configure your language model providers</p>
            </div>
          </div>
          <button
            @click="openCreateForm"
            class="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-xl font-medium transition-all duration-200 btn-press flex items-center gap-2 shadow-glow-sm"
          >
            <i class="ti ti-plus"></i>
            <span>Add Config</span>
          </button>
        </div>

        <!-- Required Configs Section -->
        <div v-if="requiredConfigs.length > 0" class="mb-8">
          <h3 class="text-sm font-semibold text-surface-500 uppercase tracking-wider mb-4 flex items-center gap-2">
            <i class="ti ti-shield-check text-accent-500"></i>
            Required Configurations
          </h3>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <div v-for="config in requiredConfigs" :key="config.name" class="group bg-white rounded-xl p-5 shadow-card border border-accent-200 hover:shadow-elevated hover:border-surface-300 transition-all duration-300">
              <!-- Card Header -->
              <div class="flex items-start justify-between mb-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-accent-400 to-accent-600 flex items-center justify-center text-white shadow-card">
                  <i class="ti ti-brain text-lg"></i>
                </div>
                <div class="flex items-center gap-1">
                  <span class="px-2 py-0.5 bg-accent-100 text-accent-700 text-xs rounded-full font-medium">Required</span>
                </div>
              </div>

              <!-- Card Content -->
              <h4 class="font-semibold text-surface-900 mb-1 truncate">{{ config.name }}</h4>
              <p class="text-xs text-surface-500 mb-3 line-clamp-2">{{ config.description }}</p>

              <!-- Model Info -->
              <div class="space-y-1.5 mb-4">
                <div class="flex items-center gap-2 text-xs text-surface-600">
                  <i class="ti ti-database text-surface-400"></i>
                  <span class="truncate">{{ config.model_name || 'Not configured' }}</span>
                </div>
                <div class="flex items-center gap-2 text-xs text-surface-600">
                  <i class="ti ti-link text-surface-400"></i>
                  <span class="truncate">{{ formatUrl(config.url) }}</span>
                </div>
              </div>

              <!-- Actions -->
              <div class="flex items-center gap-2 pt-3 border-t border-surface-100">
                <button
                  @click="openEditForm(config)"
                  class="flex-1 px-3 py-1.5 bg-surface-100 hover:bg-surface-200 text-surface-700 rounded-lg text-sm font-medium transition-all"
                >
                  Edit
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Custom Configs Section -->
        <div v-if="customConfigs.length > 0">
          <h3 class="text-sm font-semibold text-surface-500 uppercase tracking-wider mb-4 flex items-center gap-2">
            <i class="ti ti-sliders text-surface-400"></i>
            Custom Configurations
          </h3>
          <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <div v-for="config in customConfigs" :key="config.name" class="group bg-white rounded-xl p-5 shadow-card border border-surface-200/60 hover:shadow-elevated hover:border-surface-300 transition-all duration-300">
              <!-- Card Header -->
              <div class="flex items-start justify-between mb-3">
                <div class="w-10 h-10 rounded-xl bg-gradient-to-br from-surface-300 to-surface-400 flex items-center justify-center text-white shadow-card">
                  <i class="ti ti-cpu text-lg"></i>
                </div>
                <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    @click="openEditForm(config)"
                    class="w-7 h-7 rounded-lg hover:bg-surface-100 flex items-center justify-center text-surface-400 hover:text-accent-600 transition-all"
                    title="Edit">
                    <i class="ti ti-pencil text-xs"></i>
                  </button>
                  <button
                    @click="handleDeleteConfig(config.name)"
                    class="w-7 h-7 rounded-lg hover:bg-rose-50 flex items-center justify-center text-surface-400 hover:text-rose-600 transition-all"
                    title="Delete">
                    <i class="ti ti-trash text-xs"></i>
                  </button>
                </div>
              </div>

              <!-- Card Content -->
              <h4 class="font-semibold text-surface-900 mb-1 truncate">{{ config.name }}</h4>
              <p class="text-xs text-surface-500 mb-3 line-clamp-2">{{ config.description || 'Custom LLM configuration' }}</p>

              <!-- Model Info -->
              <div class="space-y-1.5">
                <div class="flex items-center gap-2 text-xs text-surface-600">
                  <i class="ti ti-database text-surface-400"></i>
                  <span class="truncate">{{ config.model_name || 'Not configured' }}</span>
                </div>
                <div class="flex items-center gap-2 text-xs text-surface-600">
                  <i class="ti ti-link text-surface-400"></i>
                  <span class="truncate">{{ formatUrl(config.url) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Empty State -->
        <div v-if="llmConfigs.length === 0" class="py-16">
          <div class="w-20 h-20 mx-auto mb-6 rounded-2xl bg-surface-100 flex items-center justify-center">
            <i class="ti ti-brain-off text-4xl text-surface-300"></i>
          </div>
          <h3 class="text-lg font-semibold text-surface-700 mb-2">No LLM configurations</h3>
          <p class="text-sm text-surface-500 mb-6">Add LLM configurations to enable AI capabilities</p>
          <button
            @click="openCreateForm"
            class="px-6 py-2.5 bg-primary-600 hover:bg-primary-700 text-white rounded-xl font-medium transition-all duration-200 btn-press shadow-glow-sm"
          >
            <i class="ti ti-plus mr-2"></i>
            Add Your First Config
          </button>
        </div>
      </div>
    </div>

    <!-- LLM Config Form Modal -->
    <LLMConfigForm
      v-if="showLLMForm"
      :config="editingConfig"
      :mode="formMode"
      @close="closeForm"
      @saved="handleConfigSaved"
    />
  </div>
</template>

<style scoped>
.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.glass {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(10px);
}

.shadow-card {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}


.shadow-glow-sm {
  box-shadow: 0 0 20px rgba(14, 165, 233, 0.3);
}

.btn-press {
  transition: all 0.2s;
}

.btn-press:active {
  transform: scale(0.95);
}
</style>
