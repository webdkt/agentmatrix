<script setup>
import { ref, computed, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useUIStore } from '@/stores/ui'
import SettingsSidebar from './SettingsSidebar.vue'
import SettingsContent from './SettingsContent.vue'
import MIcon from '@/components/icons/MIcon.vue'

const emit = defineEmits(['view-change'])

const settingsStore = useSettingsStore()
const uiStore = useUIStore()

// State
const currentCategory = ref('llm')

// Computed
const categories = computed(() => [
  {
    id: 'llm',
    label: 'LLM Configuration',
    icon: 'brain',
    description: 'Manage language model providers'
  },
  {
    id: 'email-proxy',
    label: 'Email Proxy',
    icon: 'mail',
    description: 'Configure email proxy service'
  },
  {
    id: 'proxy',
    label: 'HTTP Proxy',
    icon: 'shield',
    description: 'Configure HTTP proxy for network access'
  }
])

// Lifecycle
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

// Methods
const handleCategoryChange = (categoryId) => {
  currentCategory.value = categoryId
}

const handleBackClick = () => {
  emit('view-change', 'email')
}
</script>

<template>
  <div class="settings-view">
    <!-- Header -->
    <header class="settings-header">
      <div class="header-content">
        <button
          @click="handleBackClick"
          class="back-button"
          title="Back to Email"
        >
          <MIcon name="arrow-left" />
        </button>
        <div class="header-info">
          <div class="header-icon">
            <MIcon name="settings" />
          </div>
          <div>
            <h1 class="header-title">Settings</h1>
            <p class="header-subtitle">Manage your AgentMatrix configuration</p>
          </div>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <div class="settings-main">
      <!-- Sidebar -->
      <SettingsSidebar
        :categories="categories"
        :current-category="currentCategory"
        @category-change="handleCategoryChange"
      />

      <!-- Content Area -->
      <div class="settings-content-wrapper">
        <SettingsContent
          :current-category="currentCategory"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--surface-base);
}

.settings-header {
  flex-shrink: 0;
  background: white;
  border-bottom: 1px solid var(--border);
  padding: var(--spacing-6) var(--spacing-8);
}

.header-content {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
}

.back-button {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--surface-hover);
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--icon-lg);
  transition: all var(--duration-base) var(--ease-out);
}

.back-button:hover {
  background: var(--border);
}

.back-button:active {
  transform: scale(0.95);
}

.header-info {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
}

.header-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  background: var(--surface-hover);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--icon-xl);
  color: var(--text-secondary);
}

.header-title {
  font-size: var(--font-xl);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
  line-height: var(--leading-tight);
}

.header-subtitle {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
  margin: 0;
  margin-top: 2px;
}

.settings-main {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.settings-content-wrapper {
  flex: 1;
  overflow: hidden;
  display: flex;
}
</style>
