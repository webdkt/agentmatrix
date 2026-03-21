<script setup>
import { computed } from 'vue'
import { useConfigStore } from '@/stores/config'

const configStore = useConfigStore()

const presetOptions = computed(() => {
  return Object.entries(configStore.llmPresets).map(([key, val]) => ({
    value: key,
    label: val.label,
  }))
})

const llmModels = computed(() => {
  const provider = configStore.wizardData.default_llm.provider
  return configStore.llmPresets[provider]?.models || []
})

const slmModels = computed(() => {
  const provider = configStore.wizardData.default_slm.provider
  return configStore.llmPresets[provider]?.models || []
})

const isLLMCustom = computed(() => configStore.wizardData.default_llm.provider === 'custom')
const isSLMCustom = computed(() => configStore.wizardData.default_slm.provider === 'custom')

function onLLMProviderChange(event) {
  configStore.selectLLMPreset('default_llm', event.target.value)
}

function onSLMProviderChange(event) {
  configStore.selectLLMPreset('default_slm', event.target.value)
}
</script>

<template>
  <div class="step">
    <h2 class="step__title">Configure your LLM providers</h2>
    <p class="step__desc">
      AgentMatrix uses two models: a <strong>Large Model</strong> for complex reasoning
      and a <strong>Small Model</strong> for quick tasks.
    </p>

    <!-- Default LLM -->
    <div class="step__section">
      <div class="step__section-header">
        <i class="ti ti-brain"></i>
        <div>
          <h3>Large Model (default_llm)</h3>
          <p>Used for main agent reasoning and complex tasks</p>
        </div>
      </div>

      <div class="step__row">
        <div class="step__field">
          <label class="step__label">Provider</label>
          <select
            class="input"
            :value="configStore.wizardData.default_llm.provider"
            @change="onLLMProviderChange"
          >
            <option v-for="opt in presetOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
      </div>

      <div v-if="isLLMCustom" class="step__field">
        <label class="step__label">API URL</label>
        <input
          v-model="configStore.wizardData.default_llm.url"
          class="input"
          type="text"
          placeholder="https://api.example.com/v1/chat/completions"
        />
      </div>

      <div class="step__field">
        <label class="step__label">API Key</label>
        <input
          v-model="configStore.wizardData.default_llm.api_key"
          class="input"
          type="password"
          placeholder="sk-..."
        />
      </div>

      <div class="step__field">
        <label class="step__label">Model</label>
        <select
          v-if="!isLLMCustom && llmModels.length > 0"
          v-model="configStore.wizardData.default_llm.model_name"
          class="input"
        >
          <option v-for="m in llmModels" :key="m" :value="m">{{ m }}</option>
        </select>
        <input
          v-else
          v-model="configStore.wizardData.default_llm.model_name"
          class="input"
          type="text"
          placeholder="model-name"
        />
      </div>
    </div>

    <!-- Default SLM -->
    <div class="step__section">
      <div class="step__section-header">
        <i class="ti ti-bolt"></i>
        <div>
          <h3>Small Model (default_slm)</h3>
          <p>Used for fast tasks, parameter parsing, and lightweight operations</p>
        </div>
      </div>

      <div class="step__row">
        <div class="step__field">
          <label class="step__label">Provider</label>
          <select
            class="input"
            :value="configStore.wizardData.default_slm.provider"
            @change="onSLMProviderChange"
          >
            <option v-for="opt in presetOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>
      </div>

      <div v-if="isSLMCustom" class="step__field">
        <label class="step__label">API URL</label>
        <input
          v-model="configStore.wizardData.default_slm.url"
          class="input"
          type="text"
          placeholder="https://api.example.com/v1/chat/completions"
        />
      </div>

      <div class="step__field">
        <label class="step__label">API Key</label>
        <input
          v-model="configStore.wizardData.default_slm.api_key"
          class="input"
          type="password"
          placeholder="sk-..."
        />
      </div>

      <div class="step__field">
        <label class="step__label">Model</label>
        <select
          v-if="!isSLMCustom && slmModels.length > 0"
          v-model="configStore.wizardData.default_slm.model_name"
          class="input"
        >
          <option v-for="m in slmModels" :key="m" :value="m">{{ m }}</option>
        </select>
        <input
          v-else
          v-model="configStore.wizardData.default_slm.model_name"
          class="input"
          type="text"
          placeholder="model-name"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.step {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.step__title {
  font-family: var(--font-display);
  font-size: var(--font-xl);
  font-weight: var(--font-semibold);
  color: var(--neutral-800);
  margin: 0;
}

.step__desc {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  margin: 0;
  line-height: 1.6;
}

.step__section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: var(--neutral-50);
  border-radius: var(--radius-lg);
  border: 1px solid var(--neutral-200);
}

.step__section-header {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
}

.step__section-header i {
  font-size: 20px;
  color: var(--primary-500);
  margin-top: 2px;
}

.step__section-header h3 {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--neutral-800);
  margin: 0;
}

.step__section-header p {
  font-size: var(--font-xs);
  color: var(--neutral-500);
  margin: 0;
}

.step__row {
  display: flex;
  gap: var(--spacing-sm);
}

.step__field {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  flex: 1;
}

.step__label {
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  color: var(--neutral-600);
}
</style>
