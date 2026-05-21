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
const hasChanges = ref(false)
const newConfigName = ref('')
const showAddRow = ref(false)
const showKeys = reactive({})

const SYSTEM_CONFIGS = getSystemConfigs()
const SYSTEM_ORDER = ['default_llm', 'default_slm', 'default_vision']

const systemIconMap = {
  default_llm: 'brain',
  default_slm: 'bolt',
  default_vision: 'eye',
}

const systemDescMap = {
  default_llm: '主推理模型，用于 Agent 核心决策',
  default_slm: '轻量模型，用于快速响应和简单任务',
  default_vision: '视觉模型，用于图像理解（可选）',
}

const systemEntries = computed(() => SYSTEM_ORDER.filter(n => configs[n] !== undefined))
const customEntries = computed(() => Object.keys(configs).filter(n => !isSystemConfig(n)).sort())

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

function trackChange() {
  hasChanges.value = true
}

function toggleShowKey(name) {
  showKeys[name] = !showKeys[name]
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
  showKeys[name] = false
  newConfigName.value = ''
  showAddRow.value = false
  trackChange()
}

function removeCustom(name) {
  delete configs[name]
  delete showKeys[name]
  trackChange()
}

function clearSystem(name) {
  configs[name] = { model_name: '', api_key: '', url: '' }
  trackChange()
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
      <button class="retry-btn" @click="load">Retry</button>
    </div>

    <template v-else>
      <!-- ═══ System Configs ═══ -->
      <div class="section-group">
        <div class="section-group-header">
          <MIcon name="settings" :size="14" class="group-icon" />
          <span>系统配置</span>
        </div>

        <div
          v-for="name in systemEntries"
          :key="name"
          class="sec"
        >
          <div class="sec-side">
            <div class="sec-icon">
              <MIcon :name="systemIconMap[name] || 'box'" :size="16" />
            </div>
            <div class="sec-text">
              <div class="sec-title">
                {{ getSystemDisplayName(name) }}
                <span v-if="isRequiredConfig(name)" class="badge required">Required</span>
                <span v-else class="badge optional">Optional</span>
              </div>
              <div class="sec-desc">{{ systemDescMap[name] || '' }}</div>
              <div v-if="getSummary(configs[name])" class="sec-summary">{{ getSummary(configs[name]) }}</div>
            </div>
          </div>

          <div class="sec-main">
            <div class="sec-row">
              <div class="fi">
                <label class="fi-lbl">Model</label>
                <input
                  v-model="configs[name].model_name"
                  class="fi-inp mono"
                  placeholder="e.g. gpt-4o"
                  spellcheck="false"
                  @input="trackChange"
                />
              </div>
              <div class="fi">
                <label class="fi-lbl">API Key</label>
                <div class="pw-wrap">
                  <input
                    v-model="configs[name].api_key"
                    :type="showKeys[name] ? 'text' : 'password'"
                    class="fi-inp mono"
                    placeholder="sk-..."
                    spellcheck="false"
                    @input="trackChange"
                  />
                  <button class="eye-btn" @click="toggleShowKey(name)" type="button">
                    <MIcon :name="showKeys[name] ? 'eye-off' : 'eye'" :size="14" />
                  </button>
                </div>
              </div>
              <div class="fi">
                <label class="fi-lbl">Endpoint URL</label>
                <input
                  v-model="configs[name].url"
                  class="fi-inp mono"
                  placeholder="https://api.openai.com/v1"
                  spellcheck="false"
                  @input="trackChange"
                />
              </div>
            </div>
            <div v-if="!isRequiredConfig(name)" class="sec-actions">
              <button class="btn-text danger" @click="clearSystem(name)">
                <MIcon name="trash" :size="12" />
                Clear
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- ═══ Custom Configs ═══ -->
      <div class="section-group">
        <div class="section-group-header">
          <div class="group-header-left">
            <MIcon name="layers" :size="14" class="group-icon" />
            <span>自定义配置</span>
          </div>
          <button class="btn-add" @click="showAddRow = true">
            <MIcon name="plus" :size="12" />
            <span>添加</span>
          </button>
        </div>

        <!-- Add row -->
        <div v-if="showAddRow" class="add-row">
          <input
            v-model="newConfigName"
            class="fi-inp"
            placeholder="配置名称"
            @keyup.enter="addCustom"
            @keyup.escape="showAddRow = false; newConfigName = ''"
          />
          <button class="btn-sm primary" :disabled="!newConfigName.trim()" @click="addCustom">添加</button>
          <button class="btn-sm ghost" @click="showAddRow = false; newConfigName = ''">取消</button>
        </div>

        <!-- Custom entries -->
        <div
          v-for="name in customEntries"
          :key="name"
          class="sec"
        >
          <div class="sec-side">
            <div class="sec-icon custom">
              <MIcon name="database" :size="16" />
            </div>
            <div class="sec-text">
              <div class="sec-title">{{ name }}</div>
              <div v-if="getSummary(configs[name])" class="sec-summary">{{ getSummary(configs[name]) }}</div>
              <div v-else class="sec-desc placeholder">未配置</div>
            </div>
          </div>

          <div class="sec-main">
            <div class="sec-row">
              <div class="fi">
                <label class="fi-lbl">Model</label>
                <input
                  v-model="configs[name].model_name"
                  class="fi-inp mono"
                  placeholder="e.g. deepseek-v4-pro"
                  spellcheck="false"
                  @input="trackChange"
                />
              </div>
              <div class="fi">
                <label class="fi-lbl">API Key</label>
                <div class="pw-wrap">
                  <input
                    v-model="configs[name].api_key"
                    :type="showKeys[name] ? 'text' : 'password'"
                    class="fi-inp mono"
                    placeholder="sk-..."
                    spellcheck="false"
                    @input="trackChange"
                  />
                  <button class="eye-btn" @click="toggleShowKey(name)" type="button">
                    <MIcon :name="showKeys[name] ? 'eye-off' : 'eye'" :size="14" />
                  </button>
                </div>
              </div>
              <div class="fi">
                <label class="fi-lbl">Endpoint URL</label>
                <input
                  v-model="configs[name].url"
                  class="fi-inp mono"
                  placeholder="https://api.example.com/v1"
                  spellcheck="false"
                  @input="trackChange"
                />
              </div>
            </div>
            <div class="sec-actions">
              <button class="btn-text danger" @click="removeCustom(name)">
                <MIcon name="trash" :size="12" />
                Delete
              </button>
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
/* ═══════════════════════════════════════
   STATES
   ═══════════════════════════════════════ */
.loading-state, .error-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-12);
  color: var(--text-tertiary);
  font-size: var(--font-sm);
}

