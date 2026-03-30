<script setup>
import { ref, computed, onMounted, nextTick, onUnmounted, watch } from 'vue'
import { useConfigStore } from '@/stores/config'
import StepUserName from './steps/StepUserName.vue'
import StepDirectory from './steps/StepDirectory.vue'
import StepLLM from './steps/StepLLM.vue'
import HelpQuestion from './HelpQuestion.vue'

const emit = defineEmits(['complete'])
const configStore = useConfigStore()

const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789αβγδε∂∑∫√∞ΔΩ@#%&'.split('')
const glitchText = ref(null)
const rainCanvas = ref(null)
const currentStep = ref(0)
const errors = ref({})
const cerebellumPrefilled = ref(false)
const isExiting = ref(null)
let rainInterval = null

// ─── Rain ───
function initRain() {
  const cv = document.querySelector('.me-rain')
  if (!cv) return
  const cx = cv.getContext('2d')
  cv.width = window.innerWidth
  cv.height = window.innerHeight
  const fs = 15
  const colCount = Math.floor(cv.width / fs)
  const drops = Array.from({ length: colCount }, () => Math.random() * -60)
  const speeds = Array.from({ length: colCount }, () => .2 + Math.random() * .4)
  function draw() {
    cx.fillStyle = 'rgba(253,252,249,0.06)'
    cx.fillRect(0, 0, cv.width, cv.height)
    cx.font = fs + 'px "JetBrains Mono",monospace'
    for (let i = 0; i < colCount; i++) {
      const c = CHARS[Math.random() * CHARS.length | 0]
      const x = i * fs
      const y = drops[i] * fs
      const isLead = Math.random() > .9
      if (isLead) {
        cx.fillStyle = 'rgba(212,168,67,0.7)'
        cx.shadowColor = 'rgba(212,168,67,0.3)'
        cx.shadowBlur = 6
      } else {
        const r = 180 + Math.random() * 40
        const g = 140 + Math.random() * 40
        const b = 40 + Math.random() * 20
        cx.fillStyle = 'rgba(' + r + ',' + g + ',' + b + ',0.15)'
        cx.shadowColor = 'transparent'
        cx.shadowBlur = 0
      }
      cx.fillText(c, x, y)
      drops[i] += speeds[i]
      if (drops[i] * fs > cv.height && Math.random() > .96) {
        drops[i] = 0
        speeds[i] = .2 + Math.random() * .4
      }
    }
    cx.shadowBlur = 0
  }
  rainInterval = setInterval(draw, 50)
}

// ─── Typewriter ───
function typewriterReveal(text, targetEl) {
  if (!targetEl) return
  targetEl.textContent = ''
  targetEl.setAttribute('data-text', text)
  const spans = []
  text.split('').forEach(c => {
    const span = document.createElement('span')
    span.className = 'crt-char'
    span.setAttribute('data-char', c)
    span.style.opacity = '0'
    span.textContent = c
    targetEl.appendChild(span)
    spans.push(span)
  })
  let idx = 0
  const timer = setInterval(() => {
    if (idx >= spans.length) {
      clearInterval(timer)
      targetEl.classList.add('done')
      return
    }
    const pos = idx
    const char = text[pos]
    spans[pos].textContent = CHARS[Math.random() * CHARS.length | 0]
    spans[pos].setAttribute('data-char', spans[pos].textContent)
    spans[pos].style.opacity = '1'
    setTimeout(() => {
      spans[pos].textContent = char
      spans[pos].setAttribute('data-char', char)
    }, 90)
    idx++
  }, 80)
}

// ─── Steps ───
const STEPS = [
  { id: 'welcome', fields: [] },
  { id: 'name', fields: ['name'] },
  { id: 'dir', fields: ['dir'] },
  { id: 'brain', fields: ['brain-model', 'brain-key'] },
  { id: 'cerebellum', fields: ['cerebellum-model', 'cerebellum-key'] },
  { id: 'init', fields: [] },
]

