<template>
  <div class="profile-tab">
    <div v-if="isLoading" class="profile-tab__loading">
      <div class="thinking-bar"></div>
    </div>

    <div v-else-if="profile" class="profile-tab__content">
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
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useMatrixStore } from '../../../stores/matrix'
import { storeToRefs } from 'pinia'

const props = defineProps({
  agentName: {
    type: String,
    required: true
  }
})

const matrixStore = useMatrixStore()
const { profile, isLoadingProfile } = storeToRefs(matrixStore)

const isLoading = ref(false)

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
