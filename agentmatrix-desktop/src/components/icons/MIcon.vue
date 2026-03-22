<template>
  <svg
    v-if="customPath"
    :width="size"
    :height="size"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="1.5"
    stroke-linecap="butt"
    stroke-linejoin="miter"
    xmlns="http://www.w3.org/2000/svg"
    class="m-icon"
    v-html="customPath"
  />
  <i
    v-else
    :class="['ti', `ti-${name}`]"
    :style="{ fontSize: size + 'px' }"
    class="m-icon"
  />
</template>

<script setup>
import { computed } from 'vue'
import { iconRegistry } from './iconRegistry.js'

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

const customPath = computed(() => {
  return iconRegistry[props.name] || null
})
</script>

<style scoped>
.m-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  vertical-align: middle;
  color: inherit;
}
</style>
