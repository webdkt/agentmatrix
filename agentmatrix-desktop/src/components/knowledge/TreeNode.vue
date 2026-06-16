<script setup>
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  node: { type: Object, required: true },
  expandedDirs: { type: Object, required: true },
  currentPath: { type: String, default: '' },
  depth: { type: Number, default: 0 },
})

const emit = defineEmits(['toggle', 'select'])

const indent = `${props.depth * 20 + 8}px`

function onToggle() {
  emit('toggle', props.node.relPath)
}

function onSelect() {
  if (props.node.type === 'file') {
    emit('select', props.node)
  }
}
</script>

<template>
  <!-- Directory -->
  <div v-if="node.type === 'dir'">
    <div
      class="tree-node tree-node--dir"
      :style="{ paddingLeft: indent }"
      @click="onToggle"
    >
      <MIcon
        :name="expandedDirs.has(node.relPath) ? 'chevron-down' : 'chevron-right'"
        class="tree-node__chevron"
      />
      <svg class="tree-node__folder" viewBox="0 0 20 20" fill="none">
        <path d="M2 5.5C2 4.67 2.67 4 3.5 4H8l1.5 2H16.5C17.33 6 18 6.67 18 7.5V14.5C18 15.33 17.33 16 16.5 16H3.5C2.67 16 2 15.33 2 14.5V5.5Z" fill="#F5C542"/>
        <path d="M2 7H18V14.5C18 15.33 17.33 16 16.5 16H3.5C2.67 16 2 15.33 2 14.5V7Z" fill="#E8A820"/>
      </svg>
      <span class="tree-node__name">{{ node.name }}</span>
    </div>
    <div v-if="expandedDirs.has(node.relPath)">
      <TreeNode
        v-for="child in node.children"
        :key="child.relPath"
        :node="child"
        :expanded-dirs="expandedDirs"
        :current-path="currentPath"
        :depth="depth + 1"
        @toggle="emit('toggle', $event)"
        @select="emit('select', $event)"
      />
    </div>
  </div>

  <!-- File -->
  <div
    v-else
    class="tree-node tree-node--file"
    :class="{ 'tree-node--active': currentPath === node.relPath }"
    :style="{ paddingLeft: indent }"
    @click="onSelect"
  >
    <span class="tree-node__spacer"></span>
    <MIcon name="file-text" class="tree-node__icon" />
    <span class="tree-node__name">{{ node.name }}</span>
  </div>
</template>

<style scoped>
.tree-node {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  transition: background 0.1s;
}

.tree-node:hover {
  background: var(--surface-hover);
}

.tree-node--active {
  background: var(--surface-active);
  color: var(--accent);
}

.tree-node__chevron {
  font-size: 12px;
  color: var(--text-tertiary);
  flex-shrink: 0;
  width: 14px;
  text-align: center;
}

.tree-node__folder {
  width: 20px;
  height: 20px;
  flex-shrink: 0;
}

.tree-node__icon {
  font-size: 16px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.tree-node__spacer {
  width: 14px;
  flex-shrink: 0;
}

.tree-node__name {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
}
</style>