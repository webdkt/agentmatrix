<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useConfigStore } from '@/stores/config'
import ModelSelector from '@/components/wizard/ModelSelector.vue'
import MIcon from '@/components/icons/MIcon.vue'

const emit = defineEmits(['complete'])
const configStore = useConfigStore()

const slmSameAsBrain = ref(true)

const providers = computed(() => {
  return Object.entries(configStore.llmPresets).map(([key, preset]) => ({ key, label: preset.label }))
})

const isFormValid = computed(() => {
  const d = configStore.wizardData
  const nameOk = d.user_name.trim().length > 0
  const dirOk = d.matrix_world_path.trim().length > 0
  const llm = d.default_llm
  const brainOk = llm.model_name?.trim() && llm.api_key?.trim() && llm.url?.trim()
  if (slmSameAsBrain.value) return nameOk && dirOk && brainOk
  const slm = d.default_slm
  const cerebellumOk = slm.model_name?.trim() && slm.api_key?.trim() && slm.url?.trim()
  return nameOk && dirOk && brainOk && cerebellumOk
})

function selectProvider(field, providerKey) {
  configStore.selectLLMPreset(field, providerKey)
}

function onBrainModelChange(val) { configStore.wizardData.default_llm.model_name = val }
function onBrainProviderChange(val) { configStore.wizardData.default_llm.provider = val }
function onBrainUrlChange(val) { if (val?.trim()) configStore.wizardData.default_llm.url = val }

function onSlmModelChange(val) { configStore.wizardData.default_slm.model_name = val }
function onSlmProviderChange(val) { configStore.wizardData.default_slm.provider = val }
function onSlmUrlChange(val) { if (val?.trim()) configStore.wizardData.default_slm.url = val }

const showBrainKey = ref(false)
const showSlmKey = ref(false)

watch(slmSameAsBrain, (val) => {
  if (val) {
    configStore.wizardData.default_slm = { ...configStore.wizardData.default_llm }
  }
})

async function handleSubmit() {
  configStore.submitError = null
  if (slmSameAsBrain.value) {
    configStore.wizardData.default_slm = { ...configStore.wizardData.default_llm }
  }
  try {
    await configStore.submitWizard()
    emit('complete')
  } catch (error) { /* handled in store */ }
}

function clearError() {
  configStore.submitError = null
}

onMounted(async () => {
  await configStore.loadPresets()
})
</script>