.error-state {
  flex-direction: column;
  gap: var(--spacing-3);
}

.error-state p {
  color: var(--error);
  font-size: var(--font-sm);
}

.retry-btn {
  padding: var(--spacing-1) var(--spacing-3);
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-md);
  background: var(--surface-secondary);
  color: var(--text-secondary);
  font-size: var(--font-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.retry-btn:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.spinner { animation: spin 1s linear infinite; }
@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

/* ═══════════════════════════════════════
   SECTION GROUP
   ═══════════════════════════════════════ */
.section-group {
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  overflow: hidden;
  margin-bottom: 24px;
  box-shadow: var(--shadow-sm);
}

.section-group-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 20px;
  border-bottom: 1px solid var(--border-light);
  font-size: var(--font-sm);
  font-weight: var(--font-semibold);
  color: var(--text-primary);
  letter-spacing: var(--tracking-wide);
}

.group-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.group-icon {
  color: var(--text-tertiary);
}

/* ═══════════════════════════════════════
   SECTION — left title + right fields
   ═══════════════════════════════════════ */
.sec {
  display: grid;
  grid-template-columns: 200px 1fr;
  padding: 20px 20px;
  border-bottom: 1px solid var(--border-light);
  transition: background-color var(--duration-base) var(--ease-out);
}

.sec:last-child {
  border-bottom: none;
}

.sec:nth-child(even) {
  background: var(--surface-secondary);
}

/* ─── Left side: icon + title + description ─── */
.sec-side {
  display: flex;
  gap: 12px;
  padding-right: 20px;
}

