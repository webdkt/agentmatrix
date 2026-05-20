<script setup>
import { ref } from 'vue'
import SettingsSidebar from './SettingsSidebar.vue'
import SettingsContent from './SettingsContent.vue'

const emit = defineEmits(['view-change'])

const currentCategory = ref('llm')
const contentRef = ref(null)

const categories = [
  { id: 'llm', label: 'LLM', labelZh: '大模型', icon: 'brain', desc: '配置语言模型的 API 连接信息' },
  { id: 'email-proxy', label: 'Email', labelZh: '邮件代理', icon: 'mail', desc: '设置系统邮箱，实现邮件收发代理' },
  { id: 'proxy', label: 'Proxy', labelZh: '网络代理', icon: 'shield', desc: '配置 HTTP 代理服务器' },
]

const handleCategoryChange = (categoryId) => {
  currentCategory.value = categoryId
}

const handleBack = () => {
  emit('view-change', 'email')
}

const handleSave = () => {
  contentRef.value?.save?.()
}
</script>

<template>
  <div class="settings-view">
    <SettingsSidebar
      :categories="categories"
      :current-category="currentCategory"
      @category-change="handleCategoryChange"
      @back="handleBack"
    />
    <SettingsContent
      ref="contentRef"
      :categories="categories"
      :current-category="currentCategory"
      @save="handleSave"
    />
  </div>
</template>

<style scoped>
.settings-view {
  display: flex;
  height: 100%;
  overflow: hidden;
  background: #F2F2F5;
}
</style>
