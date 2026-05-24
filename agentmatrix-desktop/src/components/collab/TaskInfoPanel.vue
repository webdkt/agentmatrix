<script setup>
import { ref, computed } from 'vue'
import { useWhiteboard } from '@/composables/useWhiteboard'
import WhiteboardView from './WhiteboardView.vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  agentName: { type: String, required: true },
  sessionId: { type: String, required: true },
})

const whiteboard = useWhiteboard({
  agentName: () => props.agentName,
  sessionId: () => props.sessionId,
})

// ---- Accordion ----
const expandedSection = ref('whiteboard')

function toggleSection(name) {
  expandedSection.value = expandedSection.value === name ? null : name
}

const entryCount = computed(() => {
  let n = 0
  for (const entries of Object.values(whiteboard.sections.value)) n += Object.keys(entries).length
  return n
})
</script>

<template>
  <div class="task-info-panel">
    <!-- Whiteboard -->
    <div class="tip-section" :class="{ 'tip-section--collapsed': expandedSection !== 'whiteboard' }">
      <button class="tip-section__header tip-section__header--whiteboard" @click="toggleSection('whiteboard')">
        <span class="tip-section__header-icon"><MIcon name="clipboard" /></span>
        <span class="tip-section__header-label">Whiteboard</span>
        <span v-if="entryCount" class="tip-section__header-count">{{ entryCount }}</span>
        <MIcon name="chevron-down" class="tip-section__chevron" />
      </button>
      <div v-if="expandedSection === 'whiteboard'" class="tip-section__body">
        <WhiteboardView
          :sections="whiteboard.sections.value"
          :is-loaded="whiteboard.isLoaded.value"
          :agent-name="agentName"
          @save="whiteboard.replaceAll"
        />
      </div>
    </div>

    <!-- Todo -->
    <div class="tip-section" :class="{ 'tip-section--collapsed': expandedSection !== 'todo' }">
      <button class="tip-section__header tip-section__header--todo" @click="toggleSection('todo')">
        <span class="tip-section__header-icon"><MIcon name="list-checks" /></span>
        <span class="tip-section__header-label">Todo</span>
        <MIcon name="chevron-down" class="tip-section__chevron" />
      </button>
      <div v-if="expandedSection === 'todo'" class="tip-section__body">
        <div class="tip-section__placeholder">Coming soon</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.task-info-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  overflow: hidden;
  font-size: 12px;
}

.tip-section {
  display: flex;
  flex-direction: column;
  min-height: 0;
}
.tip-section--collapsed { flex-shrink: 0; }
.tip-section:not(.tip-section--collapsed) { flex: 1; min-height: 0; }

.tip-section__header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 12px;
  width: 100%;
  border: none;
  cursor: pointer;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  flex-shrink: 0;
  transition: background 0.12s ease;
}
.tip-section__header--whiteboard {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
}
.tip-section__header--todo {
  background: color-mix(in srgb, var(--success, #10b981) 10%, transparent);
  color: var(--success, #10b981);
  border-top: 1px solid var(--border-light);
}
.tip-section__header:hover { filter: brightness(0.95); }

.tip-section__header-icon { display: flex; font-size: 13px; }
.tip-section__header-label { flex: 1; text-align: left; }
.tip-section__header-count {
  font-size: 10px; font-weight: 700;
  padding: 1px 6px; border-radius: 9px;
  background: color-mix(in srgb, var(--accent) 20%, transparent);
  color: var(--accent);
}
.tip-section__chevron {
  font-size: 13px;
  transition: transform 0.2s ease;
}
.tip-section--collapsed .tip-section__chevron { transform: rotate(-90deg); }

.tip-section__body { flex: 1; min-height: 0; overflow-y: auto; }
.tip-section__placeholder {
  display: flex; align-items: center; justify-content: center;
  padding: 24px; color: var(--text-quaternary); font-size: 12px;
}
</style>