.sec-icon {
  width: 32px;
  height: 32px;
  border-radius: var(--radius-md);
  background: var(--accent-muted);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
  flex-shrink: 0;
}

.sec-icon.custom {
  background: var(--violet-soft);
  color: var(--violet);
}

.sec-text {
  padding-top: 2px;
  min-width: 0;
}

.sec-title {
  font-size: var(--font-base);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin-bottom: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.sec-desc {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  line-height: var(--leading-relaxed);
}

.sec-desc.placeholder {
  color: var(--text-quaternary);
  font-style: italic;
}

.sec-summary {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  margin-top: 6px;
  font-family: var(--font-mono);
  line-height: 1.4;
  word-break: break-all;
}

.badge {
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 3px;
  font-weight: var(--font-medium);
  line-height: 1.5;
  flex-shrink: 0;
}

.badge.required {
  background: color-mix(in srgb, var(--accent) 10%, transparent);
  color: var(--accent);
}

.badge.optional {
  background: var(--surface-hover);
  color: var(--text-tertiary);
}

/* ─── Right side: form fields ─── */
.sec-main {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.sec-row {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 14px;
}

/* ═══════════════════════════════════════
   FIELDS
   ═══════════════════════════════════════ */
.fi {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.fi-lbl {
  font-size: var(--font-sm);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  letter-spacing: 0.04em;
}

.fi-inp {
  width: 100%;
  padding: 8px 12px;
  background: var(--surface-secondary);
  border: 1.5px solid #B0B0B4;
  border-radius: var(--radius-sm);
  font-size: var(--font-base);
  color: var(--text-primary);
  transition: all var(--duration-base) var(--ease-out);
  caret-color: var(--accent);
  outline: none;
}

.fi-inp::placeholder { color: var(--text-quaternary); }

.fi-inp:focus {
  outline: none;
  border-color: var(--accent);
  border-width: 3px;
  padding: 7px 11px;
  background: var(--surface-base);
  box-shadow: 0 0 0 3px var(--accent-muted);
}

.fi-inp.mono {
  font-family: var(--font-mono);
  font-size: var(--font-sm);
}

/* ─── Password ─── */
.pw-wrap {
  position: relative;
  width: 100%;
}

.pw-wrap .fi-inp {
  padding-right: 32px;
}

.eye-btn {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  background: none;
  border: none;
  color: var(--text-quaternary);
  cursor: pointer;
  padding: 2px;
  display: flex;
  align-items: center;
  transition: color var(--duration-base) var(--ease-out);
}

.eye-btn:hover { color: var(--text-tertiary); }

/* ─── Section actions ─── */
.sec-actions {
  display: flex;
  justify-content: flex-end;
}

/* ═══════════════════════════════════════
   BUTTONS
   ═══════════════════════════════════════ */
.btn-text {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: var(--spacing-1) var(--spacing-2);
  background: none;
  border: none;
  font-size: var(--font-sm);
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: var(--radius-md);
  transition: all var(--duration-base) var(--ease-out);
}

.btn-text:hover { background: var(--surface-hover); color: var(--text-primary); }
.btn-text.danger { color: var(--text-tertiary); }
.btn-text.danger:hover { color: var(--error); background: var(--error-muted); }

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

/* ─── Add row ─── */
.add-row {
  display: flex;
  gap: var(--spacing-2);
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-light);
  background: var(--surface-secondary);
}

.add-row .fi-inp {
  flex: 1;
  max-width: 240px;
  background: var(--surface-base);
}

.btn-sm {
  padding: 6px 14px;
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
  border-color: var(--border-strong);
}

.btn-sm.ghost {
  background: transparent;
  color: var(--text-secondary);
}

.btn-sm.ghost:hover {
  background: var(--surface-hover);
}

/* ═══════════════════════════════════════
   EMPTY HINT
   ═══════════════════════════════════════ */
.empty-hint {
  font-size: var(--font-sm);
  color: var(--text-quaternary);
  text-align: center;
  padding: var(--spacing-8) var(--spacing-4);
}
</style>