// ─── Validation ───
function isStepValid(idx) {
  switch (idx) {
    case 0: return true
    case 1: return configStore.wizardData.user_name.trim().length > 0
    case 2: return configStore.wizardData.matrix_world_path.trim().length > 0
    case 3: {
      const llm = configStore.wizardData.default_llm
      return llm.model_name && llm.api_key && llm.url
    }
    case 4: {
      const slm = configStore.wizardData.default_slm
      return slm.model_name && slm.api_key && slm.url
    }
    case 5: return isStepValid(1) && isStepValid(2) && isStepValid(3) && isStepValid(4)
    default: return false
  }
}

function showError(key) {
  errors.value[key] = true
  setTimeout(() => { delete errors.value[key] }, 800)
}

// ─── Navigation ───
function goBack() {
  if (currentStep.value > 0) currentStep.value--
}

async function advance() {
  if (currentStep.value >= STEPS.length - 1) return

  // Pre-fill Cerebellum from Brain when first entering step 4
  if (currentStep.value === 3 && !cerebellumPrefilled.value) {
    configStore.wizardData.default_slm = { ...configStore.wizardData.default_llm }
    cerebellumPrefilled.value = true
  }

  if (!isStepValid(currentStep.value)) {
    // Shake and show errors
    const el = document.querySelector('.me-step--active')
    if (el) {
      el.classList.remove('me-shake')
      void el.offsetWidth
      el.classList.add('me-shake')
      setTimeout(() => el.classList.remove('me-shake'), 500)
    }
    // Show errors on empty fields
    const step = STEPS[currentStep.value]
    step.fields.forEach(f => {
      const val = getFieldValue(f)
      if (!val) showError(`${currentStep.value}.${f}`)
    })
    return
  }

  // Neon sign transition for Brain (step 3) -> Cerebellum (step 4)
  if (currentStep.value === 3) {
    isExiting.value = 3
    await new Promise(r => setTimeout(r, 400))
    isExiting.value = null
    currentStep.value++
    nextTick(() => {
      const stepEl = document.querySelector('.me-step--active')
      if (stepEl) {
        const inp = stepEl.querySelector('input:not([type=checkbox])')
        if (inp) inp.focus()
      }
    })
    return
  }

  // Neon sign transition for Cerebellum (step 4) -> Initialize (step 5)
  if (currentStep.value === 4) {
    isExiting.value = 4
    await new Promise(r => setTimeout(r, 400))
    isExiting.value = null
    currentStep.value++
    nextTick(() => {
      const stepEl = document.querySelector('.me-step--active')
      if (stepEl) {
        const inp = stepEl.querySelector('input:not([type=checkbox])')
        if (inp) inp.focus()
      }
    })
    return
  }

  currentStep.value++

  // Auto-focus first input in the new step
  nextTick(() => {
    const stepEl = document.querySelector('.me-step--active')
    if (stepEl) {
      const inp = stepEl.querySelector('input:not([type=checkbox])')
      if (inp) inp.focus()
    }
  })
}

function getFieldValue(fieldId) {
  switch (fieldId) {
    case 'name': return configStore.wizardData.user_name.trim()
    case 'dir': return configStore.wizardData.matrix_world_path.trim()
    case 'brain-model': return configStore.wizardData.default_llm.model_name.trim()
    case 'brain-key': return configStore.wizardData.default_llm.api_key.trim()
    case 'cerebellum-model': return configStore.wizardData.default_slm.model_name.trim()
    case 'cerebellum-key': return configStore.wizardData.default_slm.api_key.trim()
    default: return ''
  }
}

// Track IME composition state
let isComposing = false

function onCompositionStart() {
  isComposing = true
}

function onCompositionEnd() {
  isComposing = false
}

// Enter key: advance field or step
// Escape key: go back
function onKeydown(e) {
  if (e.key === 'Escape') {
    e.preventDefault()
    goBack()
    return
  }
  if (e.key !== 'Enter') return
  // Ignore Enter during IME composition (e.g., Chinese input)
  if (e.isComposing || isComposing) return
  e.preventDefault()

  // Find next focusable input in current step
  const stepEl = document.querySelector('.me-step--active')
  if (stepEl) {
    const inputs = [...stepEl.querySelectorAll('input:not([type=checkbox]):not([type=password]),input[type=password],select')]
    const focused = document.activeElement
    const idx = inputs.indexOf(focused)
    if (idx >= 0 && idx < inputs.length - 1) {
      // Focus next field
      inputs[idx + 1].focus()
      return
    }
  }

  // No next field or not focused on input → advance step
  advance()
}

