<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { readLLMConfigs, writeLLMConfigs, isSystemConfig, isRequiredConfig, getSystemDisplayName, getSystemConfigs, buildConfigEntry, isConfigEmpty, normalizeEntry } from '@/utils/llmConfigFs'
import { useUIStore } from '@/stores/ui'
import MIcon from '@/components/icons/MIcon.vue'

const uiStore = useUIStore()

const configs = reactive({})
const isLoading = ref(false)
const isSaving = ref(false)
const loadError = ref(null)
const expandedKey = ref(null)
const hasChanges = ref(false)
const newConfigName = ref('')
const showAddRow = ref(false)

const SYSTEM_CONFIGS = getSystemConfigs()
const SYSTEM_ORDER = ['default_llm', 'default_slm', 'default_vision']

const systemEntries = computed(() => SYSTEM_ORDER.filter(n => configs[n] !== undefined))
const customEntries = computed(() => Object.keys(configs).filter(n => !isSystemConfig(n)).sort())

const hasData = computed(() => Object.keys(configs).length > 0)

function isEmpty(entry) {
  return !entry || (!entry.model_name && !entry.api_key && !entry.url)
}

function getSummary(entry) {
  if (isEmpty(entry)) return null
  const parts = []
  if (entry.model_name) parts.push(entry.model_name)
  if (entry.url) {
    try { parts.push(new URL(entry.url).hostname) } catch { parts.push(entry.url) }
  }
  return parts.join('  \u2192  ')
}

function toggleExpand(key) {
  expandedKey.value = expandedKey.value === key ? null : key
}

function trackChange() {
  hasChanges.value = true
}

async function load() {
  isLoading.value = true
  loadError.value = null
  try {
    const data = await readLLMConfigs()
    Object.keys(configs).forEach(k => delete configs[k])
    for (const name of SYSTEM_CONFIGS) {
      configs[name] = normalizeEntry(data[name])
    }
    for (const [name, val] of Object.entries(data)) {
      if (!isSystemConfig(name)) {
        configs[name] = normalizeEntry(val)
      }
    }
    hasChanges.value = false
  } catch (e) {
    console.error('Failed to load LLM configs:', e)
    loadError.value = e.message || String(e)
  } finally {
    isLoading.value = false
  }
}

async function save() {
  isSaving.value = true
  try {
    const out = {}
    for (const name of SYSTEM_CONFIGS) {
      const entry = configs[name]
      if (name === 'default_vision' && isConfigEmpty(entry)) continue
      out[name] = buildConfigEntry(entry)
    }
    for (const name of Object.keys(configs)) {
      if (!isSystemConfig(name)) {
        out[name] = buildConfigEntry(configs[name])
      }
    }
    await writeLLMConfigs(out)
    hasChanges.value = false
    uiStore.showNotification('Configuration saved', 'success')
  } catch (e) {
    console.error('Failed to save:', e)
    uiStore.showNotification('Save failed: ' + e.message, 'error')
  } finally {
    isSaving.value = false
  }
}

function addCustom() {
  const name = newConfigName.value.trim()
  if (!name || isSystemConfig(name) || configs[name]) return
  configs[name] = { model_name: '', api_key: '', url: '' }
  expandedKey.value = name
  newConfigName.value = ''
  showAddRow.value = false
  trackChange()
}

function removeCustom(name) {
  delete configs[name]
  if (expandedKey.value === name) expandedKey.value = null
  trackChange()
}

function clearSystem(name) {
  configs[name] = { model_name: '', api_key: '', url: '' }
  trackChange()
}

function cancelEdit(key) {
  expandedKey.value = null
}

onMounted(load)

defineExpose({ save })
</script>

