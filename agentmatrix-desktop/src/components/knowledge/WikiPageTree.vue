<script setup>
import { computed } from 'vue'
import { useKnowledgeStore } from '@/stores/knowledge'
import MIcon from '@/components/icons/MIcon.vue'

const knowledgeStore = useKnowledgeStore()

const tree = computed(() => {
  const pages = knowledgeStore.pages
  const dirs = {}

  for (const page of pages) {
    const parts = page.path.split('/')
    const dir = parts.length > 1 ? parts.slice(0, -1).join('/') : ''
    const fileName = parts[parts.length - 1]

    if (!dirs[dir]) {
      dirs[dir] = []
    }
    dirs[dir].push({ ...page, fileName })
  }

  const result = []
  for (const [dir, files] of Object.entries(dirs).sort()) {
    result.push({ dir, files })
  }
  return result
})

function handlePageClick(page) {
  knowledgeStore.selectPage(page.path)
}
</script>

<template>
  <div class="page-tree">
    <div v-if="knowledgeStore.pages.length === 0" class="page-tree__empty">
      暂无页面
    </div>

    <div v-for="group in tree" :key="group.dir" class="page-tree__group">
      <div v-if="group.dir" class="page-tree__dir">
        <MIcon name="folder" />
        <span>{{ group.dir }}/</span>
      </div>
      <div
        v-for="page in group.files"
        :key="page.path"
        :class="['page-tree__item', { 'page-tree__item--active': knowledgeStore.currentPage?.path === page.path }]"
        @click="handlePageClick(page)"
      >
        <MIcon name="file-text" />
        <span class="page-tree__name">{{ page.title || page.fileName }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-tree {
  padding: var(--spacing-2);
}

.page-tree__empty {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--spacing-6);
  font-size: var(--font-sm);
}

.page-tree__group {
  margin-bottom: var(--spacing-2);
}

.page-tree__dir {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-1) var(--spacing-2);
  color: var(--text-tertiary);
  font-size: var(--font-xs);
  font-weight: var(--font-weight-medium);
}

.page-tree__item {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-1) var(--spacing-2) var(--spacing-1) var(--spacing-6);
  color: var(--text-secondary);
  font-size: var(--font-sm);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: background var(--duration-fast);
}

.page-tree__item:hover {
  background: var(--surface-hover);
}

.page-tree__item--active {
  background: var(--surface-active);
  color: var(--accent);
}

.page-tree__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>