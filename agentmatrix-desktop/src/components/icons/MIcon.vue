<script setup>
import { computed } from 'vue'
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

const component = computed(() => iconMap[props.name] || null)
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