<template>
  <div class="llm-editor">
    <div v-if="isLoading" class="loading-state">
      <MIcon name="loader" class="spinner" />
      <span>Loading...</span>
    </div>

    <div v-else-if="loadError" class="error-state">
      <p>{{ loadError }}</p>
      <button @click="load">Retry</button>
    </div>

    <template v-else>
      <!-- System -->
      <div class="section">
        <div class="section-label">系统配置</div>
        <div class="cards">
          <div
            v-for="name in systemEntries"
            :key="name"
            :class="['card', 'card-system', { expanded: expandedKey === name }]"
            @click="expandedKey !== name && toggleExpand(name)"
          >
            <!-- Header -->
            <div class="card-header" @click="toggleExpand(name)">
              <div class="card-title-row">
                <span class="card-key">{{ name }}</span>
                <span class="card-display">{{ getSystemDisplayName(name) }}</span>
                <span v-if="isRequiredConfig(name)" class="badge required">Required</span>
                <span v-else class="badge optional">Optional</span>
              </div>
              <div v-if="expandedKey !== name" class="card-summary">
                <template v-if="getSummary(configs[name])">
                  {{ getSummary(configs[name]) }}
                </template>
                <template v-else>
                  <span class="placeholder">Click to configure</span>
                </template>
              </div>
              <span class="expand-icon" :class="{ rotated: expandedKey === name }"><MIcon name="chevron-down" /></span>
            </div>

            <!-- Expanded form -->
            <div v-if="expandedKey === name" class="card-form" @click.stop>
              <div class="field">
                <label>Model</label>
                <input v-model="configs[name].model_name" class="input" placeholder="e.g. gpt-4o" @input="trackChange" />
              </div>
              <div class="field">
                <label>API Key</label>
                <input v-model="configs[name].api_key" class="input" type="password" placeholder="sk-..." @input="trackChange" />
              </div>
              <div class="field">
                <label>URL</label>
                <input v-model="configs[name].url" class="input" placeholder="https://api.openai.com/v1/chat/completions" @input="trackChange" />
              </div>
              <div class="card-actions">
                <button v-if="!isRequiredConfig(name)" class="btn-text danger" @click="clearSystem(name)">Clear</button>
                <button class="btn-text" @click="cancelEdit(name)">Cancel</button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Custom -->
      <div class="section">
        <div class="section-label">
          <span>自定义配置</span>
          <button class="btn-add" @click="showAddRow = true"><MIcon name="plus" /><span>添加</span></button>
        </div>

        <div v-if="showAddRow" class="add-row">
          <input v-model="newConfigName" class="input" placeholder="配置名称" @keyup.enter="addCustom" @keyup.escape="showAddRow = false" />
          <button class="btn-sm primary" @click="addCustom" :disabled="!newConfigName.trim()">添加</button>
          <button class="btn-sm ghost" @click="showAddRow = false; newConfigName = ''">取消</button>
        </div>

        <div class="cards">
          <div
            v-for="name in customEntries"
            :key="name"
            :class="['card', { expanded: expandedKey === name }]"
            @click="expandedKey !== name && toggleExpand(name)"
          >
            <div class="card-header" @click="toggleExpand(name)">
              <div class="card-title-row">
                <span class="card-key">{{ name }}</span>
              </div>
              <div v-if="expandedKey !== name" class="card-summary">
                <template v-if="getSummary(configs[name])">
                  {{ getSummary(configs[name]) }}
                </template>
                <template v-else>
                  <span class="placeholder">Click to configure</span>
                </template>
              </div>
              <span class="expand-icon" :class="{ rotated: expandedKey === name }"><MIcon name="chevron-down" /></span>
            </div>

            <div v-if="expandedKey === name" class="card-form" @click.stop>
              <div class="field">
                <label>Model</label>
                <input v-model="configs[name].model_name" class="input" placeholder="e.g. deepseek-v4-pro" @input="trackChange" />
              </div>
              <div class="field">
                <label>API Key</label>
                <input v-model="configs[name].api_key" class="input" type="password" placeholder="sk-..." @input="trackChange" />
              </div>
              <div class="field">
                <label>URL</label>
                <input v-model="configs[name].url" class="input" placeholder="https://api.example.com/v1/chat/completions" @input="trackChange" />
              </div>
              <div class="card-actions">
                <button class="btn-text danger" @click="removeCustom(name)">Delete</button>
                <button class="btn-text" @click="cancelEdit(name)">Cancel</button>
              </div>
            </div>
          </div>
        </div>

        <div v-if="customEntries.length === 0 && !showAddRow" class="empty-hint">
          暂无自定义配置
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.llm-editor {
  display: flex;
  flex-direction: column;
  gap: 32px;
}

