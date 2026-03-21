<script setup>
import { useConfigStore } from '@/stores/config'

const configStore = useConfigStore()
</script>

<template>
  <div class="step">
    <h2 class="step__title">What should we call you?</h2>
    <p class="step__desc">
      This name will be used as your identity in the AgentMatrix system.
      AI agents will address you by this name.
    </p>

    <div class="step__field">
      <label class="step__label" for="user-name">Your Name</label>
      <input
        id="user-name"
        v-model="configStore.wizardData.user_name"
        class="input input-lg"
        type="text"
        placeholder="e.g. Alice, Bob, DKT..."
        autofocus
        @keydown.enter="configStore.isCurrentStepValid && configStore.nextStep()"
      />
      <span class="step__hint">
        <i class="ti ti-info-circle"></i>
        This will appear as your agent name in all conversations
      </span>
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
  font-family: var(--font-serif);
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

.input-lg {
  padding: var(--spacing-md) var(--spacing-lg);
  font-size: var(--font-lg);
  border-radius: var(--radius-sm);
}

.step__hint {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  font-size: var(--font-xs);
  color: var(--neutral-400);
}
</style>
