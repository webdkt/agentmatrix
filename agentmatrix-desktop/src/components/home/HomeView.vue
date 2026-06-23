<script setup>
import { useI18n } from 'vue-i18n'
import MIcon from '@/components/icons/MIcon.vue'

const emit = defineEmits(['view-change'])
const { t } = useI18n()

const cards = [
  { id: 'collab', icon: 'message-circle', titleKey: 'views.collab.title', subtitleKey: 'views.home.subtitle.collab' },
  { id: 'automation', icon: 'bolt', titleKey: 'views.automation.title', subtitleKey: 'views.home.subtitle.automation' },
  { id: 'knowledge', icon: 'book', titleKey: 'views.knowledge.title', subtitleKey: 'views.home.subtitle.knowledge' },
  { id: 'design', icon: 'palette', titleKey: 'views.design.title', subtitleKey: 'views.home.subtitle.design' },
]

function open(viewId) {
  emit('view-change', viewId)
}
</script>

<template>
  <div class="home-view">
    <div class="home-view__grid">
      <button
        v-for="card in cards"
        :key="card.id"
        class="home-card"
        @click="open(card.id)"
      >
        <div class="home-card__icon">
          <MIcon :name="card.icon" :size="32" />
        </div>
        <div class="home-card__text">
          <div class="home-card__title">{{ t(card.titleKey) }}</div>
          <div class="home-card__subtitle">{{ t(card.subtitleKey) }}</div>
        </div>
      </button>
    </div>
  </div>
</template>

<style scoped>
.home-view {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--spacing-6);
}

.home-view__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-5);
  width: 100%;
  max-width: 720px;
}

.home-card {
  display: flex;
  align-items: center;
  gap: var(--spacing-4);
  padding: var(--spacing-6);
  background: var(--surface-base);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  text-align: left;
  transition: all var(--duration-base) var(--ease-out);
  min-height: 140px;
}

.home-card:hover {
  border-color: var(--accent);
  background: var(--surface-hover);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
}

.home-card:active {
  transform: translateY(0);
}

.home-card__icon {
  width: 56px;
  height: 56px;
  border-radius: var(--radius-md);
  background: rgba(184, 169, 201, 0.25);
  color: var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.home-card__text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.home-card__title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.home-card__subtitle {
  font-size: 13px;
  color: var(--text-tertiary);
  line-height: 1.4;
}
</style>
