<script setup>
import { computed } from 'vue'
import { getCurrentWindow } from '@tauri-apps/api/window'
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
  isOnCurrentSession: {
    type: Boolean,
    default: true,
  },
})

const emit = defineEmits(['toggle-menu', 'open-input', 'switch-session'])

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
  if (!props.isOnCurrentSession && props.agentStatus !== 'IDLE') return true
  return ['THINKING', 'WORKING', 'RECOVERING'].includes(props.agentStatus)
})

const statusType = computed(() => {
  if (!props.isOnCurrentSession && props.agentStatus !== 'IDLE') return 'working'
  switch (props.agentStatus) {
    case 'THINKING': return 'thinking'
    case 'WORKING': return 'working'
    case 'RECOVERING': return 'recovering'
    default: return null
  }
})

const activeIcon = computed(() => {
  if (!props.isOnCurrentSession && props.agentStatus !== 'IDLE') return 'loader'
  switch (props.agentStatus) {
    case 'THINKING': return 'logo'
    case 'WORKING': return 'settings'
    case 'RECOVERING': return 'loader'
    default: return null
  }
})

function onBodyMouseDown(e) {
  getCurrentWindow().startDragging()
}
</script>

<template>
  <div class="glass-card">
    <!-- Main body: draggable -->
    <div
      class="glass-card__body"
      @mousedown="onBodyMouseDown"
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
        <template v-if="isOnCurrentSession">
          <span class="glass-card__status" :class="{
            'glass-card__status--idle': agentStatus === 'IDLE',
            'glass-card__status--active': isActive,
            [`glass-card__status--${statusType}`]: statusType,
          }">
            {{ statusLabel }}
          </span>
        </template>
        <template v-else>
          <button class="glass-card__other-task" @mousedown.stop @click.stop="$emit('switch-session')">
            ON OTHER TASK
            <MIcon name="arrow-right" class="glass-card__other-task-arrow" />
          </button>
        </template>
        <button class="glass-card__icon-btn" @mousedown.stop @click.stop="$emit('open-input')" title="Send message">
          <MIcon name="send" />
        </button>
        <button class="glass-card__icon-btn glass-card__icon-btn--menu" @mousedown.stop @click.stop="$emit('toggle-menu')" title="Actions">
          <MIcon name="more-vertical" />
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
  padding: 3px 10px;
  background: rgba(0, 0, 0, 0.04);
  border-radius: 12px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary, #52525b);
  white-space: nowrap;
  transition: all 0.3s ease;
  position: relative;
  overflow: hidden;
}