// Click anywhere = advance
function onClickStep(e) {
  // Don't advance if clicking on interactive elements
  if (e.target.closest('input,select,button,a,.ms,.me-pw,.me-eye,.ms-dropdown,.help-question,.help-question__mark')) return
  advance()
}

// ─── Submit ───
async function handleSubmit() {
  try {
    await configStore.submitWizard()
    emit('complete')
  } catch (error) { /* handled in store */ }
}

// ─── Init ───
onMounted(async () => {
  await configStore.loadPresets()
  document.addEventListener('keydown', onKeydown)
  document.addEventListener('compositionstart', onCompositionStart)
  document.addEventListener('compositionend', onCompositionEnd)
  initRain()
  typewriterReveal('Welcome to the Matrix', document.querySelector('.me-glitch'))
  setTimeout(() => advance(), 4200)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  document.removeEventListener('compositionstart', onCompositionStart)
  document.removeEventListener('compositionend', onCompositionEnd)
  if (rainInterval) clearInterval(rainInterval)
})
</script>

<template>
  <div class="me" @click="onClickStep">
    <canvas ref="rainCanvas" class="me-rain"></canvas>
    <div class="me-progress" :style="{ width: `${(currentStep / (STEPS.length - 1)) * 100}%` }"></div>

    <!-- Back indicator -->
    <div v-if="currentStep > 0 && currentStep < STEPS.length - 1" class="me-back" @click.stop="goBack()">
      &#x2190;
    </div>

    <!-- STEP 0: Welcome -->
    <div class="me-step" :class="{ 'me-step--active': currentStep === 0 }" v-show="currentStep === 0">
      <div class="step-inner visible">
        <div class="me-title me-title--welcome"><span class="me-glitch" ref="glitchText"></span></div>
      </div>
    </div>

    <!-- STEP 1: Name -->
    <div class="me-step" :class="{ 'me-step--active': currentStep === 1 }" v-show="currentStep === 1">
      <div class="step-inner visible">
        <div class="me-label">// identify yourself</div>
        <input
          v-model="configStore.wizardData.user_name"
          class="me-inp"
          :class="{ done: configStore.wizardData.user_name.trim(), 'me-error': errors['1.name'] }"
          type="text"
          placeholder="your name"
          autofocus
          autocomplete="off"
          spellcheck="false"
        />
      </div>
    </div>

    <!-- STEP 2: Directory -->
    <div class="me-step" :class="{ 'me-step--active': currentStep === 2 }" v-show="currentStep === 2">
      <div class="step-inner visible">
        <div class="me-label">// workspace</div>
        <div class="me-dir" :class="{ 'me-error': errors['2.dir'] }" @click.stop="configStore.selectDirectory()">
          <span class="me-dir-path" :class="{ has: configStore.wizardData.matrix_world_path }">
            {{ configStore.wizardData.matrix_world_path || 'select workspace directory' }}
          </span>
          <span class="me-dir-browse">browse</span>
        </div>
      </div>
    </div>

    <!-- STEP 3: Brain -->
    <div class="me-step" :class="{ 'me-step--active': currentStep === 3, 'me-step--exiting': isExiting === 3 }" v-show="currentStep === 3 || isExiting === 3">
      <div class="step-inner visible">
        <div class="neon-sign" :class="{ 'neon-on': currentStep === 3 && !isExiting, 'neon-off': isExiting === 3 }">
          <svg class="neon-frame" viewBox="0 0 200 50" preserveAspectRatio="xMidYMid meet">
            <rect x="2" y="2" width="196" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="2" 
                  class="neon-border" pathLength="1"/>
          </svg>
          <span class="neon-text">BRAIN</span>
        </div>
        <StepLLM which="llm" :errors="errors" step-idx="3" />
      </div>
    </div>

    <!-- Help Question for Brain -->
    <Teleport to="body">
      <HelpQuestion v-if="currentStep === 3" type="brain" />
    </Teleport>

    <!-- STEP 4: Cerebellum -->
    <div class="me-step" :class="{ 'me-step--active': currentStep === 4, 'me-step--exiting': isExiting === 4 }" v-show="currentStep === 4 || isExiting === 4">
      <div class="step-inner visible">
        <div class="neon-sign" :class="{ 'neon-on': currentStep === 4 && !isExiting, 'neon-off': isExiting === 4 }">
          <svg class="neon-frame" viewBox="0 0 200 50" preserveAspectRatio="xMidYMid meet">
            <rect x="2" y="2" width="196" height="46" rx="4" fill="none" stroke="currentColor" stroke-width="2" 
                  class="neon-border" pathLength="1"/>
          </svg>
          <span class="neon-text">CEREBELLUM</span>
        </div>
        <StepLLM which="slm" :errors="errors" step-idx="4" />
      </div>
    </div>

    <!-- Help Question for Cerebellum -->
    <Teleport to="body">
      <HelpQuestion v-if="currentStep === 4" type="cerebellum" />
    </Teleport>

    <!-- STEP 5: Initialize -->
    <div class="me-step" :class="{ 'me-step--active': currentStep === 5 }" v-show="currentStep === 5">
      <div class="step-inner visible">
        <button
          class="me-start-btn"
          :disabled="!isStepValid(5) || configStore.isSubmitting"
          @click.stop="handleSubmit"
        >
          <span v-if="configStore.isSubmitting" class="me-btn-spin"></span>
          {{ configStore.isSubmitting ? 'Initializing...' : 'Initialize Matrix' }}
        </button>
        <div class="me-summary" v-if="isStepValid(1) && isStepValid(2) && isStepValid(3)">
          {{ configStore.wizardData.user_name }} // {{ configStore.wizardData.default_llm.model_name }} / {{ configStore.wizardData.default_slm.model_name }}
        </div>
        <div v-if="configStore.submitError" class="me-error-msg">{{ configStore.submitError }}</div>
      </div>
    </div>

    <!-- Hint -->
    <div class="me-hint" v-if="currentStep > 0 && currentStep < STEPS.length - 1">
      press enter to continue
    </div>

    <!-- Submit overlay -->
    <div class="me-overlay" :class="{ active: configStore.isSubmitting }">
      <div class="me-overlay-spin"></div>
      <div class="me-overlay-text">initializing matrix...</div>
    </div>
  </div>