<template>
  <div class="wiz">
    <!-- ── Header ── -->
    <header class="wiz-header">
      <div class="wiz-header-left">
        <div class="wiz-logo"><MIcon name="sparkles" :size="20" /></div>
        <div>
          <h1 class="wiz-title">AgentMatrix Setup</h1>
          <p class="wiz-sub">Complete all fields below, then launch.</p>
        </div>
      </div>
    </header>

    <!-- ── Sections ── -->
    <div class="wiz-body">

      <!-- Section 1: Profile -->
      <section class="sec">
        <div class="sec-side">
          <div class="sec-icon"><MIcon name="user" :size="16" /></div>
          <div class="sec-text">
            <div class="sec-title">基础设置</div>
            <div class="sec-desc">你的名字用于 Agent 如何称呼你。工作目录是 Matrix 存储所有配置和数据的位置。</div>
          </div>
        </div>
        <div class="sec-main">
          <div class="sec-row">
            <div class="fi">
              <label class="fi-lbl">Your Name</label>
              <input v-model="configStore.wizardData.user_name" class="fi-inp" type="text" placeholder="e.g. Alice" autofocus autocomplete="off" spellcheck="false" />
            </div>
            <div class="fi fi--grow">
              <label class="fi-lbl">Workspace Directory</label>
              <div class="dir-row" @click="configStore.selectDirectory()">
                <span class="dir-path" :class="{ has: configStore.wizardData.matrix_world_path }">
                  {{ configStore.wizardData.matrix_world_path || 'Click to choose directory...' }}
                </span>
                <span class="dir-btn">Browse</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      <!-- Section 2: Brain -->
      <section class="sec">
        <div class="sec-side">
          <div class="sec-icon"><MIcon name="brain" :size="16" /></div>
          <div class="sec-text">
            <div class="sec-title">大脑模型</div>
            <div class="sec-desc">Brain 是主推理模型，负责复杂任务。选择供应商可自动填充 URL 和默认模型名。</div>
          </div>
        </div>
        <div class="sec-main">
          <div class="sec-row">
            <div class="fi fi--full">
              <label class="fi-lbl">Provider</label>
              <div class="pills">
                <button v-for="p in providers" :key="p.key" class="pill" :class="{ active: configStore.wizardData.default_llm.provider === p.key }" @click="selectProvider('default_llm', p.key)" type="button">{{ p.label }}</button>
              </div>
            </div>
          </div>
          <div class="sec-row sec-row--model">
            <div class="fi fi--model zen-field">
              <label class="fi-lbl">Model</label>
              <ModelSelector :presets="configStore.llmPresets" :model-value="configStore.wizardData.default_llm.model_name" :provider="configStore.wizardData.default_llm.provider" @update:model-value="onBrainModelChange" @update:provider="onBrainProviderChange" @update:url="onBrainUrlChange" />
            </div>
            <div class="fi">
              <label class="fi-lbl">API Key</label>
              <div class="pw-wrap">
                <input v-model="configStore.wizardData.default_llm.api_key" :type="showBrainKey ? 'text' : 'password'" class="fi-inp mono" placeholder="sk-..." spellcheck="false" />
                <button class="eye-btn" @click="showBrainKey = !showBrainKey" type="button">
                  <MIcon :name="showBrainKey ? 'eye-off' : 'eye'" :size="14" />
                </button>
              </div>
            </div>
            <div class="fi">
              <label class="fi-lbl">Endpoint URL</label>
              <input v-model="configStore.wizardData.default_llm.url" class="fi-inp mono" type="text" placeholder="https://api.example.com/v1" spellcheck="false" />
            </div>
          </div>
        </div>
      </section>

      <!-- Section 3: Cerebellum -->
      <section class="sec">
        <div class="sec-side">
          <div class="sec-icon"><MIcon name="bolt" :size="16" /></div>
          <div class="sec-text">
            <div class="sec-title">小脑模型</div>
            <div class="sec-desc">Cerebellum 处理内部轻量操作，可以用更便宜的模型。默认与大脑相同。</div>
          </div>
        </div>
        <div class="sec-main">
          <!-- Toggle -->
          <div class="slm-toggle-row">
            <label class="toggle" @click.prevent="slmSameAsBrain = !slmSameAsBrain">
              <span class="toggle-box" :class="{ on: slmSameAsBrain }">
                <MIcon v-if="slmSameAsBrain" name="check" :size="10" />
              </span>
              <span class="toggle-text">Same as Brain</span>
            </label>
            <span v-if="slmSameAsBrain" class="slm-using">
              将使用大脑模型: <span class="slm-model">{{ configStore.wizardData.default_llm.model_name || '—' }}</span>
            </span>
          </div>

          <!-- Expanded SLM fields -->
          <template v-if="!slmSameAsBrain">
            <div class="sec-row">
              <div class="fi fi--full">
                <label class="fi-lbl">Provider</label>
                <div class="pills">
                  <button v-for="p in providers" :key="p.key" class="pill" :class="{ active: configStore.wizardData.default_slm.provider === p.key }" @click="selectProvider('default_slm', p.key)" type="button">{{ p.label }}</button>
                </div>
              </div>
            </div>
            <div class="sec-row">
              <div class="fi zen-field">
                <label class="fi-lbl">Model</label>
                <ModelSelector :presets="configStore.llmPresets" :model-value="configStore.wizardData.default_slm.model_name" :provider="configStore.wizardData.default_slm.provider" @update:model-value="onSlmModelChange" @update:provider="onSlmProviderChange" @update:url="onSlmUrlChange" />
              </div>
              <div class="fi">
                <label class="fi-lbl">API Key</label>
                <div class="pw-wrap">
                  <input v-model="configStore.wizardData.default_slm.api_key" :type="showSlmKey ? 'text' : 'password'" class="fi-inp mono" placeholder="sk-..." spellcheck="false" />
                  <button class="eye-btn" @click="showSlmKey = !showSlmKey" type="button">
                    <MIcon :name="showSlmKey ? 'eye-off' : 'eye'" :size="14" />
                  </button>
                </div>
              </div>
              <div class="fi">
                <label class="fi-lbl">Endpoint URL</label>
                <input v-model="configStore.wizardData.default_slm.url" class="fi-inp mono" type="text" placeholder="https://api.example.com/v1" spellcheck="false" />
              </div>
            </div>
          </template>
        </div>
      </section>

      <!-- Error -->
      <div v-if="configStore.submitError" :class="['err', { 'err--info': configStore.submitError === 'PODMAN_INSTALL_REQUIRED' }]" @click="clearError" title="Click to dismiss">
        <template v-if="configStore.submitError === 'PODMAN_INSTALL_REQUIRED'">Podman installer launched. Complete installation, then retry.</template>
        <template v-else>{{ configStore.submitError }}</template>
      </div>

      <!-- Submit -->
      <button class="submit" :disabled="!isFormValid || configStore.isSubmitting" @click="handleSubmit">
        <span v-if="configStore.isSubmitting" class="submit-spin"></span>
        <MIcon v-else name="rocket" :size="16" />
        {{ configStore.isSubmitting ? 'Initializing...' : 'Launch AgentMatrix' }}
      </button>
    </div>

    <!-- Loading overlay -->
    <div class="overlay" :class="{ active: configStore.isSubmitting }">
      <div class="overlay-spin"></div>
      <div class="overlay-text">Initializing matrix...</div>
    </div>
  </div>
