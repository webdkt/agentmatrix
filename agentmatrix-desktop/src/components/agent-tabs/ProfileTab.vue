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

          <button
            class="profile-action"
            :disabled="!canStop"
            :class="{ 'profile-action--loading': isStopping }"
            @click="handleStop"
          >
            <MIcon name="square" />
            <span>{{ $t('matrix.profile.stop') }}</span>
          </button>

          <button
            class="profile-action"
            :disabled="!canPauseResume"
            :class="{ 'profile-action--loading': isPausingResuming }"
            @click="handlePauseResume"
          >
            <MIcon :name="isPaused ? 'play' : 'pause'" />
            <span>{{ isPaused ? $t('matrix.profile.resume') : $t('matrix.profile.pause') }}</span>
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
          <!-- 新增：显示当前状态 -->
          <div class="profile-field">
            <span class="profile-field__label">{{ $t('matrix.profile.status') }}</span>
            <span class="profile-field__value">{{ agentStatus }}</span>
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
import { ref, watch, computed } from 'vue'
import { useMatrixStore } from '@/stores/matrix'
import { useAgentStore } from '@/stores/agent'
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
const agentStore = useAgentStore()
const { profile, isLoadingProfile } = storeToRefs(matrixStore)

const isLoading = ref(false)
const showPromptModal = ref(false)
const isStopping = ref(false)
const isPausingResuming = ref(false)

// 获取Agent状态
const agentStatus = computed(() => {
  return agentStore.getAgentStatus(props.agentName) || 'IDLE'
})

// Agent是否暂停
const isPaused = computed(() => {
  return agentStatus.value === 'PAUSED'
})

// 是否可以Stop（当Agent正在工作时）
const canStop = computed(() => {
  const status = agentStatus.value
  return ['WORKING', 'THINKING'].includes(status) && !isStopping.value
})

// 是否可以Pause/Resume（只要不是IDLE或ERROR就可以暂停）
const canPauseResume = computed(() => {
  const status = agentStatus.value
  return !['IDLE', 'ERROR'].includes(status) && !isPausingResuming.value
})

// 处理Stop按钮点击
async function handleStop() {
  if (!props.agentName || isStopping.value) return

  isStopping.value = true
  try {
    await matrixStore.stopAgent(props.agentName)
    // 状态会通过WebSocket自动更新
  } catch (error) {
    console.error('Failed to stop agent:', error)
    alert(`停止Agent失败: ${error.message || error}`)
  } finally {
    isStopping.value = false
  }
}

// 处理Pause/Resume按钮点击
async function handlePauseResume() {
  if (!props.agentName || isPausingResuming.value) return

  isPausingResuming.value = true
  try {
    if (isPaused.value) {
      await matrixStore.resumeAgent(props.agentName)
    } else {
      await matrixStore.pauseAgent(props.agentName)
    }
    // 状态会通过WebSocket自动更新
  } catch (error) {
    console.error('Failed to pause/resume agent:', error)
    alert(`${isPaused.value ? '恢复' : '暂停'}Agent失败: ${error.message || error}`)
  } finally {
    isPausingResuming.value = false
  }
}

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
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: var(--spacing-6);
}

.profile-tab__loading {
  padding: var(--spacing-8);
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
  margin-bottom: var(--spacing-8);
}

.profile-section__title {
  font-family: var(--font-sans);
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  font-weight: var(--font-medium);
  margin-bottom: var(--spacing-4);
  padding-bottom: var(--spacing-1);
  border-bottom: 1px solid var(--border);
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
  color: var(--text-secondary);
  background: white;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease;
}

.profile-action:hover:not(:disabled) {
  background: var(--surface-secondary);
  border-color: var(--border);
}

.profile-action:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.profile-action--primary {
  color: var(--accent);
  background: var(--accent-muted);
  border-color: var(--accent);
}

.profile-action--primary:hover:not(:disabled) {
  background: var(--accent-medium);
  border-color: var(--accent-hover);
}

.profile-action--loading {
  opacity: 0.6;
  cursor: wait;
}

.profile-action :deep(svg) {
  width: 14px;
  height: 14px;
}

.profile-fields {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.profile-field {
  display: flex;
  gap: var(--spacing-4);
}

.profile-field__label {
  font-family: var(--font-sans);
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  min-width: 120px;
}

.profile-field__value {
  font-family: var(--font-sans);
  font-size: 14px;
  color: var(--text-secondary);
}

.profile-field__value--mono {
  font-family: var(--font-mono);
  font-size: 13px;
}

.profile-skills {
  display: flex;
  flex-wrap: wrap;
  gap: var(--spacing-2);
}

.profile-skill {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--text-secondary);
  background: var(--surface-hover);
  padding: 2px 8px;
  border-radius: 2px;
  border: 1px solid var(--border);
}

.profile-persona {
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: 2px;
  padding: var(--spacing-4);
  max-height: 300px;
  overflow-y: auto;
}

.profile-persona__text {
  font-family: var(--font-sans);
  font-size: 14px;
  color: var(--text-secondary);
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
  color: var(--text-tertiary);
  font-family: var(--font-sans);
  font-style: italic;
}
</style>
