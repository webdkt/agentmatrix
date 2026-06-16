<script setup>
import { ref, watch } from 'vue'
import { invoke } from '@tauri-apps/api/core'
import { useKnowledgeStore } from '@/stores/knowledge'
import MIcon from '@/components/icons/MIcon.vue'
import TreeNode from './TreeNode.vue'

const knowledgeStore = useKnowledgeStore()

const tree = ref([])
const loading = ref(false)
const expandedDirs = ref(new Set())

const WIKI_SKIP = new Set(['_schema.md', 'log.md', 'knowledge.db', 'knowledge.db-shm', 'knowledge.db-wal'])
const DIR_SKIP = new Set(['log_archive', 'raw'])

async function loadTree() {
  if (!knowledgeStore.currentKB) return

  loading.value = true
  try {
    const config = await invoke('get_config')
    const wikiRoot = `${config.matrix_world_path}/workspace/wiki/${knowledgeStore.currentKB.name}`
    tree.value = await buildTree(wikiRoot, '')
    expandedDirs.value = new Set(collectDirPaths(tree.value))
  } catch (e) {
    console.error('Failed to load page tree:', e)
    tree.value = []
  } finally {
    loading.value = false
  }
}

function collectDirPaths(nodes) {
  const paths = []
  for (const node of nodes) {
    if (node.type === 'dir') {
      paths.push(node.relPath)
      paths.push(...collectDirPaths(node.children))
    }
  }
  return paths
}

async function buildTree(basePath, relPath) {
  const fullPath = relPath ? `${basePath}/${relPath}` : basePath
  let entries
  try {
    entries = await invoke('read_directory', { path: fullPath })
  } catch {
    return []
  }

  const result = []
  for (const entry of entries) {
    const subRel = relPath ? `${relPath}/${entry.name}` : entry.name

    if (entry.is_dir) {
      if (DIR_SKIP.has(entry.name)) continue
      const children = await buildTree(basePath, subRel)
      result.push({ type: 'dir', name: entry.name, relPath: subRel, children })
    } else {
      if (!entry.name.endsWith('.md')) continue
      if (WIKI_SKIP.has(entry.name)) continue
      result.push({ type: 'file', name: entry.name, relPath: subRel })
    }
  }
  return result
}

function toggleDir(dirPath) {
  if (expandedDirs.value.has(dirPath)) {
    expandedDirs.value.delete(dirPath)
  } else {
    expandedDirs.value.add(dirPath)
  }
}

function handlePageClick(page) {
  knowledgeStore.selectPage(page.relPath)
}

watch(() => knowledgeStore.currentKB, () => {
  if (knowledgeStore.currentKB) loadTree()
}, { immediate: true })
</script>

<template>
  <div class="page-tree">
    <div v-if="loading" class="page-tree__empty">加载中...</div>
    <div v-else-if="tree.length === 0" class="page-tree__empty">暂无内容</div>
    <div v-else class="page-tree__root">
      <TreeNode
        v-for="node in tree"
        :key="node.relPath"
        :node="node"
        :expanded-dirs="expandedDirs"
        :current-path="knowledgeStore.currentPage?.path"
        :depth="0"
        @toggle="toggleDir"
        @select="handlePageClick"
      />
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

.page-tree__root {
  display: flex;
  flex-direction: column;
  gap: 1px;
}
</style>