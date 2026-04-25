<script setup>
import { useConfigStore } from '@/stores/config'
const configStore = useConfigStore()
</script>

<template>
  <input
    v-model="configStore.wizardData.user_name"
    class="me-inp"
    :class="{ done: configStore.wizardData.user_name.trim() }"
    type="text"
    placeholder="your name"
    autocomplete="off"
    spellcheck="false"
  />
</template>

<style scoped>
.me-inp {
  display: block;
  width: 100%;
  max-width: 480px;
  margin: 0 auto;
  background: transparent;
  border: none;
  border-bottom: 2px solid var(--border);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 44px;
  padding: 14px 0;
  outline: none;
  text-align: center;
  transition: border-color 0.3s;
  caret-color: var(--accent);
}

.me-inp::placeholder {
  color: var(--text-quaternary);
  font-style: normal;
  font-size: 24px;
}

.me-inp:focus {
  border-bottom-color: var(--accent);
}

.me-inp.done {
  border-bottom-color: var(--success);
}
</style>