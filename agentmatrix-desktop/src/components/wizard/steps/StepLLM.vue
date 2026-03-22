<script setup>
import { computed } from 'vue'
import { useConfigStore } from '@/stores/config'

const props = defineProps({
  which: { type: String, required: true } // 'llm' or 'slm'
})

const configStore = useConfigStore()

const field = computed(() => props.which === 'llm' ? 'default_llm' : 'default_slm')
const data = computed(() => configStore.wizardData[field.value])

const presetOptions = computed(() =>
  Object.entries(configStore.llmPresets).map(([key, val]) => ({
    value: key,
    label: val.label,
  }))
)

const models = computed(() =>
  configStore.llmPresets[data.value.provider]?.models || []
)

const isCustom = computed(() => data.value.provider === 'custom')

function onProviderChange(e) {
  configStore.selectLLMPreset(field.value, e.target.value)
}

function togEye(btn) {
  const inp = btn.previousElementSibling
  if (inp.type === 'password') { inp.type = 'text'; btn.textContent = '\u25ce' }
  else { inp.type = 'password'; btn.textContent = '\u25c9' }
}
</script>

<template>
  <div class="me-llm">
    <!-- Custom: URL first -->
    <div v-if="isCustom" class="me-fg">
      <input
        v-model="data.url"
        class="me-sel"
        type="text"
        placeholder="api url"
        spellcheck="false"
      />
    </div>

    <!-- Provider (non-custom) -->
    <div v-else class="me-fg">
      <select class="me-sel" :value="data.provider" @change="onProviderChange">
        <option v-for="opt in presetOptions" :key="opt.value" :value="opt.value">
          {{ opt.label }}
        </option>
      </select>
    </div>

    <!-- Model -->
    <div class="me-fg">
      <select
        v-if="!isCustom && models.length > 0"
        class="me-sel"
        :value="data.model_name"
        @change="data.model_name = $event.target.value"
      >
        <option v-for="m in models" :key="m" :value="m">{{ m }}</option>
      </select>
      <input
        v-else
        v-model="data.model_name"
        class="me-sel"
        type="text"
        placeholder="model name"
        spellcheck="false"
      />
    </div>

    <!-- API Key -->
    <div class="me-fg">
      <div class="me-pw">
        <input
          v-model="data.api_key"
          class="me-inp"
          type="password"
          placeholder="api key"
          spellcheck="false"
        />
        <button class="me-eye" @click="togEye($event.target)">&#x25c9;</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.me-llm {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.me-fg {
  margin-bottom: 0;
}

.me-sel {
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
  appearance: none;
  cursor: pointer;
  transition: border-color 0.3s;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%239A9A9A' stroke-width='2'%3E%3Cpath d='M6 9l6 6 6-6'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0 center;
}

.me-sel:focus {
  border-bottom-color: var(--vermillion);
}

.me-sel option {
  background: var(--parchment-50);
  color: var(--ink-900);
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
</style>