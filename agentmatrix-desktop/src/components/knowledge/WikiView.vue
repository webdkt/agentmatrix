<script setup>
import { ref } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import WikiSidebar from './WikiSidebar.vue'
import WikiPageViewer from './WikiPageViewer.vue'
import WikiChatPanel from './WikiChatPanel.vue'
import MIcon from '@/components/icons/MIcon.vue'

const emit = defineEmits(['back'])
const knowledgeStore = useKnowledgeStore()

const chatOpen = ref(false)

function toggleChat() {
  chatOpen.value = !chatOpen.value
}
</script>

<template>
  <div class="wiki-view">
    <div class="wiki-view__header">
      <button class="wiki-view__back" @click="emit('back')">
        <MIcon name="arrow-left" />
      </button>
      <h2>{{ knowledgeStore.currentKB?.name || '知识库' }}</h2>
      <button class="wiki-view__chat-toggle" @click="toggleChat" :title="chatOpen ? '收起聊天' : '展开聊天'">
        <MIcon name="message-circle" />
      </button>
    </div>

    <div class="wiki-view__body">
      <WikiSidebar class="wiki-view__sidebar" />
      <WikiPageViewer class="wiki-view__content" />
      <WikiChatPanel
        v-if="chatOpen"
        class="wiki-view__chat"
        @close="chatOpen = false"
      />
    </div>
  </div>
</template>

<style scoped>
.wiki-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.wiki-view__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.wiki-view__header h2 {
  flex: 1;
  font-size: var(--font-lg);
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
  margin: 0;
}

.wiki-view__back,
.wiki-view__chat-toggle {
  background: none;
  border: none;
  color: var(--text-secondary);
  cursor: pointer;
  padding: var(--spacing-1);
  border-radius: var(--radius-sm);
}

.wiki-view__back:hover,
.wiki-view__chat-toggle:hover {
  background: var(--surface-hover);
  color: var(--text-primary);
}

.wiki-view__chat-toggle {
  color: var(--accent);
}

.wiki-view__body {
  flex: 1;
  display: flex;
  overflow: hidden;
  position: relative;
}

.wiki-view__sidebar {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--border);
}

.wiki-view__content {
  flex: 1;
  overflow: hidden;
}

.wiki-view__chat {
  position: absolute;
  right: 0;
  top: 0;
  bottom: 0;
  width: 400px;
  z-index: 10;
}
</style>