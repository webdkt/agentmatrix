<script setup>
import { useKnowledgeStore } from '@/stores/knowledge'
import MIcon from '@/components/icons/MIcon.vue'

const emit = defineEmits(['create', 'select'])
const knowledgeStore = useKnowledgeStore()

function handleSelect(kb) {
  emit('select', kb)
}
</script>

<template>
  <div class="kb-list">
    <div class="kb-list__header">
      <h2>知识库</h2>
      <button class="kb-list__add-btn" @click="emit('create')">
        <MIcon name="plus" />
        <span>添加知识库</span>
      </button>
    </div>

    <div v-if="knowledgeStore.loading" class="kb-list__loading">
      加载中...
    </div>

    <div v-else-if="knowledgeStore.kbs.length === 0" class="kb-list__empty">
      <MIcon name="book" />
      <p>还没有知识库</p>
      <button class="kb-list__create-btn" @click="emit('create')">
        创建第一个知识库
      </button>
    </div>

    <div v-else class="kb-list__items">
      <div
        v-for="kb in knowledgeStore.kbs"
        :key="kb.name"
        class="kb-list__item"
        @click="handleSelect(kb)"
      >
        <div class="kb-list__item-icon">
          <MIcon name="book" />
        </div>
        <div class="kb-list__item-info">
          <div class="kb-list__item-name">{{ kb.name }}</div>
          <div class="kb-list__item-meta">
            <span v-if="kb.has_schema" class="kb-list__status--ready">已就绪</span>
            <span v-else class="kb-list__status--pending">未初始化</span>
            <span class="kb-list__page-count">{{ kb.page_count }} 个页面</span>
          </div>
        </div>
        <MIcon name="chevron-right" />
      </div>
    </div>
  </div>
</template>

<style scoped>
.kb-list {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: var(--spacing-6);
  overflow-y: auto;
}

.kb-list__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-6);
}

.kb-list__header h2 {
  font-size: var(--font-xl);
  font-weight: var(--font-weight-bold);
  color: var(--text-primary);
  margin: 0;
}

.kb-list__add-btn {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--font-sm);
  transition: opacity var(--duration-fast);
}

.kb-list__add-btn:hover {
  opacity: 0.9;
}

.kb-list__loading {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--spacing-10);
}

.kb-list__empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-4);
  padding: var(--spacing-10);
  color: var(--text-tertiary);
}

.kb-list__empty svg {
  width: 48px;
  height: 48px;
  opacity: 0.3;
}

.kb-list__create-btn {
  padding: var(--spacing-2) var(--spacing-4);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: var(--font-sm);
}

.kb-list__items {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.kb-list__item {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  background: var(--surface-secondary);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--duration-fast);
}

.kb-list__item:hover {
  background: var(--surface-hover);
}

.kb-list__item-icon {
  color: var(--accent);
}

.kb-list__item-info {
  flex: 1;
}

.kb-list__item-name {
  font-weight: var(--font-weight-medium);
  color: var(--text-primary);
}

.kb-list__item-meta {
  display: flex;
  gap: var(--spacing-3);
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  margin-top: var(--spacing-1);
}

.kb-list__status--ready {
  color: var(--success);
}

.kb-list__status--pending {
  color: var(--warning);
}
</style>