</template>

<style scoped>
/* ═══════════════════════════════════════
   PAGE
   ═══════════════════════════════════════ */
.wiz {
  width: 100vw;
  height: 100vh;
  display: flex;
  flex-direction: column;
  font-family: var(--font-sans);
  background: var(--surface-base);
}

/* ─── Header ─── */
.wiz-header {
  padding: 24px 48px 20px;
  border-bottom: 2px solid var(--text-primary);
  flex-shrink: 0;
}

.wiz-header-left {
  display: flex;
  align-items: center;
  gap: 14px;
}

.wiz-logo {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  border: 2px solid var(--accent);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
}

.wiz-title {
  font-size: var(--font-xl);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin: 0;
}

.wiz-sub {
  font-size: var(--font-base);  color: var(--text-tertiary);
  margin: 2px 0 0;
}

/* ═══════════════════════════════════════
   BODY — vertical stack of sections
   ═══════════════════════════════════════ */
.wiz-body {
  flex: 1;
  padding: 0 48px 32px;
  display: flex;
  flex-direction: column;
}

/* ═══════════════════════════════════════
   SECTION — left title + right fields
   ═══════════════════════════════════════ */
.sec {
  display: grid;
  grid-template-columns: 220px 1fr;
  border-bottom: 1px solid var(--border);
  padding: 24px 48px;
  margin-left: -48px;
  margin-right: -48px;
}

.sec:nth-child(2) {
  background: var(--surface-secondary);
}

.sec:last-of-type {
  border-bottom: none;
}

