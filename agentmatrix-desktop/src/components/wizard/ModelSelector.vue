<script setup>
import { ref, computed, watch } from 'vue'

const props = defineProps({
  presets: { type: Object, required: true },
  modelValue: { type: String, default: '' },
  provider: { type: String, default: '' },
})

const emit = defineEmits(['update:modelValue', 'update:provider', 'update:url', 'state-change'])

const query = ref(props.modelValue)
const focused = ref(false)
const hoveredIdx = ref(-1)

// Flatten all models from presets into a searchable list
const allModels = computed(() => {
  const list = []
  for (const [key, preset] of Object.entries(props.presets)) {
    if (key === 'custom') continue
    for (const model of (preset.models || [])) {
      list.push({ model, provider: key, url: preset.url, label: preset.label })
    }
  }
  return list
})

// Filter models by query
const filtered = computed(() => {
  if (!query.value.trim()) return allModels.value
  const q = query.value.toLowerCase().trim()
  return allModels.value.filter(m => m.model.toLowerCase().includes(q))
})

// Is the current query an exact match to a known model?
const exactMatch = computed(() =>
  allModels.value.find(m => m.model.toLowerCase() === query.value.trim().toLowerCase())
)

// Detect provider from pattern matching
function detectProvider(name) {
  const lower = name.toLowerCase().trim()
  for (const [key, preset] of Object.entries(props.presets)) {
    if (key === 'custom') continue
    for (const p of (preset.patterns || [])) {
      if (lower.startsWith(p)) {
        return { provider: key, url: preset.url, label: preset.label }
      }
    }
  }
  return { provider: 'custom', url: '', label: 'Custom' }
}

// Current state for parent
const currentState = computed(() => {
  const val = query.value.trim()
  if (!val) return { model: '', provider: '', url: '', state: 'empty' }
  if (exactMatch.value) {
    return { model: val, provider: exactMatch.value.provider, url: exactMatch.value.url, state: 'known' }
  }
  const detected = detectProvider(val)
  return { model: val, provider: detected.provider, url: detected.url, state: 'new' }
})

// Watch for state changes and emit
watch(currentState, (s) => {
  emit('update:modelValue', s.model)
  emit('update:provider', s.provider)
  emit('update:url', s.url)
  emit('state-change', s.state)
}, { immediate: true })

function select(item) {
  query.value = item.model
  focused.value = false
  hoveredIdx.value = -1
}

function onInput(e) {
  query.value = e.target.value
  hoveredIdx.value = -1
}

function onFocus() {
  focused.value = true
}

function onBlur() {
  // Delay to allow click on dropdown item
  setTimeout(() => { focused.value = false; hoveredIdx.value = -1 }, 150)
}

function onKeydown(e) {
  if (e.key === 'ArrowDown') {
    e.preventDefault()
    hoveredIdx.value = Math.min(hoveredIdx.value + 1, filtered.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    hoveredIdx.value = Math.max(hoveredIdx.value - 1, 0)
  } else if (e.key === 'Enter' && hoveredIdx.value >= 0 && focused.value) {
    e.preventDefault()
    select(filtered.value[hoveredIdx.value])
  } else if (e.key === 'Escape') {
    focused.value = false
    hoveredIdx.value = -1
  }
}

// Watch for presets changes to handle async loading
watch(() => props.presets, () => {
  // Trigger re-computation of allModels when presets are loaded
  // This ensures dropdown shows models when presets become available
}, { immediate: true, deep: true })

// Sync from parent
watch(() => props.modelValue, (v) => {
  if (v !== query.value) query.value = v
})
</script>

<template>
  <div class="ms">
    <div class="ms-input-wrap">
      <input
        class="ms-input"
        type="text"
        :value="query"
        placeholder="model name"
        autocomplete="off"
        spellcheck="false"
        @input="onInput"
        @focus="onFocus"
        @blur="onBlur"
        @keydown="onKeydown"
      />
      <!-- State indicator -->
      <span v-if="query.trim() && !exactMatch" class="ms-new">new</span>
      <span v-else-if="exactMatch" class="ms-provider">{{ exactMatch.label }}</span>
    </div>

    <!-- Dropdown -->
    <div v-if="focused && filtered.length > 0" class="ms-dropdown">
      <div
        v-for="(item, idx) in filtered"
        :key="item.model"
        class="ms-option"
        :class="{ hover: idx === hoveredIdx }"
        @mousedown.prevent="select(item)"
        @mouseenter="hoveredIdx = idx"
      >
        <span class="ms-option-model">{{ item.model }}</span>
        <span class="ms-option-provider">{{ item.label }}</span>
      </div>
    </div>

    <!-- No match hint -->
    <div v-if="focused && filtered.length === 0 && query.trim()" class="ms-dropdown ms-dropdown--empty">
      <div class="ms-empty-text">
        <template v-if="currentState.provider !== 'custom'">
          new model · {{ currentState.provider }}
        </template>
        <template v-else>
          new model · enter url below
        </template>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ms {
  position: relative;
  max-width: 480px;
  margin: 0 auto;
}

.ms-input-wrap {
  position: relative;
}

.ms-input {
  display: block;
  width: 100%;
  background: transparent;
  border: none;
  border-bottom: 2px solid var(--border);
  color: var(--text-primary);
  font-family: var(--font-mono);
  font-size: 24px;
  padding: 12px 60px 12px 0;
  outline: none;
  text-align: center;
  transition: border-color 0.3s;
  caret-color: var(--accent);
}

.ms-input::placeholder {
  color: var(--text-quaternary);
  font-size: 18px;
}

.ms-input:focus {
  border-bottom-color: var(--accent);
}

.ms-new,
.ms-provider {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  font-size: 10px;
  font-weight: 600;
  padding: 2px 6px;
  border-radius: var(--radius-sm);
}

.ms-new {
  color: var(--amber);
  background: var(--amber-dim);
}

.ms-provider {
  color: var(--success);
  background: rgba(45, 106, 79, 0.08);
}

.ms-dropdown {
  position: absolute;
  top: calc(100% + 4px);
  left: 50%;
  transform: translateX(-50%);
  width: 100%;
  max-height: 200px;
  overflow-y: auto;
  background: var(--surface-base);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  z-index: 50;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.ms-dropdown--empty {
  max-height: none;
  overflow: hidden;
}

.ms-option {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.1s;
}

.ms-option:hover,
.ms-option.hover {
  background: var(--surface-hover);
}

.ms-option-model {
  font-size: 16px;
  color: var(--text-primary);
}

.ms-option-provider {
  font-size: 11px;
  color: var(--text-quaternary);
  font-weight: 600;
}

.ms-empty-text {
  padding: 12px 14px;
  font-size: 13px;
  color: var(--text-quaternary);
  text-align: center;
}
</style>