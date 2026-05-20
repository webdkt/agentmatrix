<script setup>
import { ref, computed } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import LLMConfigList from './llm/LLMConfigList.vue'
import EmailProxyConfig from './email-proxy/EmailProxyConfig.vue'
import ProxyConfig from './proxy/ProxyConfig.vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  categories: {
    type: Array,
    required: true
  },
  currentCategory: {
    type: String,
    required: true
  }
})

const emit = defineEmits(['save'])

const settingsStore = useSettingsStore()
const contentRef = ref(null)

const currentMeta = computed(() => {
  return props.categories.find(c => c.id === props.currentCategory) || props.categories[0]
})

const currentCategoryComponent = computed(() => {
  const map = {
    'llm': LLMConfigList,
    'email-proxy': EmailProxyConfig,
    'proxy': ProxyConfig
  }
  return map[props.currentCategory] || null
})

function save() {
  contentRef.value?.save?.()
}

defineExpose({ save })
</script>

<template>
  <div class="settings-content">
    <header class="page-header">
      <div class="page-header-left">
        <div class="page-icon-wrap">
          <MIcon :name="currentMeta.icon" class="page-icon" />
        </div>
        <div class="page-title-group">
          <h1 class="page-title">{{ currentMeta.labelZh }} 配置</h1>
          <p class="page-desc">{{ currentMeta.desc }}</p>
        </div>
      </div>
      <button class="save-btn" @click="emit('save')">
        <MIcon name="check" class="save-icon" />
        <span>保存全部</span>
      </button>
    </header>

    <main class="content-body">
      <component :is="currentCategoryComponent" v-if="currentCategoryComponent" ref="contentRef" />
    </main>
  </div>
</template>

<style scoped>
.settings-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.page-header {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 40px;
  background: white;
  border-bottom: 1px solid var(--border);
}

.page-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.page-icon-wrap {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--accent-muted);
  border-radius: var(--radius-xl);
  flex-shrink: 0;
}

.page-icon {
  font-size: 22px;
  color: var(--accent);
}

.page-title-group {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.page-title {
  font-size: var(--font-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin: 0;
  line-height: 1.3;
  letter-spacing: var(--tracking-tight);
}

.page-desc {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.4;
}

.save-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  height: 36px;
  padding: 0 18px;
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-full);
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  box-shadow: 0 1px 2px rgba(166, 123, 123, 0.2);
}

.save-btn:hover {
  background: var(--accent-hover);
  box-shadow: 0 2px 6px rgba(166, 123, 123, 0.3);
  transform: translateY(-0.5px);
}

.save-icon {
  font-size: 15px;
}

.content-body {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  background: #F2F2F5;
  padding: 28px 40px 48px;
}
</style>
