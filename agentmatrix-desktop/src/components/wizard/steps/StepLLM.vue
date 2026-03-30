<script setup>
import { computed, ref, watch } from 'vue'
import { useConfigStore } from '@/stores/config'
import ModelSelector from '@/components/wizard/ModelSelector.vue'

const props = defineProps({
  which: { type: String, required: true }, // 'llm' or 'slm'
  errors: { type: Object, default: () => ({}) },
  stepIdx: { type: String, default: '3' },
})

const emit = defineEmits(['valid-change'])

const configStore = useConfigStore()

const field = computed(() => props.which === 'llm' ? 'default_llm' : 'default_slm')
const data = computed(() => configStore.wizardData[field.value])

// ModelSelector state
const modelState = ref('empty') // 'empty' | 'known' | 'new'

function onModelChange(val) {
  data.value.model_name = val
}

function onProviderChange(val) {
  data.value.provider = val
}

function onUrlChange(val) {
  // Only update URL if it's a valid preset URL (not empty)
  // This prevents clearing URL when typing doesn't match any model
  if (val && val.trim()) {
    data.value.url = val
  }
}

function onModelState(state) {
  modelState.value = state
}

// Validation
const isValid = computed(() => {
  return data.value.model_name.trim() && data.value.api_key.trim() && data.value.url
})

watch(isValid, (v) => emit('valid-change', v), { immediate: true })

// Error keys
const prefix = computed(() => props.which === 'llm' ? 'brain' : 'cerebellum')
const modelError = computed(() => props.errors[`${props.stepIdx}.${prefix.value}-model`])
const keyError = computed(() => props.errors[`${props.stepIdx}.${prefix.value}-key`])

function togEye(btn) {
  const inp = btn.previousElementSibling
  if (inp.type === 'password') { inp.type = 'text'; btn.textContent = '\u25ce' }
  else { inp.type = 'password'; btn.textContent = '\u25c9' }
}
</script>

<template>
  <div class="me-llm">
    <!-- Model selector -->
    <div class="me-fg" :class="{ 'me-error': modelError }">
      <ModelSelector
        :presets="configStore.llmPresets"
        :model-value="data.model_name"
        :provider="data.provider"
        @update:model-value="onModelChange"
        @update:provider="onProviderChange"
        @update:url="onUrlChange"
        @state-change="onModelState"
      />
    </div>

    <!-- API Key -->
    <div class="me-fg" :class="{ 'me-error': keyError }">
      <div class="me-pw">
        <input
          v-model="data.api_key"
          class="me-inp"
          type="password"
          placeholder="api key"
          spellcheck="false"
          @keydown.enter="$emit('enter')"
        />
        <button class="me-eye" @click="togEye($event.target)">&#x25c9;</button>
      </div>
    </div>

    <!-- URL (always visible) -->
    <div class="me-fg me-url-row">
      <input
        v-model="data.url"
        class="me-url"
        type="text"
        placeholder="api url"
        spellcheck="false"
        @keydown.enter="$emit('enter')"
      />
    </div>
  </div>
</template>

<style scoped>
.me-llm {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

/* Error state */
.me-error :deep(.ms-input),
.me-error :deep(.me-inp) {
  border-bottom-color: var(--fault) !important;
}

.me-fg {
  margin-bottom: 0;
}

.me-pw {
  position: relative;
  max-width: 480px;
  margin: 0 auto;
}

.me-inp {
  display: block;
  width: 100%;
  margin: 0;
  background: transparent;
  border: none;
  border-bottom: 2px solid var(--parchment-300);
  color: var(--ink-900);
  font-family: var(--font-mono);
  font-size: 24px;
  padding: 12px 40px 12px 0;
  outline: none;
  text-align: center;
  transition: border-color 0.3s;
  caret-color: var(--vermillion);
}

.me-inp::placeholder {
  color: var(--ink-ghost);
  font-size: 18px;
}

.me-inp:focus {
  border-bottom-color: var(--vermillion);
}

.me-eye {
  position: absolute;
  right: 4px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--ink-ghost);
  cursor: pointer;
  font-size: 20px;
  padding: 4px;
  transition: color 0.2s;
}

.me-eye:hover {
  color: var(--ink-dim);
}

/* URL field - always visible */
.me-url-row {
  animation: me-fade-in 0.3s ease;
}

@keyframes me-fade-in {
  from { opacity: 0; transform: translateY(-8px) }
  to { opacity: 1; transform: translateY(0) }
}

.me-url {
  display: block;
  width: 100%;
  max-width: 480px;
  margin: 0 auto;
  background: transparent;
  border: none;
  border-bottom: 2px solid var(--parchment-300);
  color: var(--ink-900);
  font-family: var(--font-mono);
  font-size: 24px;
  padding: 12px 0;
  outline: none;
  text-align: center;
  transition: border-color 0.3s;
  caret-color: var(--vermillion);
}

.me-url::placeholder {
  color: var(--ink-ghost);
  font-size: 18px;
}

.me-url:focus {
  border-bottom-color: var(--vermillion);
}
</style>