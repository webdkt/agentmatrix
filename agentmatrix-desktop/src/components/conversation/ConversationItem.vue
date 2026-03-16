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
    :class="isActive ? 'bg-primary-50/70 border-primary-200' : 'border-transparent hover:bg-surface-50 hover:border-surface-200'"
    class="session-item cursor-pointer p-3 rounded-xl border transition-all duration-200"
  >
    <div class="flex items-center gap-3">
      <!-- Avatar with gradient based on index -->
      <div class="relative">
        <div
          :class="avatarColorClass"
          class="w-11 h-11 rounded-full bg-gradient-to-br flex items-center justify-center text-white font-semibold shadow-card flex-shrink-0"
        >
          <span>{{ subjectInitial }}</span>
        </div>

        <!-- 待处理图标 -->
        <div
          v-if="hasPending"
          class="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full border-2 border-white flex items-center justify-center shadow-sm"
        >
          <span class="text-white text-xs font-bold">1</span>
        </div>
      </div>

      <div class="flex-1 min-w-0">
        <!-- Agent Names (top, bold, prominent) -->
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2 flex-1 min-w-0">
            <span class="font-bold text-black text-base truncate">
              {{ displayParticipants }}
            </span>
          </div>
          <span class="text-xs text-surface-400 flex-shrink-0">
            {{ formatDate(session.last_email_time) }}
          </span>
        </div>

        <!-- Subject (bottom, regular, prevents overflow) -->
        <p class="text-sm text-surface-600 truncate mt-1">
          {{ session.subject || 'No Subject' }}
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.session-item {
  transition: all 0.2s ease;
}

.shadow-card {
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}
</style>
