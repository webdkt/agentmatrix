<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import MIcon from '@/components/icons/MIcon.vue'

const { t } = useI18n()

const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
  schema: {
    type: Array,
    default: () => [],
  },
  agentName: {
    type: String,
    default: null,
  },
  agentStatus: {
    type: String,
    default: 'IDLE',
  },
})

const emit = defineEmits(['close', 'invoke-action'])

function isDisabled(item) {
  if (!item.requires_idle) return false
  return props.agentStatus !== 'IDLE'
}

function handleAction(item) {
  if (isDisabled(item)) return
  emit('invoke-action', item)
  emit('close')
}

// Click outside to close
function handleClickOutside(e) {
  if (!props.visible) return
  // Defer so button click handler runs first
  setTimeout(() => emit('close'), 0)
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <Transition name="menu-pop">
    <div v-if="visible" class="floating-menu" @click.stop>
      <template v-for="item in schema" :key="item.name || item.action">
        <!-- Group with children -->
        <template v-if="item.children">
          <div class="floating-menu__group">
            <div class="floating-menu__group-label">
              {{ t(`ui_actions.groups.${item.name}`, item.name) }}
            </div>
            <button
              v-for="child in item.children"
              :key="child.action"
              class="floating-menu__item"
              :class="{ 'floating-menu__item--disabled': isDisabled(child) }"
              :disabled="isDisabled(child)"
              @click="handleAction(child)"
            >
              <MIcon :name="child.icon || 'bolt'" />
              <span>{{ t(`ui_actions.actions.${child.action}`, child.action) }}</span>
            </button>
          </div>
        </template>

        <!-- Top-level action -->
        <button
          v-else-if="item.action"
          class="floating-menu__item"
          :class="{ 'floating-menu__item--disabled': isDisabled(item) }"
          :disabled="isDisabled(item)"
          @click="handleAction(item)"
        >
          <MIcon :name="item.icon || 'bolt'" />
          <span>{{ t(`ui_actions.actions.${item.action}`, item.action) }}</span>
        </button>
      </template>

      <!-- Restore to desktop -->
      <div class="floating-menu__divider"></div>
      <button class="floating-menu__item" @click="$emit('close'); $emit('restore')">
        <MIcon name="arrows-maximize" />
        <span>Switch to Desktop</span>
      </button>
    </div>
  </Transition>
</template>

<style scoped>
.floating-menu {
  min-width: 100%;
  padding: 4px 8px 8px;
  border-top: 1px solid rgba(0, 0, 0, 0.04);
}


.floating-menu__group {
  padding: 2px 0;
}

.floating-menu__group-label {
  padding: 6px 12px 4px;
  font-size: 10px;
  font-weight: 600;
  color: var(--text-quaternary, #d4d4d8);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.floating-menu__item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: transparent;
  color: var(--text-secondary, #52525b);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  border-radius: 8px;
  text-align: left;
  white-space: nowrap;
  transition: background 0.12s ease;
}

.floating-menu__item:hover:not(:disabled) {
  background: rgba(0, 0, 0, 0.04);
}

.floating-menu__item--disabled,
.floating-menu__item:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.floating-menu__divider {
  height: 1px;
  background: var(--border-light, #f0f0f2);
  margin: 4px 8px;
}

/* ---- Pop animation ---- */
.menu-pop-enter-active {
  transition: all 0.2s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}
.menu-pop-leave-active {
  transition: all 0.15s ease;
}
.menu-pop-enter-from {
  opacity: 0;
  transform: scale(0.92) translateY(-4px);
}
.menu-pop-leave-to {
  opacity: 0;
  transform: scale(0.95) translateY(-2px);
}
</style>
