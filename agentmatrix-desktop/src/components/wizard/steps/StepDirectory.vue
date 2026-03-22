<script setup>
import { useConfigStore } from '@/stores/config'
const configStore = useConfigStore()
</script>

<template>
  <div class="me-dir" @click="configStore.selectDirectory()">
    <span class="me-dir-path" :class="{ has: configStore.wizardData.matrix_world_path }">
      {{ configStore.wizardData.matrix_world_path || 'select workspace directory' }}
    </span>
    <span class="me-dir-browse">browse</span>
  </div>
</template>

<style scoped>
.me-dir {
  max-width: 480px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 2px solid var(--parchment-300);
  padding: 12px 0;
  cursor: pointer;
  transition: border-color 0.3s;
}

.me-dir:hover {
  border-bottom-color: var(--vermillion);
}

.me-dir-path {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 20px;
  color: var(--ink-ghost);
  text-align: center;
}

.me-dir-path.has {
  color: var(--ink-900);
}

.me-dir-browse {
  font-size: 12px;
  color: var(--amber);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  flex-shrink: 0;
  transition: color 0.2s;
  font-weight: 600;
}

.me-dir:hover .me-dir-browse {
  color: var(--vermillion);
}
</style>