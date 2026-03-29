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

// 计算头像颜色 - 智能配色系统
// 同一agent的不同session使用同色系但有变化，避免单调
const avatarStyle = computed(() => {
  const name = props.session.name || props.session.participants?.[0] || 'New'
  const sessionId = props.session.session_id || ''

  // 第一步：基于agent名称生成基础色相（同一agent = 同一基础色系）
  let hash = 0
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash)
  }
  const baseHue = Math.abs(hash % 360)

  // 第二步：基于sessionId和名称的组合生成变化因子
  // 同一agent的不同session会有不同的变化
  let sessionHash = hash
  for (let i = 0; i < sessionId.length; i++) {
    sessionHash = sessionId.charCodeAt(i) + ((sessionHash << 3) - sessionHash)
  }

  // 色相偏移：-15到+15度（保持在同一色系）
  const hueOffset = (sessionHash % 31) - 15
  const hue = baseHue + hueOffset

  // 饱和度：60-75%（保持柔和）
  const saturation = 60 + (Math.abs(sessionHash >> 8) % 16)

  // 亮度变化：52-62%（创造层次感）
  const lightness1 = 52 + (Math.abs(sessionHash >> 12) % 8)
  const lightness2 = lightness1 - 8 + (Math.abs(sessionHash >> 16) % 4)

  // 渐变角度：135°或145°交替
  const angle = (sessionHash % 2 === 0) ? 135 : 145

  return {
    background: `linear-gradient(${angle}deg,
      hsl(${hue}, ${saturation}%, ${lightness1}%) 0%,
      hsl(${hue}, ${saturation}%, ${lightness2}%) 100%)`
  }
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
  return props.session.is_unread
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
        <span v-if="isUnread" class="session-item__unread-dot"></span>
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
  border-left: 3px solid transparent;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.session-item:hover {
  background: var(--parchment-50);
  border-color: transparent;
  border-left-color: var(--neutral-300);
}

.session-item--active {
  background: var(--parchment-50);
  border-color: transparent;
  border-left: 3px solid var(--accent);
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
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: var(--font-semibold);
  font-size: var(--font-sm);
  /* 背景色通过 :style 动态设置 */
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
  background: var(--fault);
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
  display: flex;
  align-items: center;
  gap: 6px;
}

/* Unread dot */
.session-item__unread-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  background: var(--fault);
  border-radius: 50%;
}
</style>