.loading-state, .error-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-12);
  color: var(--text-tertiary);
  font-size: var(--font-sm);
}

.spinner { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.section {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
}

.section-label {
  font-size: 13px;
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  letter-spacing: var(--tracking-wide);
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 2px;
}

.btn-add {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: white;
  color: var(--accent);
  border: 1px solid var(--accent);
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: var(--font-medium);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.btn-add:hover {
  background: var(--accent);
  color: white;
}

.cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

/* Card */
.card {
  background: white;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--duration-base) var(--ease-out);
}

.card.expanded {
  box-shadow: var(--shadow-md);
}

.card-system { border-left: 3px solid var(--accent); }

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 18px;
  cursor: pointer;
  min-height: 48px;
  border-radius: 10px;
  transition: background-color var(--duration-base) var(--ease-out);
}

.card:not(.expanded) .card-header:hover {
  background-color: var(--surface-secondary);
}

.card-title-row {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  flex: 1;
  min-width: 0;
}

.card-key {
  font-family: 'SF Mono', 'Menlo', 'Monaco', monospace;
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.card-display {
  font-size: var(--font-sm);
  color: var(--text-tertiary);
}

.badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: var(--font-medium);
  line-height: 1.5;
}

.badge.required {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
}

.badge.optional {
  background: var(--surface-hover);
  color: var(--text-tertiary);
}

.card-summary {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  text-align: right;
  margin-left: var(--spacing-3);
  margin-right: var(--spacing-1);
}

.placeholder {
  color: var(--text-quaternary);
  font-style: italic;
}

.expand-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  color: var(--text-quaternary);
  font-size: 14px;
  flex-shrink: 0;
  transition: transform var(--duration-base) var(--ease-out);
  pointer-events: none;
}

.expand-icon.rotated {
  transform: rotate(180deg);
}

/* Form */
.card-form {
  padding: 16px 18px 18px;
  border-top: 1px solid var(--border-light);
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field label {
  font-size: var(--font-xs);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
}

.input {
  width: 100%;
  padding: var(--spacing-2) var(--spacing-3);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
  font-size: var(--font-sm);
  color: var(--text-primary);
  outline: none;
  transition: border-color var(--duration-base) var(--ease-out), box-shadow var(--duration-base) var(--ease-out);
}

.input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
  background: var(--surface-base);
}

.input::placeholder {
  color: var(--text-quaternary);
}

.card-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--spacing-2);
  padding-top: var(--spacing-2);
}

.btn-text {
  padding: var(--spacing-1) var(--spacing-2);
  background: none;
  border: none;
  font-size: var(--font-sm);
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: var(--radius-md);
}

.btn-text:hover { background: var(--surface-hover); color: var(--text-primary); }
.btn-text.danger:hover { color: var(--error-600); background: var(--error-50); }

/* Add row */
.add-row {
  display: flex;
  gap: var(--spacing-2);
  align-items: center;
  padding: var(--spacing-2) var(--spacing-3);
  border: 1px dashed var(--border-strong);
  border-radius: var(--radius-md);
}

.add-row .input {
  flex: 1;
  padding: var(--spacing-1) var(--spacing-2);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  background: var(--surface-base);
}

.add-row .input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.btn-sm {
  padding: var(--spacing-1) var(--spacing-3);
  border-radius: var(--radius-md);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  cursor: pointer;
  border: 1px solid var(--border-strong);
  transition: all var(--duration-base) var(--ease-out);
}

.btn-sm.primary {
  background: var(--accent);
  color: white;
  border-color: var(--accent);
}

.btn-sm.primary:disabled {
  background: var(--border-strong);
  color: var(--text-tertiary);
  cursor: not-allowed;
}

.btn-sm.ghost {
  background: transparent;
  color: var(--text-secondary);
}

.empty-hint {
  font-size: var(--font-sm);
  color: var(--text-quaternary);
  text-align: center;
  padding: var(--spacing-4);
}
</style>