/* ─── Left side: icon + title + description ─── */
.sec-side {
  display: flex;
  gap: 12px;
  padding-right: 28px;
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

.sec-text {
  padding-top: 2px;
}

.sec-title {
  font-size: var(--font-base);
  font-weight: var(--font-bold);
  color: var(--text-primary);
  margin-bottom: 6px;
}

.sec-desc {
  font-size: var(--font-sm);
  color: var(--text-secondary);
  line-height: var(--leading-relaxed);
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

.sec-row--model {
  grid-template-columns: 3fr 4fr 4fr;
}

.fi--model {
  max-width: 280px;
}

/* ═══════════════════════════════════════
   FIELDS
   ═══════════════════════════════════════ */
.fi {
  display: flex;
  flex-direction: column;
  gap: 5px;
}

.fi--full {
  grid-column: 1 / -1;
}

.fi--grow {
  flex: 1;
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

/* ─── Directory ─── */
.dir-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  background: var(--surface-secondary);
  border: 1.5px solid #B0B0B4;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.dir-row:hover {
  border-color: var(--accent);
  background: var(--surface-base);
  box-shadow: 0 0 0 3px var(--accent-muted);
}

.dir-path {
  flex: 1;
  font-family: var(--font-mono);
  font-size: var(--font-sm);
  color: var(--text-quaternary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dir-path.has { color: var(--text-primary); }

.dir-btn {
  font-size: var(--font-xs);
  font-weight: var(--font-bold);
  color: var(--accent);
  letter-spacing: 0.06em;
  text-transform: uppercase;
  flex-shrink: 0;
}

/* ─── Provider Pills ─── */
.pills {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.pill {
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: var(--font-sm);
  font-weight: var(--font-medium);
  background: var(--surface-secondary);
  color: var(--text-secondary);
  border: 1px solid var(--border);
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
}

.pill:hover {
  border-color: var(--accent);
  color: var(--accent);
}

.pill.active {
  background: var(--accent);
  color: #fff;
  border-color: var(--accent);
}

/* ─── Password ─── */
.pw-wrap {
  position: relative;
  width: 100%;
}

.pw-wrap .fi-inp {
  width: 100%;
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

/* ═══════════════════════════════════════
   CEREBELLUM TOGGLE
   ═══════════════════════════════════════ */
.slm-toggle-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 8px 0;
}

.toggle {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  user-select: none;
}

.toggle-box {
  width: 16px;
  height: 16px;
  border-radius: 3px;
  border: 1.5px solid #B0B0B4;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all var(--duration-base) var(--ease-out);
  color: transparent;
}

.toggle-box.on {
  background: var(--accent);
  border-color: var(--accent);
  color: #fff;
}

.toggle-text {
  font-size: var(--font-base);
  color: var(--text-primary);
  font-weight: var(--font-medium);
}

.slm-using {
  font-size: var(--font-sm);
  color: var(--text-secondary);
}

.slm-model {
  font-family: var(--font-mono);
  font-weight: var(--font-medium);
  color: var(--text-primary);
}

/* ═══════════════════════════════════════
   SUBMIT
   ═══════════════════════════════════════ */
.submit {
  margin-top: auto;
  padding: 12px 0;
  width: 100%;
  background: var(--text-primary);
  color: var(--surface-base);
  border: none;
  border-radius: var(--radius-sm);
  font-family: var(--font-sans);
  font-size: var(--font-base);
  font-weight: var(--font-bold);
  letter-spacing: 0.04em;
  cursor: pointer;
  transition: all var(--duration-base) var(--ease-out);
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.submit:hover:not(:disabled) { background: var(--accent); }
.submit:disabled { background: var(--surface-hover); color: var(--text-tertiary); border: 1.5px solid var(--border-strong); cursor: not-allowed; }

.submit-spin {
  width: 12px; height: 12px;
  border: 2px solid currentColor; border-top-color: transparent;
  border-radius: 50%; animation: spin 1s linear infinite;
}

/* ═══════════════════════════════════════
   ERROR
   ═══════════════════════════════════════ */
.err {
  padding: 10px 14px;
  background: var(--error-muted);
  color: var(--error);
  font-size: var(--font-xs);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--error);
  margin-top: 8px;
  cursor: pointer;
}

.err--info {
  background: var(--success-muted);
  color: var(--success);
  border-left-color: var(--success);
}

/* ═══════════════════════════════════════
   LOADING OVERLAY
   ═══════════════════════════════════════ */
.overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(255,255,255,0.92);
  display: flex; flex-direction: column;
  align-items: center; justify-content: center; gap: var(--spacing-4);
  opacity: 0; pointer-events: none;
  transition: opacity var(--duration-slower) var(--ease-out);
}

.overlay.active { opacity: 1; pointer-events: all; }

.overlay-spin {
  width: 28px; height: 28px;
  border: 2px solid var(--border); border-top-color: var(--accent);
  border-radius: 50%; animation: spin 1s linear infinite;
}

.overlay-text {
  font-size: var(--font-xs);
  color: var(--text-tertiary);
  letter-spacing: 0.06em;
}

@keyframes spin { to { transform: rotate(360deg); } }

/* ═══════════════════════════════════════
   ModelSelector overrides
   ═══════════════════════════════════════ */
.zen-field :deep(.ms) { max-width: none; margin: 0; }
.zen-field :deep(.ms-input-wrap) { position: relative; }

.zen-field :deep(.ms-input) {
  font-family: var(--font-mono);
  font-size: var(--font-sm);
  text-align: left;
  padding: 8px 40px 8px 12px;
  background: var(--surface-secondary);
  border: 1.5px solid #B0B0B4;
  border-radius: var(--radius-sm);
}

.zen-field :deep(.ms-input::placeholder) { font-size: var(--font-sm); color: var(--text-quaternary); }

.zen-field :deep(.ms-input:focus) {
  border-color: var(--accent);
  border-width: 3px;
  padding: 7px 39px 7px 11px;
  background: var(--surface-base);
  box-shadow: 0 0 0 3px var(--accent-muted);
  outline: none;
}

.zen-field :deep(.ms-dropdown) { left: 0; transform: none; }
.zen-field :deep(.ms-option-model) { font-size: var(--font-sm); }
.zen-field :deep(.ms-new),
.zen-field :deep(.ms-provider) { font-size: var(--font-xs); }
</style>
