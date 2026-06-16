<script setup>
import { computed, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useServiceStore } from '@/stores/service'
import ServiceDetail from './ServiceDetail.vue'

const { t } = useI18n()
const serviceStore = useServiceStore()

// 2-state: 'list' | 'detail'
const viewState = computed(() => serviceStore.currentService ? 'detail' : 'list')

onMounted(async () => {
  await serviceStore.fetchServices()
})

function onSelectService(name) {
  serviceStore.selectService(name)
}

function onBack() {
  serviceStore.reset()
}

function statusColor(running) {
  return running ? 'var(--success)' : 'var(--text-tertiary)'
}

const loading = computed(() => serviceStore.loading)
</script>

<template>
  <div class="services-view">
    <!-- Header / Breadcrumb -->
    <div class="services-view__header">
      <template v-if="viewState === 'list'">
        <h1 class="services-view__title">{{ t('services.title') }}</h1>
      </template>
      <template v-else>
        <span class="services-view__title">{{ t('services.title') }}</span>
      </template>
    </div>

    <!-- List View -->
    <div v-if="viewState === 'list'" class="services-view__list">
      <div v-if="loading && !serviceStore.services.length" class="services-view__loading">
        {{ t('services.loading') }}
      </div>
      <div v-else-if="!serviceStore.services.length" class="services-view__empty">
        {{ t('services.noServices') }}
      </div>
      <div v-else class="service-cards">
        <button
          v-for="svc in serviceStore.services"
          :key="svc.name"
          class="service-card"
          @click="onSelectService(svc.name)"
        >
          <div class="service-card__header">
            <span class="service-card__status-dot" :style="{ background: statusColor(svc.running) }"></span>
            <span class="service-card__name">{{ svc.name }}</span>
          </div>
          <div class="service-card__meta">
            <span>{{ svc.worker_count || 0 }} {{ t('services.workers.title').toLowerCase() }}</span>
            <span v-if="svc.working_count" class="service-card__working">{{ svc.working_count }} working</span>
          </div>
        </button>
      </div>
    </div>

    <!-- Detail View (with internal split panel) -->
    <ServiceDetail
      v-else
      :service="serviceStore.currentService"
      @back="onBack"
    />
  </div>
</template>

<style scoped>
.services-view {
  width: 100%;
  height: 100%;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.services-view__header {
  padding: var(--spacing-3) var(--spacing-4);
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.services-view__title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.services-view__list {
  flex: 1;
  overflow-y: auto;
  padding: var(--spacing-4);
}

.services-view__loading,
.services-view__empty {
  text-align: center;
  color: var(--text-tertiary);
  padding: var(--spacing-8);
}

.service-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--spacing-4);
}

.service-card {
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: var(--spacing-4);
  cursor: pointer;
  text-align: left;
  transition: all var(--duration-base) var(--ease-out);
}

.service-card:hover {
  border-color: var(--accent);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.service-card__header {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  margin-bottom: var(--spacing-2);
}

.service-card__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.service-card__name {
  font-weight: 600;
  font-size: 15px;
  color: var(--text-primary);
}

.service-card__meta {
  display: flex;
  gap: var(--spacing-3);
  font-size: 13px;
  color: var(--text-tertiary);
}

.service-card__working {
  color: var(--accent);
}
</style>
