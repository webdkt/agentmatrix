<script setup>
import { computed } from 'vue'
import { useSessionStore } from '@/stores/session'

const sessionStore = useSessionStore()

const props = defineProps({
  session: {
    type: Object,
    required: true
  },
  isActive: {
    type: Boolean,
    default: false
  },
  index: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['click'])

// 计算头像颜色 - Morandi 莫兰迪配色
const morandiColors = [
  '#C4A4A0', // rose
  '#9CAF88', // sage
  '#8E9AAF', // slate
  '#B8A9C9', // mauve
  '#B5A89A', // taupe
  '#C08B6E', // terracotta
  '#A8B09A', // olive
  '#7B8FA1', // blue
]

const avatarStyle = computed(() => {
  const name = props.session.name || props.session.participants?.[0] || 'New'
  const sessionId = props.session.session_id || ''
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  for (let i = 0; i < sessionId.length; i++) {
    hash = sessionId.charCodeAt(i) + ((hash << 5) - hash)
  }
  const colorIndex = Math.abs(hash) % morandiColors.length
  return { background: morandiColors[colorIndex] }
})

// 格式化日期
const formatDate = (dateString) => {
  if (!dateString) return ''

  const date = new Date(dateString)
  const now = new Date()
  const diffMs = now - date
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

  if (diffDays === 0) {
    // 今天，显示时间
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: false
    })
  } else if (diffDays === 1) {
    // 昨天
    return 'Yesterday'
  } else if (diffDays < 7) {
    // 本周，显示星期
    return date.toLocaleDateString('en-US', { weekday: 'short' })
  } else {
    // 更早，显示日期
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric'
    })
  }
}

// 参与者显示名称
const displayParticipants = computed(() => {
  if (!props.session.participants || props.session.participants.length === 0) {
    return 'New Chat'
  }
  return props.session.participants.join(', ')
})

// 主题首字母
const subjectInitial = computed(() => {
  const subject = props.session.subject || ''
  return subject.charAt(0).toUpperCase()
})

// 检查是否有待处理问题
const hasPending = computed(() => {
  const sessionId = props.session.session_id
  return sessionStore.hasPendingQuestion(sessionId)
})

// 检查是否有未读邮件
const isUnread = computed(() => {
  return sessionStore.isSessionUnread(props.session.session_id)
})
</script>

<template>
  <div
    @click="emit('click')"
    :class="['session-item', { 'session-item--active': isActive, 'session-item--unread': isUnread }]"
  >
    <!-- Avatar -->
    <div class="session-item__avatar-wrapper">
      <div
        class="session-item__avatar"
        :style="avatarStyle"
      >
        <span class="session-item__initial">{{ subjectInitial }}</span>
      </div>

      <!-- Pending indicator -->
      <div
        v-if="hasPending"
        class="session-item__pending"
      >
        <span class="session-item__pending-count">1</span>
      </div>
    </div>

    <!-- Info -->
    <div class="session-item__info">
      <div class="session-item__name">{{ displayParticipants }}</div>
      <div class="session-item__preview">{{ session.subject || 'No Subject' }}</div>
    </div>

    <!-- Meta (right-aligned) -->
    <div class="session-item__meta">
      <span class="session-item__time">{{ formatDate(session.last_email_time) }}</span>
      <div v-if="isUnread" class="session-item__unread">1</div>
    </div>
  </div>
</template>

<style scoped>
.session-item {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 14px 12px;
  background: transparent;
  border: 1px solid transparent;
  border-left: 2px solid transparent;
  border-radius: var(--radius-md);
  margin-bottom: 3px;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.session-item:hover {
  background: var(--surface-hover);
}

.session-item--active {
  background: var(--surface-secondary);
  border-left-color: var(--accent);
}

.session-item--active .session-item__name {
  font-weight: 600;
}

/* Avatar */
.session-item__avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}

.session-item__avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(255,255,255,0.9);
  font-weight: var(--font-semibold);
  font-size: 15px;
  position: relative;
  overflow: hidden;
  /* 背景色通过 :style 动态设置（Morandi 色） */
}

/* Frosted glass overlay */
.session-item__avatar::after {
  content: '';
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background: rgba(255,255,255,0.12);
  border: 1px solid rgba(255,255,255,0.2);
}

.session-item__initial {
  position: relative;
  z-index: 1;
  font-size: 16px;
  text-shadow: 0 1px 2px rgba(0,0,0,0.15);
}

/* Pending indicator */
.session-item__pending {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 18px;
  height: 18px;
  background: var(--error);
  border-radius: 50%;
  border: 2px solid white;
  display: flex;
  align-items: center;
  justify-content: center;
}

.session-item__pending-count {
  color: white;
  font-size: 10px;
  font-weight: var(--font-bold);
  line-height: 1;
}

/* Info */
.session-item__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}

.session-item__name {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-item__preview {
  font-size: 16px;
  color: #71717A;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}

/* Meta (right-aligned) */
.session-item__meta {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 5px;
  flex-shrink: 0;
}

.session-item__time {
  font-size: 12px;
  color: var(--text-quaternary);
}

.session-item__unread {
  min-width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: var(--accent);
  color: white;
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 6px;
}
</style>
