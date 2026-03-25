<template>
  <div class="profile-tab">
    <div v-if="isLoading" class="profile-tab__loading">
      <div class="thinking-bar"></div>
    </div>

    <div v-else-if="profile" class="profile-tab__content">
      <!-- Action Buttons -->
      <section class="profile-section">
        <h3 class="profile-section__title">{{ $t('matrix.profile.actions') }}</h3>
        <div class="profile-actions">
          <button
            class="profile-action profile-action--primary"
            @click="showPromptModal = true"
          >
            <MIcon name="terminal" />
            <span>{{ $t('matrix.profile.viewPrompt') }}</span>
          </button>

          <button class="profile-action" disabled>
            <MIcon name="square" />
            <span>{{ $t('matrix.profile.stop') }}</span>
          </button>

          <button class="profile-action" disabled>
            <MIcon name="refresh-cw" />
            <span>{{ $t('matrix.profile.reload') }}</span>
          </button>

          <button class="profile-action" disabled>
            <MIcon name="copy" />
            <span>{{ $t('matrix.profile.clone') }}</span>
          </button>

          <button class="profile-action" disabled>
            <MIcon name="mail" />
            <span>{{ $t('matrix.profile.mailTo') }}</span>
          </button>
        </div>
      </section>

      <!-- 基本信息 -->
      <section class="profile-section">
        <h3 class="profile-section__title">{{ $t('matrix.profile.basicInfo') }}</h3>
        <div class="profile-fields">
          <div class="profile-field">
            <span class="profile-field__label">{{ $t('matrix.profile.name') }}</span>
            <span class="profile-field__value">{{ profile.name }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field__label">{{ $t('matrix.profile.description') }}</span>
            <span class="profile-field__value">{{ profile.description }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field__label">{{ $t('matrix.profile.className') }}</span>
            <span class="profile-field__value profile-field__value--mono">{{ profile.class_name }}</span>
          </div>
          <div class="profile-field">
            <span class="profile-field__label">{{ $t('matrix.profile.backendModel') }}</span>
            <span class="profile-field__value">{{ profile.backend_model }}</span>
          </div>
        </div>
      </section>

      <!-- Skills -->
      <section class="profile-section">
        <h3 class="profile-section__title">{{ $t('matrix.profile.skills') }}</h3>
        <div class="profile-skills">
          <span
            v-for="skill in profile.skills"
            :key="skill"
            class="profile-skill"
          >
            {{ skill }}
          </span>
        </div>
      </section>

      <!-- Persona -->
      <section class="profile-section">
        <h3 class="profile-section__title">{{ $t('matrix.profile.persona') }}</h3>
        <div class="profile-persona">
          <pre class="profile-persona__text">{{ profile.persona || '(empty)' }}</pre>
        </div>
      </section>
    </div>

    <div v-else class="profile-tab__empty">
      {{ $t('matrix.profile.noData') }}
    </div>

    <!-- Prompt Preview Modal -->
    <PromptPreviewModal
      :show="showPromptModal"
      :agentName="agentName"
      @close="showPromptModal = false"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useMatrixStore } from '../../../stores/matrix'
import { storeToRefs } from 'pinia'
import MIcon from '@/components/icons/MIcon.vue'
import PromptPreviewModal from '@/components/dialog/PromptPreviewModal.vue'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  }
})

const matrixStore = useMatrixStore()
const { profile, isLoadingProfile } = storeToRefs(matrixStore)

const isLoading = ref(false)
const showPromptModal = ref(false)

watch(() => props.agentName, async (newName) => {
  if (newName) {
    isLoading.value = true
    await matrixStore.loadProfile(newName)
    isLoading.value = false
  }
}, { immediate: true })
</script>

<style scoped>
.profile-tab {
  height: 100%;
  overflow-y: auto;
  padding: var(--spacing-lg);
}

.profile-tab__loading {
  padding: var(--spacing-xl);
}

.thinking-bar {
  height: 2px;
  background: var(--accent);
  animation: thinking 1.5s ease-in-out infinite;
}

@keyframes thinking {
  0% { width: 0; margin-left: 0; }
  50% { width: 60%; margin-left: 20%; }
  100% { width: 0; margin-left: 100%; }
}

.profile-section {
  margin-bottom: var(--spacing-xl);
}

.profile-section__title {
  font-family: var(--font-sans);
  font-size: 11px;
  font-variant: small-caps;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--ink-500);
  margin-bottom: var(--spacing-md);
  padding-bottom: var(--spacing-xs);
  border-bottom: 1px solid var(--parchment-300);
}

/* Action Buttons */
.profile-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.profile-action {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-600);
  background: white;
  border: 1px solid var(--parchment-300);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.15s ease;
}

.profile-action:hover:not(:disabled) {
  background: var(--parchment-100);
  border-color: var(--parchment-400);
}

.profile-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.profile-action--primary {
  color: var(--accent-600, #5a3d2e);
  background: var(--accent-50, #f9f6f4);
  border-color: var(--accent-200, #d4c4b8);
}

.profile-action--primary:hover:not(:disabled) {
  background: var(--accent-100, #f0e9e4);
  border-color: var(--accent-300, #c4a894);
}

.profile-action :deep(svg) {
  width: 14px;
  height: 14px;
}

.profile-fields {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.profile-field {
  display: flex;
  gap: var(--spacing-md);
}

.profile-field__label {
  font-family: var(--font-sans);
  font-size: 12px;
  color: var(--ink-500);
  min-width: 120px;
  font-variant: small-caps;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.profile-field__value {
  font-family: var(--font-sans);
  font-size: 14px;
  color: var(--ink-700);
}

.profile-field__value--mono {
  font-family: var(--font-mono);
  font-size: 13px;
}

.profile-skills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-sm);
}

.profile-skill {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--ink-700);
  background: var(--parchment-200);
  padding: 2px 8px;
  border-radius: 2px;
  border: 1px solid var(--parchment-300);
}

.profile-persona {
  background: var(--parchment-100);
  border: 1px solid var(--parchment-300);
  border-radius: 2px;
  padding: var(--spacing-md);
  max-height: 300px;
  overflow-y: auto;
}

.profile-persona__text {
  font-family: var(--font-serif);
  font-size: 14px;
  color: var(--ink-700);
  line-height: 1.8;
  white-space: pre-wrap;
  word-break: break-word;
  margin: 0;
}

.profile-tab__empty {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--ink-400);
  font-family: var(--font-serif);
  font-style: italic;
}
</style>
