<script setup>
import { onMounted } from 'vue'
import { useConfigStore } from '@/stores/config'
import StepUserName from './steps/StepUserName.vue'
import StepDirectory from './steps/StepDirectory.vue'
import StepLLM from './steps/StepLLM.vue'
import StepComplete from './steps/StepComplete.vue'

const emit = defineEmits(['complete'])
const configStore = useConfigStore()

onMounted(async () => {
  await configStore.loadPresets()
})

const steps = [
  { num: 1, label: 'Name', icon: 'ti ti-user' },
  { num: 2, label: 'Directory', icon: 'ti ti-folder' },
  { num: 3, label: 'LLM', icon: 'ti ti-brain' },
  { num: 4, label: 'Done', icon: 'ti ti-check' },
]

async function handleSubmit() {
  try {
    await configStore.submitWizard()
    emit('complete')
  } catch (error) {
    // Error is handled in the store
  }
}
</script>

<template>
  <div class="wizard">
    <div class="wizard__container">
      <!-- Logo & Title -->
      <div class="wizard__header">
        <div class="wizard__logo">
          <i class="ti ti-atom-2"></i>
        </div>
        <h1 class="wizard__title">AgentMatrix Setup</h1>
        <p class="wizard__subtitle">Configure your AI agent workspace</p>
      </div>

      <!-- Step Indicator -->
      <div class="wizard__stepper">
        <div
          v-for="step in steps"
          :key="step.num"
          :class="[
            'wizard__step',
            {
              'wizard__step--active': configStore.currentStep === step.num,
              'wizard__step--completed': configStore.currentStep > step.num,
            },
          ]"
        >
          <div class="wizard__step-dot">
            <i v-if="configStore.currentStep > step.num" class="ti ti-check"></i>
            <span v-else>{{ step.num }}</span>
          </div>
          <span class="wizard__step-label">{{ step.label }}</span>
        </div>
        <div class="wizard__step-line">
          <div
            class="wizard__step-line-fill"
            :style="{ width: `${((configStore.currentStep - 1) / (steps.length - 1)) * 100}%` }"
          ></div>
        </div>
      </div>

      <!-- Step Content -->
      <div class="wizard__content">
        <StepUserName v-if="configStore.currentStep === 1" />
        <StepDirectory v-else-if="configStore.currentStep === 2" />
        <StepLLM v-else-if="configStore.currentStep === 3" />
        <StepComplete v-else-if="configStore.currentStep === 4" />
      </div>

      <!-- Error -->
      <div v-if="configStore.submitError" class="wizard__error">
        <i class="ti ti-alert-circle"></i>
        {{ configStore.submitError }}
      </div>

      <!-- Navigation -->
      <div class="wizard__nav">
        <button
          v-if="configStore.canGoBack"
          class="btn btn-secondary btn-lg"
          @click="configStore.prevStep()"
        >
          <i class="ti ti-arrow-left"></i>
          Back
        </button>
        <div v-else></div>

        <button
          v-if="!configStore.isLastStep"
          class="btn btn-primary btn-lg"
          :disabled="!configStore.isCurrentStepValid"
          @click="configStore.nextStep()"
        >
          Next
          <i class="ti ti-arrow-right"></i>
        </button>
        <button
          v-else
          class="btn btn-primary btn-lg"
          :disabled="configStore.isSubmitting || !configStore.isCurrentStepValid"
          @click="handleSubmit"
        >
          <i v-if="configStore.isSubmitting" class="ti ti-loader wizard__spinner"></i>
          <i v-else class="ti ti-rocket"></i>
          {{ configStore.isSubmitting ? 'Setting up...' : 'Get Started' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.wizard {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, var(--neutral-50) 0%, var(--primary-50) 100%);
}

.wizard__container {
  width: 100%;
  max-width: 560px;
  background: white;
  border-radius: var(--radius-xl);
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.08), 0 1px 3px rgba(0, 0, 0, 0.05);
  padding: var(--spacing-2xl);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xl);
}

/* Header */
.wizard__header {
  text-align: center;
}

.wizard__logo {
  width: 64px;
  height: 64px;
  background: linear-gradient(135deg, var(--primary-500), var(--primary-600));
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 32px;
  color: white;
  margin: 0 auto var(--spacing-md);
  box-shadow: 0 8px 24px rgba(99, 102, 241, 0.3);
}

.wizard__title {
  font-family: var(--font-display);
  font-size: var(--font-2xl);
  font-weight: var(--font-bold);
  color: var(--neutral-900);
  margin: 0;
}

.wizard__subtitle {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  margin: var(--spacing-xs) 0 0;
}

/* Stepper */
.wizard__stepper {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-lg);
  position: relative;
  padding: 0 var(--spacing-md);
}

.wizard__step {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
  z-index: 1;
}

.wizard__step-dot {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  background: var(--neutral-100);
  color: var(--neutral-400);
  border: 2px solid var(--neutral-200);
  transition: all 0.3s ease;
}

.wizard__step--active .wizard__step-dot {
  background: var(--primary-500);
  color: white;
  border-color: var(--primary-500);
  box-shadow: 0 0 0 4px rgba(99, 102, 241, 0.15);
}

.wizard__step--completed .wizard__step-dot {
  background: var(--success-500);
  color: white;
  border-color: var(--success-500);
}

.wizard__step-label {
  font-size: var(--font-xs);
  color: var(--neutral-400);
  font-weight: var(--font-medium);
}

.wizard__step--active .wizard__step-label {
  color: var(--primary-600);
}

.wizard__step--completed .wizard__step-label {
  color: var(--success-700);
}

.wizard__step-line {
  position: absolute;
  top: 18px;
  left: 60px;
  right: 60px;
  height: 2px;
  background: var(--neutral-200);
  z-index: 0;
}

.wizard__step-line-fill {
  height: 100%;
  background: var(--success-500);
  transition: width 0.4s ease;
}

/* Content */
.wizard__content {
  min-height: 240px;
}

/* Error */
.wizard__error {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--error-50);
  border: 1px solid var(--error-200, #fecaca);
  border-radius: var(--radius-md);
  color: var(--error-700);
  font-size: var(--font-sm);
}

/* Navigation */
.wizard__nav {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.wizard__spinner {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