</template>

<style scoped>
.me {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: var(--parchment-50);
  position: relative;
  cursor: default;
}

.me-rain {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  z-index: 0;
  pointer-events: none;
  display: block;
}

.me-progress {
  position: fixed;
  top: 0;
  left: 0;
  height: 2px;
  background: var(--vermillion);
  z-index: 10;
  transition: width 0.5s ease;
}

.me-step {
  position: fixed;
  inset: 0;
  z-index: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 40px;
  cursor: pointer;
}

.step-inner {
  max-width: 520px;
  width: 100%;
  text-align: center;
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.6s ease, transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
  pointer-events: none;
  position: relative;
}

.step-inner.visible {
  opacity: 1;
  transform: translateY(0);
  pointer-events: all;
}

.me-title {
  font-size: 52px;
  font-weight: 700;
  color: var(--ink-900);
  line-height: 1.2;
  letter-spacing: -0.5px;
  margin-bottom: 32px;
}

.me-title--welcome {
  font-size: 60px;
  margin-bottom: 0;
  cursor: pointer;
  position: relative;
  display: inline-block;
  color: var(--ink-900);
}

/* CRT effect container - like question mark structure */
.me-title--welcome {
  position: relative;
  display: inline-block;
  z-index: 1;
}

/* 1. Scanlines overlay - chunky low-res CRT feel */
.me-title--welcome::after {
  content: '';
  position: absolute;
  inset: -20% -10%;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 3px,
    rgba(253, 252, 249, 0.35) 3px,
    rgba(253, 252, 249, 0.35) 7px
  );
  pointer-events: none;
  z-index: 2;
  opacity: 0.9;
}

/* Single character effect - each letter is its own CRT component */
:deep(.crt-char) {
  position: relative;
  display: inline-block;
  color: #5C1800 !important;
  user-select: none;
  white-space: pre;  /* Preserve spaces */
  
  /* Vertical striping - on the text itself */
  background: repeating-linear-gradient(
    90deg,
    transparent,
    transparent 1px,
    rgba(194, 59, 34, 0.2) 1px,
    rgba(194, 59, 34, 0.2) 2px
  ) !important;
  -webkit-background-clip: text !important;
  background-clip: text !important;
  
  /* Text glow */
  text-shadow:
    0 0 4px rgba(194, 59, 34, 0.5) !important;
  
  /* CRT flicker */
  animation: crt-flicker 0.12s infinite;
}

