<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import LLMConfigList from './llm/LLMConfigList.vue'
import EmailProxyConfig from './email-proxy/EmailProxyConfig.vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  currentCategory: {
    type: String,
    required: true
  }
})

const settingsStore = useSettingsStore()

const isLoading = ref(false)
const error = ref(null)

// Methods - MUST be defined before watch
const loadCategoryData = async (category) => {
  isLoading.value = true
  error.value = null

  try {
    switch (category) {
      case 'llm':
        await settingsStore.loadLLMConfig()
        break
      case 'email-proxy':
        // Will be implemented when Email Proxy API is ready
        break
    }
  } catch (err) {
    error.value = err.message
    console.error(`Failed to load ${category} data:`, err)
  } finally {
    isLoading.value = false
  }
}

// Computed
const currentCategoryComponent = computed(() => {
  const components = {
    'llm': LLMConfigList,
    'email-proxy': EmailProxyConfig
  }
  return components[props.currentCategory] || null
})

const categoryTitle = computed(() => {
  const titles = {
    'llm': 'LLM Configuration',
    'email-proxy': 'Email Proxy'
  }
  return titles[props.currentCategory] || 'Settings'
})

const categoryDescription = computed(() => {
  const descriptions = {
    'llm': 'Manage your language model providers and API configurations',
    'email-proxy': 'Configure email proxy service settings'
  }
  return descriptions[props.currentCategory] || ''
})

// Watch category changes to load data
watch(() => props.currentCategory, async (newCategory) => {
  await loadCategoryData(newCategory)
}, { immediate: true })

// Lifecycle
onMounted(async () => {
  await loadCategoryData(props.currentCategory)
})
</script>

<template>
  <main class="settings-content">
    <!-- Loading State -->
    <div v-if="isLoading" class="loading-state">
      <div class="loading-spinner">
        <MIcon name="loader" />
      </div>
      <p>Loading settings...</p>
    </div>

    <!-- Error State -->
    <div v-else-if="error" class="error-state">
      <div class="error-icon">
        <MIcon name="alert-circle" />
      </div>
      <h3>Failed to load settings</h3>
      <p>{{ error }}</p>
    </div>

    <!-- Content -->
    <div v-else class="content-wrapper">
      <!-- Category Header -->
      <header class="category-header">
        <div>
          <h2 class="category-title">{{ categoryTitle }}</h2>
          <p class="category-description">{{ categoryDescription }}</p>
        </div>
      </header>

      <!-- Category Content -->
      <div class="category-content">
        <component :is="currentCategoryComponent" v-if="currentCategoryComponent" />
        <div v-else class="not-found">
          <MIcon name="help-circle" />
          <p>Category not found</p>
        </div>
      </div>
    </div>
  </main>
</template>

<style scoped>
.settings-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: white;
}

.loading-state,
.error-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  gap: var(--spacing-md);
  color: var(--neutral-500);
  padding: var(--spacing-xl);
}

.loading-spinner {
  font-size: 48px;
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

.error-icon {
  font-size: 48px;
  color: var(--error-500);
}

.error-state h3 {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--neutral-700);
  margin: 0;
}

.error-state p {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  margin: 0;
}

.content-wrapper {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.category-header {
  flex-shrink: 0;
  padding: var(--spacing-xl) var(--spacing-xl) var(--spacing-lg) var(--spacing-xl);
  border-bottom: 1px solid var(--neutral-100);
}

.category-title {
  font-size: var(--font-2xl);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin: 0 0 var(--spacing-2) 0;
  line-height: var(--leading-tight);
}

.category-description {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  margin: 0;
}

.category-content {
  flex: 1;
  overflow-y: auto;
  padding: 0 var(--spacing-xl) var(--spacing-xl) var(--spacing-xl);
}

.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  gap: var(--spacing-md);
  color: var(--neutral-400);
}

.not-found i {
  font-size: 64px;
}
</style>
