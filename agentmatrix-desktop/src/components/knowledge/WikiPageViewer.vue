<script setup>
import { computed } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import MIcon from '@/components/icons/MIcon.vue'

const knowledgeStore = useKnowledgeStore()

const renderedContent = computed(() => {
  if (!knowledgeStore.currentPage?.content) return ''
  // Simple markdown rendering - convert basic markdown to HTML
  let content = knowledgeStore.currentPage.content
  // Headers
  content = content.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  content = content.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  content = content.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  // Bold and italic
  content = content.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  content = content.replace(/\*(.+?)\*/g, '<em>$1</em>')
  // Links
  content = content.replace(/\[(.+?)\]\((.+?)\)/g, '<a href="$2">$1</a>')
  // Lists
  content = content.replace(/^- (.+)$/gm, '<li>$1</li>')
  // Line breaks
  content = content.replace(/\n\n/g, '</p><p>')
  content = '<p>' + content + '</p>'
  // Clean up empty paragraphs
  content = content.replace(/<p><\/p>/g, '')
  content = content.replace(/<p>(<h[1-6]>)/g, '$1')
  content = content.replace(/(<\/h[1-6]>)<\/p>/g, '$1')
  return content
})
</script>

<template>
  <div class="page-viewer">
    <div v-if="!knowledgeStore.currentPage" class="page-viewer__empty">
      <MIcon name="file-text" />
      <p>选择一个页面查看</p>
    </div>

    <div v-else class="page-viewer__content">
      <div class="page-viewer__header">
        <h1>{{ knowledgeStore.currentPage.path }}</h1>
      </div>
      <div class="page-viewer__body" v-html="renderedContent" />
    </div>
  </div>
</template>

<style scoped>
.page-viewer {
  width: 100%;
  height: 100%;
  overflow-y: auto;
}

.page-viewer__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: var(--text-tertiary);
  gap: var(--spacing-3);
}

.page-viewer__empty svg {
  width: 48px;
  height: 48px;
  opacity: 0.3;
}

.page-viewer__content {
  padding: var(--spacing-6);
  max-width: 800px;
  margin: 0 auto;
}

.page-viewer__header h1 {
  font-size: var(--font-xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0 0 var(--spacing-4) 0;
  word-break: break-all;
}

.page-viewer__body {
  font-size: var(--font-sm);
  line-height: 1.8;
  color: var(--text-primary);
}

.page-viewer__body :deep(h1) {
  font-size: var(--font-xl);
  margin: var(--spacing-6) 0 var(--spacing-3);
}

.page-viewer__body :deep(h2) {
  font-size: var(--font-lg);
  margin: var(--spacing-5) 0 var(--spacing-2);
}

.page-viewer__body :deep(h3) {
  font-size: var(--font-md);
  margin: var(--spacing-4) 0 var(--spacing-2);
}

.page-viewer__body :deep(strong) {
  font-weight: var(--font-weight-bold);
}

.page-viewer__body :deep(a) {
  color: var(--accent);
  text-decoration: none;
}

.page-viewer__body :deep(a:hover) {
  text-decoration: underline;
}

.page-viewer__body :deep(li) {
  margin-left: var(--spacing-4);
  list-style: disc;
}
</style>