.glass-card__status--idle {
  color: var(--text-quaternary, #d4d4d8);
  font-weight: 400;
}

.glass-card__status--active {
  background: rgba(184, 169, 201, 0.12);
  color: var(--morandi-mauve, #8B7BA5);
}

/* Thinking state - violet glow with shimmer */
.glass-card__status--thinking {
  background: linear-gradient(90deg, 
    rgba(124, 58, 237, 0.08) 0%,
    rgba(124, 58, 237, 0.18) 50%,
    rgba(124, 58, 237, 0.08) 100%
  );
  background-size: 200% 100%;
  color: #7C3AED;
  font-weight: 600;
  border: 1px solid rgba(124, 58, 237, 0.2);
  animation: thinking-shimmer 2s ease-in-out infinite;
  text-shadow: 0 0 8px rgba(124, 58, 237, 0.3);
}

.glass-card__status--thinking::before {
  content: '';
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(90deg, 
    transparent 0%,
    rgba(255, 255, 255, 0.4) 50%,
    transparent 100%
  );
  animation: thinking-light 2s ease-in-out infinite;
}

@keyframes thinking-shimmer {
  0%, 100% { 
    background-position: 0% 50%;
    box-shadow: 0 0 8px rgba(124, 58, 237, 0.15);
  }
  50% { 
    background-position: 100% 50%;
    box-shadow: 0 0 16px rgba(124, 58, 237, 0.3);
  }
}

@keyframes thinking-light {
  0% { left: -100%; }
  50% { left: 100%; }
  100% { left: 100%; }
}

/* Working state - teal glow with pulse */
.glass-card__status--working {
  background: linear-gradient(90deg,
    rgba(13, 148, 136, 0.08) 0%,
    rgba(13, 148, 136, 0.2) 50%,
    rgba(13, 148, 136, 0.08) 100%
  );
  background-size: 200% 100%;
  color: #0D9488;
  font-weight: 600;
  border: 1px solid rgba(13, 148, 136, 0.25);
  animation: working-pulse 1.5s ease-in-out infinite;
  text-shadow: 0 0 8px rgba(13, 148, 136, 0.3);
}

.glass-card__status--working::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  width: 120%;
  height: 120%;
  transform: translate(-50%, -50%);
  background: radial-gradient(circle, rgba(13, 148, 136, 0.15) 0%, transparent 70%);
  animation: working-glow 1.5s ease-in-out infinite;
}

@keyframes working-pulse {
  0%, 100% {
    background-position: 0% 50%;
    transform: scale(1);
  }
  50% {
    background-position: 100% 50%;
    transform: scale(1.02);
  }
}

@keyframes working-glow {
  0%, 100% { opacity: 0; transform: translate(-50%, -50%) scale(0.8); }
  50% { opacity: 1; transform: translate(-50%, -50%) scale(1); }
}

/* Recovering state - amber glow with flash */
.glass-card__status--recovering {
  background: linear-gradient(90deg,
    rgba(217, 119, 6, 0.08) 0%,
    rgba(217, 119, 6, 0.2) 50%,
    rgba(217, 119, 6, 0.08) 100%
  );
  background-size: 200% 100%;
  color: #D97706;
  font-weight: 600;
  border: 1px solid rgba(217, 119, 6, 0.25);
  animation: recovering-flash 1.2s ease-in-out infinite;
  text-shadow: 0 0 8px rgba(217, 119, 6, 0.3);
}

.glass-card__status--recovering::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(90deg,
    transparent 0%,
    rgba(217, 119, 6, 0.1) 25%,
    rgba(255, 255, 255, 0.3) 50%,
    rgba(217, 119, 6, 0.1) 75%,
    transparent 100%
  );
  background-size: 200% 100%;
  animation: recovering-light 1.2s linear infinite;
}

@keyframes recovering-flash {
  0%, 100% {
    background-position: 0% 50%;
    box-shadow: 0 0 8px rgba(217, 119, 6, 0.2);
  }
  25% {
    box-shadow: 0 0 16px rgba(217, 119, 6, 0.4);
  }
  50% {
    background-position: 100% 50%;
    box-shadow: 0 0 8px rgba(217, 119, 6, 0.2);
  }
  75% {
    box-shadow: 0 0 20px rgba(217, 119, 6, 0.5);
  }
}

@keyframes recovering-light {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
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
}

.glass-card__icon-btn--menu {
  margin-left: auto;
}

.glass-card__icon-btn:hover {
  background: rgba(0, 0, 0, 0.06);
  color: var(--text-primary, #18181b);
}

/* ---- ON OTHER TASK button ---- */
.glass-card__other-task {
  display: flex;
  align-items: center;
  gap: 3px;
  padding: 2px 8px;
  background: rgba(180, 140, 80, 0.08);
  border: 1px solid rgba(180, 140, 80, 0.15);
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
  font-family: inherit;
  color: rgba(160, 120, 60, 0.85);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
  pointer-events: auto;
}

.glass-card__other-task:hover {
  background: rgba(180, 140, 80, 0.14);
  border-color: rgba(180, 140, 80, 0.3);
}

.glass-card__other-task-arrow {
  font-size: 10px;
}

@keyframes status-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}
</style>
