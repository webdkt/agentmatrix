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

// 计算头像颜色类
const avatarColorClass = computed(() => {
  const colorIndex = props.index % 5
  const colors = [
    'from-blue-400 to-blue-600',
    'from-emerald-400 to-emerald-600',
    'from-violet-400 to-violet-600',
    'from-amber-400 to-orange-500',
    'from-rose-400 to-pink-600',
  ]
  return colors[colorIndex]
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
</script>

<template>
  <div
    @click="emit('click')"
    :class="['session-item', { 'session-item--active': isActive }]"
  >
    <!-- Avatar -->
    <div class="session-item__avatar-wrapper">
      <div
        :class="['session-item__avatar', avatarColorClass]"
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

    <!-- Content (Left-aligned) -->
    <div class="session-item__content">
      <!-- Header: Agent name + Date -->
      <div class="session-item__header">
        <span class="session-item__name">
          {{ displayParticipants }}
        </span>
        <span class="session-item__date">
          {{ formatDate(session.last_email_time) }}
        </span>
      </div>

      <!-- Subject -->
      <p class="session-item__subject">
        {{ session.subject || 'No Subject' }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.session-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md); /* 12px tight gap */
  padding: var(--spacing-sm) var(--spacing-md); /* 12px 16px */
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.session-item:hover {
  background: var(--neutral-50);
  border-color: var(--neutral-200);
}

.session-item--active {
  background: var(--primary-50);
  border-color: var(--primary-200);
}

/* Avatar */
.session-item__avatar-wrapper {
  position: relative;
  flex-shrink: 0;
}

.session-item__avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(to bottom right, var(--primary-400), var(--primary-600));
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: var(--font-semibold);
  font-size: var(--font-sm);
  box-shadow: var(--shadow-sm);
}

.session-item__initial {
  font-size: 14px;
}

/* Pending indicator */
.session-item__pending {
  position: absolute;
  top: -2px;
  right: -2px;
  width: 18px;
  height: 18px;
  background: var(--error-500);
  border-radius: 50%;
  border: 2px solid white;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: var(--shadow-xs);
}

.session-item__pending-count {
  color: white;
  font-size: 10px;
  font-weight: var(--font-bold);
  line-height: 1;
}

/* Content */
.session-item__content {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px; /* Tight internal spacing */
}

/* Header: Name + Date */
.session-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-sm);
}

.session-item__name {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.session-item__date {
  font-size: var(--font-xs);
  color: var(--neutral-400);
  flex-shrink: 0;
}

/* Subject */
.session-item__subject {
  font-size: var(--font-sm);
  font-weight: var(--font-normal);
  color: var(--neutral-600);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}
</style>
