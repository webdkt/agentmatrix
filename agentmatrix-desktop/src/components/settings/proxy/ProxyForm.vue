<script setup>
import { ref, onMounted } from 'vue'
import MIcon from '@/components/icons/MIcon.vue'

const props = defineProps({
  config: {
    type: Object,
    default: null
  }
})

const emit = defineEmits(['save', 'close'])

const host = ref('')
const port = ref('')

onMounted(() => {
  if (props.config) {
    host.value = props.config.host || ''
    port.value = props.config.port ? String(props.config.port) : ''
  }
})

const handleSave = () => {
  if (!host.value || !port.value) return
  emit('save', {
    host: host.value,
    port: port.value
  })
}

const handleCancel = () => {
  emit('close')
}

const handleOverlayClick = (e) => {
  if (e.target === e.currentTarget) {
    emit('close')
  }
}
</script>

<template>
  <div class="modal-overlay" @click="handleOverlayClick">
    <div class="modal-container">
      <div class="modal-header">
        <h2 class="modal-title">HTTP Proxy Configuration</h2>
        <button class="close-button" @click="handleCancel">
          <MIcon name="x" />
        </button>
      </div>

      <div class="modal-body">
        <div class="form-section">
          <p class="form-section-description">
            Configure an HTTP proxy server to route LLM API calls and agent container network traffic.
            When enabled, all outgoing HTTP/HTTPS requests will pass through this proxy.
          </p>

          <div class="form-group">
            <label class="form-label" for="proxy-host">Proxy Host</label>
            <input
              id="proxy-host"
              v-model="host"
              type="text"
              class="form-input"
              placeholder="127.0.0.1"
            />
            <span class="form-hint">The proxy server IP address or hostname</span>
          </div>

          <div class="form-group">
            <label class="form-label" for="proxy-port">Proxy Port</label>
            <input
              id="proxy-port"
              v-model="port"
              type="number"
              class="form-input"
              placeholder="7890"
              min="1"
              max="65535"
            />
            <span class="form-hint">The proxy server port number (1-65535)</span>
          </div>
        </div>

        <div class="form-help">
          <h4>How it works</h4>
          <ul>
            <li>LLM API calls will route through the proxy via HTTP_PROXY environment variables</li>
            <li>Agent containers will use the proxy with container-specific hostname mapping</li>
            <li>Podman containers use <code>host.containers.internal</code>, Docker uses <code>host.docker.internal</code></li>
          </ul>
        </div>
      </div>

      <div class="modal-footer">
        <button class="cancel-button" @click="handleCancel">Cancel</button>
        <button
          class="save-button"
          @click="handleSave"
          :disabled="!host || !port"
        >
          Save
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-container {
  background: white;
  border-radius: var(--radius-xl);
  width: 520px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--spacing-6) var(--spacing-8);
  border-bottom: 1px solid var(--border);
}

.modal-title {
  font-size: var(--font-lg);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  margin: 0;
}

.close-button {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--icon-base);
}

.close-button:hover {
  background: var(--surface-hover);
  color: var(--text-secondary);
}

.modal-body {
  padding: var(--spacing-8);
  overflow-y: auto;
}

.form-section-description {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  margin: 0 0 var(--spacing-6) 0;
  line-height: 1.5;
}

.form-group {
  margin-bottom: var(--spacing-6);
}

.form-label {
  display: block;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  color: var(--text-secondary);
  margin-bottom: var(--spacing-1);
}

.form-input {
  width: 100%;
  padding: var(--spacing-2) var(--spacing-4);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  color: var(--text-primary);
  background: white;
  transition: border-color var(--duration-base) var(--ease-out);
  box-sizing: border-box;
}

.form-input:focus {
  outline: none;
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-muted);
}

.form-input::placeholder {
  color: var(--text-tertiary);
}

.form-hint {
  display: block;
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  margin-top: var(--spacing-1);
}

.form-help {
  margin-top: var(--spacing-6);
  padding: var(--spacing-4);
  background: var(--surface-base);
  border-radius: var(--radius-md);
  border: 1px solid var(--border);
}

.form-help h4 {
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-secondary);
  margin: 0 0 var(--spacing-2) 0;
}

.form-help ul {
  margin: 0;
  padding-left: var(--spacing-6);
}

.form-help li {
  font-size: var(--font-xs);
  color: var(--text-secondary);
  line-height: 1.6;
}

.form-help code {
  background: var(--border);
  padding: 1px 4px;
  border-radius: 3px;
  font-size: var(--font-xs);
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-2);
  padding: var(--spacing-6) var(--spacing-8);
  border-top: 1px solid var(--border);
}

.cancel-button {
  padding: var(--spacing-2) var(--spacing-6);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-strong);
  background: white;
  color: var(--text-secondary);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.cancel-button:hover {
  background: var(--surface-base);
}

.save-button {
  padding: var(--spacing-2) var(--spacing-6);
  border-radius: var(--radius-md);
  border: none;
  background: var(--accent);
  color: white;
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.save-button:hover:not(:disabled) {
  background: var(--accent-hover);
}

.save-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
