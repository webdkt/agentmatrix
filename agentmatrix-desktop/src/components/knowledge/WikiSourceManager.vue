<script setup>
import { ref } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import MIcon from '@/components/icons/MIcon.vue'

const knowledgeStore = useKnowledgeStore()

const newPath = ref('')
const newDescription = ref('')
const adding = ref(false)
const error = ref(null)

async function handleAdd() {
  if (!newPath.value.trim()) return

  adding.value = true
  error.value = null

  try {
    await knowledgeStore.addSource(newPath.value, newDescription.value)
    newPath.value = ''
    newDescription.value = ''
  } catch (e) {
    error.value = e.message || '添加失败'
  } finally {
    adding.value = false
  }
}

async function handleDelete(source) {
  if (!confirm(`确定删除源目录？\n${source.path}`)) return

  try {
    await knowledgeStore.removeSource(source.id)
  } catch (e) {
    error.value = e.message || '删除失败'
  }
}
</script>

<template>
  <div class="source-mgr">
    <div class="source-mgr__add">
      <input
        v-model="newPath"
        type="text"
        placeholder="源目录路径（支持 ~）"
        :disabled="adding"
        @keyup.enter="handleAdd"
      />
      <input
        v-model="newDescription"
        type="text"
        placeholder="描述（可选）"
        :disabled="adding"
        @keyup.enter="handleAdd"
      />
      <button class="source-mgr__add-btn" @click="handleAdd" :disabled="adding || !newPath.trim()">
        <MIcon name="plus" />
      </button>
    </div>

    <div v-if="error" class="source-mgr__error">{{ error }}</div>

    <div v-if="knowledgeStore.sources.length === 0" class="source-mgr__empty">
      暂无源目录
    </div>

    <div v-else class="source-mgr__list">
      <div v-for="src in knowledgeStore.sources" :key="src.id" class="source-mgr__item">
        <div class="source-mgr__item-info">
          <div class="source-mgr__item-path">{{ src.path }}</div>
          <div v-if="src.description" class="source-mgr__item-desc">{{ src.description }}</div>
        </div>
        <button class="source-mgr__delete" @click="handleDelete(src)" title="删除">
          <MIcon name="trash" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.source-mgr {
  padding: var(--spacing-3);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.source-mgr__add {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.source-mgr__add input {
  width: 100%;
  padding: var(--spacing-2);
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  color: var(--text-primary);
  font-size: var(--font-xs);
}

.source-mgr__add input:focus {
  outline: none;
  border-color: var(--accent);
}

.source-mgr__add-btn {
  align-self: flex-end;
  padding: var(--spacing-1) var(--spacing-3);
  background: var(--accent);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: var(--font-xs);
}

.source-mgr__add-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.source-mgr__error {
  color: var(--error);
  font-size: var(--font-xs);
}

.source-mgr__empty {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--spacing-6);
  font-size: var(--font-sm);
}

.source-mgr__list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.source-mgr__item {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2);
  background: var(--surface-secondary);
  border-radius: var(--radius-sm);
}

.source-mgr__item-info {
  flex: 1;
  min-width: 0;
}

.source-mgr__item-path {
  font-size: var(--font-xs);
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.source-mgr__item-desc {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  margin-top: 2px;
}

.source-mgr__delete {
  background: none;
  border: none;
  color: var(--text-tertiary);
  cursor: pointer;
  padding: var(--spacing-1);
  border-radius: var(--radius-sm);
}

.source-mgr__delete:hover {
  color: var(--error);
  background: var(--surface-hover);
}
</style>