/* Space characters need width */
:deep(.crt-char[data-char=" "]) {
  width: 0.5em;
}

/* 2. Per-character glow - each letter has its own circular glow (like question mark __glow) */
:deep(.crt-char)::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 140%;
  height: 140%;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(194, 59, 34, 0.15) 0%,
    rgba(194, 59, 34, 0.08) 40%,
    transparent 70%
  );
  pointer-events: none;
  animation: glow-pulse 2.5s ease-in-out infinite;
  z-index: -1;
}

/* No phosphor afterglow - keep text sharp */

@keyframes glow-pulse {
  0%, 100% { opacity: 0.5; transform: translate(-50%, -50%) scale(1); }
  50% { opacity: 0.8; transform: translate(-50%, -50%) scale(1.15); }
}

@keyframes crt-flicker {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.97; }
}


/* Keep only the glitch animations */
@keyframes me-g1 {
  0%,100%{transform:translate(0)}20%{transform:translate(-1px,1px)}40%{transform:translate(1px,-1px)}60%{transform:translate(-1px,0)}80%{transform:translate(1px,0)}
}

@keyframes me-g2 {
  0%,100%{transform:translate(0)}25%{transform:translate(1px,-1px)}50%{transform:translate(-1px,1px)}75%{transform:translate(1px,0)}
}

.me-label {
  font-size: 20px;
  color: var(--amber);
  letter-spacing: 0.3em;
  text-transform: uppercase;
  margin-bottom: 28px;
  font-weight: 600;
}

/* Neon sign effect for Brain/Cerebellum titles */
.neon-sign {
  position: relative;
  display: inline-block;
  margin-bottom: 48px;
  color: var(--accent);
  opacity: 0;
}

.neon-sign.neon-on {
  animation: neon-appear 1.2s ease forwards;
}\n
.neon-sign.neon-off {
  animation: neon-disappear 0.4s ease forwards;
}

@keyframes neon-appear {
  0% { opacity: 0; }
  100% { opacity: 1; }
}

@keyframes neon-disappear {
  0% { opacity: 1; }
  50% { opacity: 0.3; }
  100% { opacity: 0; }
}

.neon-frame {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 220px;
  height: 60px;
  overflow: visible;
}

.neon-border {
  stroke: var(--accent);
  stroke-dasharray: 1;
  stroke-dashoffset: 1;
}

.neon-on .neon-border {
  animation: neon-border-light 1.2s ease forwards;
}

@keyframes neon-border-light {
  0% { stroke-dashoffset: 1; }
  100% { stroke-dashoffset: 0; }
}

.neon-text {
  position: relative;
  display: inline-block;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: 0.2em;
  padding: 16px 48px;
  color: var(--accent);
  opacity: 0;
}

.neon-on .neon-text {
  animation: neon-text-flicker 0.8s ease 0.6s forwards;
}

@keyframes neon-text-flicker {
  0%, 100% { opacity: 0; }
  20% { opacity: 1; }
  40% { opacity: 0.5; }
  60% { opacity: 1; }
  80% { opacity: 0.7; }
  100% { opacity: 1; }
}

.neon-off .neon-text,
.neon-off .neon-border {
  animation: neon-flicker-off 0.3s ease forwards;
}

@keyframes neon-flicker-off {
  0%, 100% { opacity: 1; }
  25% { opacity: 0.3; }
  50% { opacity: 1; }
  75% { opacity: 0.2; }
  100% { opacity: 0; }
}

/* Input */
.me-inp {
  display: block;
  width: 100%;
  max-width: 480px;
  margin: 0 auto;
  background: transparent;
  border: none;
  border-bottom: 2px solid var(--parchment-300);
  color: var(--ink-900);
  font-family: var(--font-mono);
  font-size: 44px;
  padding: 14px 0;
  outline: none;
  text-align: center;
  transition: border-color 0.3s;
  caret-color: var(--vermillion);
  cursor: text;
}

