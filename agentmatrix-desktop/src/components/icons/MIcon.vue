<script setup>
import { computed } from 'vue'
import * as LucideIcons from 'lucide-vue-next'
import { iconMap } from './iconRegistry.js'

const props = defineProps({
  name: {
    type: String,
    required: true,
  },
  size: {
    type: [Number, String],
    default: 20,
  },
})

// kebab-case → PascalCase: "file-search" → "FileSearch"
function toPascalCase(str) {
  return str.replace(/(^|-)(\w)/g, (_, _sep, c) => c.toUpperCase())
}

const component = computed(() => {
  // Check alias registry first (logo, agent, dispatch, etc.)
  if (iconMap[props.name]) return iconMap[props.name]
  // Auto-lookup from all Lucide icons
  return LucideIcons[toPascalCase(props.name)] || null
})
</script>

<template>
  <component
    v-if="component"
    :is="component"
    :size="size"
    :stroke-width="1.75"
    class="m-icon"
  />
  <span
    v-else
    class="m-icon m-icon--fallback"
    :style="{ fontSize: size + 'px' }"
  >?</span>
</template>

<style scoped>
.m-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  vertical-align: middle;
  color: inherit;
}

.m-icon--fallback {
  opacity: 0.3;
}
</style>
