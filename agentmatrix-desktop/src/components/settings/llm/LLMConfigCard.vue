<script setup>
import { computed } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'
import { isSystemConfig, isRequiredConfig, getSystemDisplayName, getDefaultDescription } from '@/utils/llmConfigFs'

const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  isSystem: {
    type: Boolean,
    default: false
  },
  isRequired: {
    type: Boolean,
    default: false
  },
  unconfigured: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['edit', 'delete'])

const formatUrl = (url) => {
  if (!url) return ''
  try {
    const urlObj = new URL(url)
    return urlObj.hostname
  } catch {
    return url
  }
}

const handleEdit = () => {
  emit('edit', props.config)
}

const handleDelete = () => {
  emit('delete', props.config.name)
}

const displayName = computed(() => {
  if (isSystemConfig(props.config.name)) {
    return getSystemDisplayName(props.config.name)
  }
  return props.config.name
})

const displayDescription = computed(() => {
  if (props.config.description) return props.config.description
  return getDefaultDescription(props.config.name)
})

const badgeLabel = computed(() => {
  if (props.isRequired) return 'Required'
  if (props.isSystem) return 'System'
  return ''
})

const configIcon = computed(() => {
  return props.isSystem ? 'shield-check' : 'cpu'
})

const configIconClass = computed(() => {
  return props.isSystem ? 'icon-system' : 'icon-custom'
})
</script>

<template>
  <div
    class="llm-config-card"
    :class="{
      'card-system': isSystem,
      'card-required': isRequired,
      'card-unconfigured': unconfigured
    }"
  >
    <!-- Card Header -->
    <div class="card-header">
      <div :class="['card-icon', configIconClass]">
        <MIcon :name="configIcon" />
      </div>
      <div v-if="badgeLabel" class="config-badge" :class="badgeLabel.toLowerCase()">
        <MIcon v-if="isRequired" name="shield" />
        <MIcon v-else name="shield-check" />
        <span>{{ badgeLabel }}</span>
      </div>
    </div>

    <!-- Card Content -->
    <div class="card-content">
      <h4 class="config-name">{{ displayName }}</h4>
      <p v-if="unconfigured" class="config-description unconfigured-text">
        Not yet configured — click Edit to set up
      </p>
      <p v-else class="config-description">
        {{ displayDescription }}
      </p>

      <div v-if="!unconfigured" class="config-details">
        <div class="detail-item">
          <MIcon name="database" />
          <span class="detail-label">Model</span>
          <span class="detail-value">{{ config.model_name || 'Not set' }}</span>
        </div>
        <div class="detail-item">
          <MIcon name="link" />
          <span class="detail-label">API</span>
          <span class="detail-value">{{ formatUrl(config.url) || 'Not set' }}</span>
        </div>
      </div>
    </div>

    <!-- Card Actions -->
    <div class="card-actions">
      <button
        @click="handleEdit"
        class="btn-action btn-edit"
        :title="unconfigured ? 'Configure' : 'Edit configuration'"
      >
        <MIcon :name="unconfigured ? 'plus' : 'pencil'" />
        <span>{{ unconfigured ? 'Configure' : 'Edit' }}</span>
      </button>
      <button
        v-if="!isRequired"
        @click="handleDelete"
        class="btn-action btn-delete"
        title="Delete configuration"
      >
        <MIcon name="trash" />
      </button>
    </div>
  </div>
</template>

<style scoped>
.llm-config-card {
  background: var(--surface-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: var(--spacing-5);
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.llm-config-card:hover {
  border-color: var(--border-strong);
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}

.card-system {
  border-color: var(--border);
  background: var(--surface-secondary);
}

.card-required {
  border-left: 3px solid var(--accent);
}

.card-unconfigured {
  border-style: dashed;
  opacity: 0.8;
}

.card-unconfigured:hover {
  opacity: 1;
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-2);
}

.card-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--icon-lg);
  flex-shrink: 0;
}

.icon-system {
  background: var(--accent);
  color: white;
}

.icon-custom {
  background: var(--text-quaternary);
  color: white;
}

.card-unconfigured .icon-system,
.card-unconfigured .icon-custom {
  background: var(--border-strong);
  color: var(--text-tertiary);
}

.config-badge {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: 2px var(--spacing-2);
  border-radius: var(--radius-sm);
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  flex-shrink: 0;
  line-height: 1.4;
}

.config-badge i {
  font-size: 12px;
}

.config-badge.required {
  background: color-mix(in srgb, var(--accent) 12%, transparent);
  color: var(--accent);
}

.config-badge.system {
  background: var(--surface-hover);
  color: var(--text-tertiary);
}

.card-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
}

.config-name {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-unconfigured .config-name {
  color: var(--text-secondary);
}

.config-description {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  margin: 0;
  line-height: var(--leading-relaxed);
}

.unconfigured-text {
  color: var(--text-tertiary);
  font-style: italic;
}

.config-details {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  padding-top: var(--spacing-2);
  border-top: 1px solid var(--surface-hover);
}

.detail-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--font-sm);
}

.detail-item i {
  font-size: 14px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.detail-label {
  color: var(--text-tertiary);
  font-weight: var(--font-medium);
  flex-shrink: 0;
  min-width: 40px;
}

.detail-value {
  color: var(--text-secondary);
  font-weight: var(--font-medium);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.card-actions {
  display: flex;
  gap: var(--spacing-2);
  padding-top: var(--spacing-2);
  border-top: 1px solid var(--surface-hover);
}

.btn-action {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2) var(--spacing-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  background: white;
}

.btn-action i {
  font-size: 14px;
}

.btn-edit {
  flex: 1;
  color: var(--text-secondary);
}

.btn-edit:hover {
  background: var(--surface-base);
  border-color: var(--text-tertiary);
  color: var(--accent);
}

.card-unconfigured .btn-edit {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.card-unconfigured .btn-edit:hover {
  background: var(--accent-hover);
  color: white;
  border-color: var(--accent-hover);
}

.btn-delete {
  padding: var(--spacing-2);
  color: var(--text-tertiary);
  border-color: var(--border);
}

.btn-delete:hover {
  background: var(--error-50);
  border-color: var(--error-300);
  color: var(--error-600);
}
</style>