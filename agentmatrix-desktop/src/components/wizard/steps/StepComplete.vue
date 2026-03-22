<script setup>
import { ref } from 'vue'
import { useConfigStore } from '@/stores/config'
import MIcon from '@/components/icons/MIcon.vue'

const configStore = useConfigStore()
const showEmailProxy = ref(false)
</script>

<template>
  <div class="step">
    <h2 class="step__title">Review & Launch</h2>
    <p class="step__desc">
      Review your configuration and start your AgentMatrix workspace.
    </p>

    <!-- Summary -->
    <div class="step__summary">
      <div class="step__summary-item">
        <MIcon name="user" />
        <div>
          <span class="step__summary-label">User Name</span>
          <span class="step__summary-value">{{ configStore.wizardData.user_name }}</span>
        </div>
      </div>

      <div class="step__summary-item">
        <MIcon name="folder" />
        <div>
          <span class="step__summary-label">Data Directory</span>
          <span class="step__summary-value step__summary-value--mono">
            {{ configStore.wizardData.matrix_world_path }}
          </span>
        </div>
      </div>

      <div class="step__summary-item">
        <MIcon name="brain" />
        <div>
          <span class="step__summary-label">Large Model</span>
          <span class="step__summary-value">
            {{ configStore.wizardData.default_llm.model_name }}
            <span class="step__badge">{{ configStore.wizardData.default_llm.provider }}</span>
          </span>
        </div>
      </div>

      <div class="step__summary-item">
        <MIcon name="bolt" />
        <div>
          <span class="step__summary-label">Small Model</span>
          <span class="step__summary-value">
            {{ configStore.wizardData.default_slm.model_name }}
            <span class="step__badge">{{ configStore.wizardData.default_slm.provider }}</span>
          </span>
        </div>
      </div>
    </div>

    <!-- Email Proxy (Optional) -->
    <div class="step__optional">
      <button
        class="step__optional-toggle"
        @click="showEmailProxy = !showEmailProxy"
      >
        <MIcon :name="showEmailProxy ? 'chevron-down' : 'chevron-right'" />
        <MIcon name="mail" />
        Email Proxy Service (Optional)
      </button>

      <div v-if="showEmailProxy" class="step__email-proxy">
        <div class="step__field">
          <label class="step__checkbox-label">
            <input
              v-model="configStore.wizardData.email_proxy.enabled"
              type="checkbox"
            />
            Enable Email Proxy
          </label>
        </div>

        <template v-if="configStore.wizardData.email_proxy.enabled">
          <div class="step__row">
            <div class="step__field">
              <label class="step__label">Matrix Mailbox</label>
              <input
                v-model="configStore.wizardData.email_proxy.matrix_mailbox"
                class="input"
                type="text"
                placeholder="matrix@example.com"
              />
            </div>
            <div class="step__field">
              <label class="step__label">User Mailbox</label>
              <input
                v-model="configStore.wizardData.email_proxy.user_mailbox"
                class="input"
                type="text"
                placeholder="user@example.com"
              />
            </div>
          </div>

          <div class="step__row">
            <div class="step__field">
              <label class="step__label">IMAP Host</label>
              <input
                v-model="configStore.wizardData.email_proxy.imap.host"
                class="input"
                type="text"
                placeholder="imap.gmail.com"
              />
            </div>
            <div class="step__field step__field--small">
              <label class="step__label">Port</label>
              <input
                v-model.number="configStore.wizardData.email_proxy.imap.port"
                class="input"
                type="number"
                placeholder="993"
              />
            </div>
          </div>

          <div class="step__row">
            <div class="step__field">
              <label class="step__label">SMTP Host</label>
              <input
                v-model="configStore.wizardData.email_proxy.smtp.host"
                class="input"
                type="text"
                placeholder="smtp.gmail.com"
              />
            </div>
            <div class="step__field step__field--small">
              <label class="step__label">Port</label>
              <input
                v-model.number="configStore.wizardData.email_proxy.smtp.port"
                class="input"
                type="number"
                placeholder="587"
              />
            </div>
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.step {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
}

.step__title {
  font-family: var(--font-serif);
  font-size: var(--font-xl);
  font-weight: var(--font-semibold);
  color: var(--neutral-800);
  margin: 0;
}

.step__desc {
  font-size: var(--font-sm);
  color: var(--neutral-500);
  margin: 0;
  line-height: 1.6;
}

/* Summary */
.step__summary {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
}

.step__summary-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-md);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--neutral-50);
  border-radius: var(--radius-sm);
}

.step__summary-item > i {
  font-size: 20px;
  color: var(--accent);
  flex-shrink: 0;
}

.step__summary-item > div {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.step__summary-label {
  font-size: var(--font-xs);
  color: var(--neutral-400);
  font-weight: var(--font-medium);
}

.step__summary-value {
  font-size: var(--font-sm);
  color: var(--neutral-800);
  font-weight: var(--font-medium);
}

.step__summary-value--mono {
  font-family: var(--font-mono);
  font-size: var(--font-xs);
}

.step__badge {
  display: inline-block;
  padding: 1px 6px;
  background: var(--neutral-100);
  color: var(--neutral-700);
  border-radius: var(--radius-sm);
  font-size: 11px;
  font-weight: var(--font-medium);
  font-variant: small-caps;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

/* Optional section */
.step__optional {
  border-top: 1px solid var(--neutral-200);
  padding-top: var(--spacing-md);
}

.step__optional-toggle {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  background: none;
  border: none;
  cursor: pointer;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--neutral-600);
  padding: var(--spacing-xs) 0;
}

.step__optional-toggle:hover {
  color: var(--accent);
}

/* Email Proxy form */
.step__email-proxy {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-sm);
  padding: var(--spacing-md);
  background: var(--neutral-50);
  border-radius: var(--radius-sm);
  margin-top: var(--spacing-sm);
}

.step__row {
  display: flex;
  gap: var(--spacing-sm);
}

.step__field {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
  flex: 1;
}

.step__field--small {
  flex: 0 0 100px;
}

.step__label {
  font-size: var(--font-xs);
  font-weight: var(--font-medium);
  color: var(--neutral-600);
}

.step__checkbox-label {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  font-size: var(--font-sm);
  color: var(--neutral-700);
  cursor: pointer;
}
</style>
