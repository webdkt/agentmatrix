<script setup>
import { computed } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: {
    type: String,
    default: null,
  },
  agentStatus: {
    type: String,
    default: 'IDLE',
  },
})

const emit = defineEmits(['toggle-menu', 'open-input'])

const agentInitial = computed(() => {
  return props.agentName ? props.agentName.charAt(0).toUpperCase() : '?'
})

const statusLabel = computed(() => {
  switch (props.agentStatus) {
    case 'THINKING': return 'thinking'
    case 'WORKING': return 'working'
    case 'RECOVERING': return 'recovering'
    case 'WAITING_FOR_USER': return 'waiting'
    case 'PAUSED': return 'paused'
    case 'ERROR': return 'error'
    default: return 'idle'
  }
})

const isActive = computed(() => {
  return ['THINKING', 'WORKING', 'RECOVERING'].includes(props.agentStatus)
})

const activeIcon = computed(() => {
  switch (props.agentStatus) {
    case 'THINKING': return 'brain'
    case 'WORKING': return 'settings'
    case 'RECOVERING': return 'loader'
    default: return null
  }
})
</script>

<template>
  <div class="glass-card">
    <!-- Main body: draggable -->
    <div
      class="glass-card__body"
      data-tauri-drag-region
    >
      <div
        class="glass-card__avatar"
        :class="{ 'glass-card__avatar--active': isActive }"
      >
        <span v-if="isActive && activeIcon" class="glass-card__avatar-icon">
          <MIcon :name="activeIcon" />
        </span>
        <span v-else class="glass-card__avatar-letter">{{ agentInitial }}</span>
      </div>
      <div class="glass-card__info">
        <span class="glass-card__name">{{ agentName || 'Agent' }}</span>
        <span class="glass-card__status" :class="{ 'glass-card__status--idle': agentStatus === 'IDLE' }">
          {{ statusLabel }}
        </span>
        <button class="glass-card__icon-btn" @click.stop="$emit('open-input')" title="Send message">
          <MIcon name="send" />
        </button>
        <button class="glass-card__icon-btn glass-card__icon-btn--menu" @click.stop="$emit('toggle-menu')" title="Actions">
          <MIcon name="dots-vertical" />
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.glass-card {
  position: relative;
  padding: 14px 16px 8px;
  user-select: none;
  flex-shrink: 0;
  border-bottom: 1px solid rgba(0, 0, 0, 0.04);
}

.glass-card__body {
  display: flex;
  align-items: center;
  gap: 12px;
  min-width: 0;
}

.glass-card__avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--morandi-mauve, #B8A9C9);
  color: rgba(255, 255, 255, 0.9);
  font-size: 14px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  position: relative;
  transition: box-shadow 0.4s ease;
  pointer-events: none;
}

.glass-card__avatar::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.12);
  border: 1px solid rgba(255, 255, 255, 0.2);
  z-index: 0;
}

/* Active state: avatar pulses with a glow ring */
.glass-card__avatar--active {
  animation: avatar-breathe 2s ease-in-out infinite;
  box-shadow: 0 0 0 0 rgba(184, 169, 201, 0.4);
}

.glass-card__avatar-letter {
  position: relative;
  z-index: 1;
}

.glass-card__avatar-icon {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  animation: icon-spin 1.5s linear infinite;
}

@keyframes avatar-breathe {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(184, 169, 201, 0.4);
  }
  50% {
    box-shadow: 0 0 0 6px rgba(184, 169, 201, 0);
  }
}

@keyframes icon-spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.glass-card__info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1;
  pointer-events: none;
}

.glass-card__name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary, #18181b);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.glass-card__status {
  padding: 2px 8px;
  background: rgba(255, 255, 255, 0.5);
  border-radius: 12px;
  font-size: 14px;
  color: var(--text-tertiary, #a1a1aa);
  white-space: nowrap;
  transition: opacity 0.2s ease;
}

.glass-card__status--idle {
  opacity: 0.5;
}

.glass-card__icon-btn {
  width: 26px;
  height: 26px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-tertiary, #a1a1aa);
  font-size: 15px;
  transition: all 0.12s ease;
  flex-shrink: 0;
  pointer-events: auto;
  -webkit-app-region: no-drag;
}

.glass-card__icon-btn--menu {
  margin-left: auto;
}

.glass-card__icon-btn:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-primary, #18181b);
}
</style>