.me-inp::placeholder {
  color: var(--ink-ghost);
  font-style: normal;
  font-size: 24px;
}

.me-inp:focus {
  border-bottom-color: var(--vermillion);
}

.me-inp.done {
  border-bottom-color: var(--verdant);
}

/* Error state */
.me-inp.me-error,
.me-dir.me-error {
  border-bottom-color: var(--fault) !important;
  animation: me-error-flash 0.4s ease;
}

@keyframes me-error-flash {
  0%, 100% { opacity: 1 }
  50% { opacity: 0.5 }
}

/* Dir picker */
.me-dir {
  max-width: 480px;
  margin: 0 auto;
  display: flex;
  align-items: center;
  gap: 12px;
  border-bottom: 2px solid var(--parchment-300);
  padding: 12px 0;
  cursor: pointer;
  transition: border-color 0.3s;
}

.me-dir:hover {
  border-bottom-color: var(--vermillion);
}

.me-dir-path {
  flex: 1;
  font-family: var(--font-mono);
  font-size: 20px;
  color: var(--ink-ghost);
  text-align: center;
}

.me-dir-path.has {
  color: var(--ink-900);
}

.me-dir-browse {
  font-size: 12px;
  color: var(--amber);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  flex-shrink: 0;
  transition: color 0.2s;
  font-weight: 600;
  animation: me-breathe 2s ease-in-out infinite;
}

@keyframes me-breathe {
  0%, 100% { opacity: 0.5 }
  50% { opacity: 1 }
}

.me-dir:hover .me-dir-browse {
  color: var(--vermillion);
}

/* Same checkbox */
/* Start button */
.me-start-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background-color: #1A1A1A;
  color: #FDFCF9;
  border: none;
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  padding: 16px 52px;
  border-radius: 2px;
  cursor: pointer;
  transition: background-color 0.2s;
  margin-top: 40px;
}

.me-start-btn:hover { background-color: #C23B22; }
.me-start-btn:disabled { opacity: 0.2; cursor: default; }
.me-start-btn:disabled:hover { background-color: #1A1A1A; }

.me-summary {
  font-size: 13px;
  color: var(--ink-ghost);
  margin-top: 20px;
  letter-spacing: 0.05em;
}

.me-error-msg {
  margin-top: 16px;
  padding: 8px 16px;
  background: var(--fault-muted);
  color: var(--fault);
  font-size: 12px;
  border-radius: 2px;
}

/* Back indicator */
.me-back {
  position: fixed;
  top: 20px;
  left: 20px;
  z-index: 5;
  font-size: 20px;
  color: var(--ink-ghost);
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 2px;
  transition: color 0.2s, background 0.2s;
  user-select: none;
}

.me-back:hover {
  color: var(--ink-900);
  background: var(--parchment-200);
}

/* Hint */

.me-hint {
  position: fixed;
  bottom: 28px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 13px;
  color: var(--ink-dim);
  letter-spacing: 0.15em;
  z-index: 2;
  pointer-events: none;
  animation: me-hint-blink 2s ease-in-out infinite;
}

@keyframes me-hint-blink {
  0%, 100% { opacity: 0.4 }
  50% { opacity: 0.9 }
}

/* Overlay */
.me-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: var(--parchment-50);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 20px;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.5s;
}

.me-overlay.active { opacity: 1; pointer-events: all }

.me-overlay-spin {
  width: 32px;
  height: 32px;
  border: 2px solid var(--parchment-300);
  border-top-color: var(--vermillion);
  border-radius: 50%;
  animation: me-spin 1s linear infinite;
}

.me-overlay-text {
  font-size: 14px;
  color: var(--ink-dim);
  letter-spacing: 0.15em;
}

.me-btn-spin {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: me-spin 1s linear infinite;
}

@keyframes me-spin { to { transform: rotate(360deg) } }

/* Shake */
.me-shake {
  animation: me-shake 0.4s ease;
}

@keyframes me-shake {
  0%, 100% { transform: translateX(0) }
  15% { transform: translateX(-8px) }
  30% { transform: translateX(8px) }
  45% { transform: translateX(-6px) }
  60% { transform: translateX(6px) }
  75% { transform: translateX(-3px) }
  90% { transform: translateX(3px) }
}
</style>