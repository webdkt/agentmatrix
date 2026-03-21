<script setup>
import { computed } from 'vue'

const props = defineProps({
  config: {
    type: Object,
    required: true
  },
  isRequired: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits(['edit', 'delete'])

const formatUrl = (url) => {
  if (!url) return 'Not configured'
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

const configIcon = computed(() => {
  return props.isRequired ? 'ti-shield-check' : 'ti-cpu'
})

const configIconClass = computed(() => {
  return props.isRequired ? 'icon-required' : 'icon-custom'
})
</script>

<template>
  <div class="llm-config-card" :class="{ 'card-required': isRequired }">
    <!-- Card Header -->
    <div class="card-header">
      <div :class="['card-icon', configIconClass]">
        <i :class="['ti', configIcon]"></i>
      </div>
      <div v-if="isRequired" class="required-badge">
        <i class="ti ti-shield"></i>
        <span>Required</span>
      </div>
    </div>

    <!-- Card Content -->
    <div class="card-content">
      <h4 class="config-name">{{ config.name }}</h4>
      <p class="config-description">
        {{ config.description || getDefaultDescription(config.name) }}
      </p>

      <div class="config-details">
        <div class="detail-item">
          <i class="ti ti-database"></i>
          <span class="detail-label">Model</span>
          <span class="detail-value">{{ config.model_name || 'Not configured' }}</span>
        </div>
        <div class="detail-item">
          <i class="ti ti-link"></i>
          <span class="detail-label">API</span>
          <span class="detail-value">{{ formatUrl(config.url) }}</span>
        </div>
      </div>
    </div>

    <!-- Card Actions -->
    <div class="card-actions">
      <button
        @click="handleEdit"
        class="btn-action btn-edit"
        title="Edit configuration"
      >
        <i class="ti ti-pencil"></i>
        <span>Edit</span>
      </button>
      <button
        v-if="!isRequired"
        @click="handleDelete"
        class="btn-action btn-delete"
        title="Delete configuration"
      >
        <i class="ti ti-trash"></i>
      </button>
    </div>
  </div>
</template>

<script>
export default {
  methods: {
    getDefaultDescription(name) {
      const descriptions = {
        'default_llm': 'Primary language model for main agent reasoning and complex tasks',
        'default_slm': 'Small language model for simple tasks and quick responses',
        'browser-use-llm': 'Language model for browser automation and web interactions'
      }
      return descriptions[name] || 'Custom LLM configuration'
    }
  }
}
</script>

<style scoped>
.llm-config-card {
  background: white;
  border: 1px solid var(--neutral-200);
  border-radius: var(--radius-lg);
  padding: var(--spacing-lg);
  box-shadow: var(--shadow-sm);
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.llm-config-card:hover {
  box-shadow: var(--shadow-md);
  border-color: var(--neutral-300);
}

.llm-config-card.card-required {
  border-color: var(--primary-200);
  background: linear-gradient(135deg, #fafafa 0%, #f8f9ff 100%);
}

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--spacing-3);
}

.card-icon {
  width: 48px;
  height: 48px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--icon-xl);
  flex-shrink: 0;
  box-shadow: var(--shadow-sm);
}

.icon-required {
  background: linear-gradient(135deg, var(--primary-400), var(--primary-600));
  color: white;
}

.icon-custom {
  background: linear-gradient(135deg, var(--neutral-300), var(--neutral-400));
  color: white;
}

.required-badge {
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  padding: var(--spacing-1) var(--spacing-3);
  background: var(--primary-100);
  color: var(--primary-700);
  border-radius: var(--radius-full);
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  flex-shrink: 0;
}

.required-badge i {
  font-size: var(--icon-sm);
}

.card-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.config-name {
  font-size: var(--font-base);
  font-weight: var(--font-semibold);
  color: var(--neutral-900);
  margin: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.config-description {
  font-size: var(--font-sm);
  color: var(--neutral-600);
  margin: 0;
  line-height: var(--leading-relaxed);
}

.config-details {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  padding-top: var(--spacing-2);
  border-top: 1px solid var(--neutral-100);
}

.detail-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  font-size: var(--font-sm);
}

.detail-item i {
  font-size: var(--icon-md);
  color: var(--neutral-400);
  flex-shrink: 0;
}

.detail-label {
  color: var(--neutral-500);
  font-weight: var(--font-medium);
  flex-shrink: 0;
}

.detail-value {
  color: var(--neutral-700);
  font-weight: var(--font-medium);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.card-actions {
  display: flex;
  gap: var(--spacing-2);
  padding-top: var(--spacing-3);
  border-top: 1px solid var(--neutral-100);
}

.btn-action {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  border-radius: var(--radius-md);
  border: 1px solid var(--neutral-300);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  background: white;
}

.btn-edit {
  flex: 1;
  color: var(--neutral-700);
}

.btn-edit:hover {
  background: var(--primary-50);
  border-color: var(--primary-300);
  color: var(--primary-700);
}

.btn-delete {
  padding: var(--spacing-3);
  color: var(--neutral-400);
  border-color: var(--neutral-200);
}

.btn-delete:hover {
  background: var(--error-50);
  border-color: var(--error-300);
  color: var(--error-600);
}
</style>
