<script setup>
import { useConfigStore } from '@/stores/config'

const configStore = useConfigStore()
</script>

<template>
  <div class="step">
    <h2 class="step__title">Where should we store your data?</h2>
    <p class="step__desc">
      Choose a directory for your MatrixWorld data. This is where all agent
      configurations, sessions, and files will be stored.
    </p>

    <div class="step__field">
      <label class="step__label" for="matrix-path">MatrixWorld Directory</label>
      <div class="step__path-row">
        <input
          id="matrix-path"
          v-model="configStore.wizardData.matrix_world_path"
          class="input"
          type="text"
          placeholder="~/MatrixWorld"
        />
        <button class="btn btn-secondary" @click="configStore.selectDirectory()">
          <i class="ti ti-folder-open"></i>
          Browse
        </button>
      </div>
      <span class="step__hint">
        <i class="ti ti-info-circle"></i>
        You can use the default path or choose your own location
      </span>
    </div>

    <div class="step__info-box">
      <i class="ti ti-database"></i>
      <div>
        <strong>What will be created:</strong>
        <ul>
          <li>Agent configurations &amp; LLM settings</li>
          <li>Session history &amp; email database</li>
          <li>Workspace files &amp; skills</li>
        </ul>
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

.step__field {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.step__label {
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-700);
}

.step__path-row {
  display: flex;
  gap: var(--spacing-sm);
}

.step__path-row .input {
  flex: 1;
}

.step__hint {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: var(--font-xs);
  color: var(--neutral-400);
}

.step__info-box {
  display: flex;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--info-50);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  color: var(--info-700);
}

.step__info-box i {
  font-size: 20px;
  flex-shrink: 0;
  margin-top: 2px;
}

.step__info-box ul {
  margin: var(--spacing-xs) 0 0;
  padding-left: var(--spacing-lg);
}

.step__info-box li {
  margin-bottom: 2px;
}
</style>
