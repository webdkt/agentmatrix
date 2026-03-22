<script setup>
import { ref, onMounted, nextTick, onUnmounted } from 'vue'
import { useConfigStore } from '@/stores/config'
import StepUserName from './steps/StepUserName.vue'
import StepDirectory from './steps/StepDirectory.vue'
import StepLLM from './steps/StepLLM.vue'

const emit = defineEmits(['complete'])
const configStore = useConfigStore()

const CHARS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789αβγδε∂∑∫√∞ΔΩ@#%&'.split('')
const stepRefs = ref([])
const currentStep = ref(0)
const glitchText = ref(null)
const rainCanvas = ref(null)
let rainInterval = null

// ─── Rain ───
function initRain() {
  const cv = rainCanvas.value
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

function isStepValid(idx) {
  switch (idx) {
    case 0: return true
    case 1: return configStore.wizardData.user_name.trim().length > 0
    case 2: return configStore.wizardData.matrix_world_path.trim().length > 0
    case 3: {
      const llm = configStore.wizardData.default_llm
      return llm.url && llm.api_key && llm.model_name
    }
    case 4: {
      const slm = configStore.wizardData.default_slm
      return slm.url && slm.api_key && slm.model_name
    }
    case 5: return isStepValid(1) && isStepValid(2) && isStepValid(3) && isStepValid(4)
    default: return false
  }
}

function scrollToStep(idx) {
  const el = stepRefs.value[idx]
  if (!el) return
  el.scrollIntoView({ behavior: 'smooth' })
  currentStep.value = idx
}

function setStepRef(el, idx) {
  if (el) stepRefs.value[idx] = el
}

// ─── Typewriter welcome ───
function typewriterReveal(text, targetEl) {
  if (!targetEl) return
  targetEl.textContent = ''
  const spans = []
  text.split('').forEach(c => {
    const span = document.createElement('span')
    span.style.opacity = '0'
    span.textContent = c
    targetEl.appendChild(span)
    spans.push(span)
  })
  let idx = 0
  const timer = setInterval(() => {
    if (idx >= spans.length) {
      clearInterval(timer)
      targetEl.setAttribute('data-text', text)
      targetEl.classList.add('done')
      return
    }
    const pos = idx
    spans[pos].textContent = CHARS[Math.random() * CHARS.length | 0]
    spans[pos].style.opacity = '1'
    spans[pos].style.textShadow = '0 0 12px rgba(212,168,67,0.5)'
    setTimeout(() => {
      spans[pos].textContent = text[pos]
      spans[pos].style.textShadow = '0 0 4px rgba(212,168,67,0.2)'
    }, 90)
    idx++
  }, 80)
}

// ─── Scroll lock ───
function onScroll() {
  let firstInvalid = -1
  for (let i = 0; i < stepRefs.value.length; i++) {
    if (!isStepValid(i)) { firstInvalid = i; break }
  }
  if (firstInvalid === -1) return
  const el = stepRefs.value[firstInvalid]
  if (!el) return
  if (window.scrollY > el.offsetTop + 50) {
    el.scrollIntoView({ behavior: 'smooth' })
  }
}

// ─── Enter key ───
function onKeydown(e) {
  if (e.key !== 'Enter') return
  const a = document.activeElement
  if (a && a.tagName === 'SELECT') return
  if (a && (a.type === 'password')) return

  for (let i = 0; i < stepRefs.value.length; i++) {
    const el = stepRefs.value[i]
    if (!el) continue
    const rect = el.getBoundingClientRect()
    if (Math.abs(rect.top) < window.innerHeight * 0.5 && isStepValid(i)) {
      if (i < stepRefs.value.length - 1) {
        scrollToStep(i + 1)
        setTimeout(() => {
          const inp = stepRefs.value[i + 1]?.querySelector('input:not([type=checkbox]):not([type=password]),select')
          if (inp) inp.focus()
        }, 600)
      }
      break
    }
  }
}

// ─── Submit ───
async function handleSubmit() {
  try {
    await configStore.submitWizard()
    emit('complete')
  } catch (error) {
    // error handled in store
  }
}

onMounted(async () => {
  await configStore.loadPresets()
  addEventListener('scroll', onScroll)
  document.addEventListener('keydown', onKeydown)

  await nextTick()
  initRain()
  // Start typewriter immediately
  typewriterReveal('Welcome to the Matrix', glitchText.value)
  // Auto-advance to name after welcome finishes
  setTimeout(() => scrollToStep(1), 4200)
})

onUnmounted(() => {
  removeEventListener('scroll', onScroll)
  document.removeEventListener('keydown', onKeydown)
  if (rainInterval) clearInterval(rainInterval)
})
</script>

<template>
  <div class="me">
    <canvas ref="rainCanvas" class="me-rain"></canvas>
    <div class="me-progress" :style="{ width: `${(currentStep / (stepRefs.length - 1)) * 100}%` }"></div>

    <!-- STEP 0: Welcome -->
    <div :ref="el => setStepRef(el, 0)" class="me-step">
      <div class="step-inner visible">
        <div class="me-title me-title--welcome"><span class="me-glitch" ref="glitchText"></span></div>
      </div>
    </div>

    <!-- STEP 1: Name -->
    <div :ref="el => setStepRef(el, 1)" class="me-step">
      <div class="step-inner visible">
        <div class="me-label">// identify yourself</div>
        <StepUserName />
      </div>
    </div>

    <!-- STEP 2: Directory -->
    <div :ref="el => setStepRef(el, 2)" class="me-step">
      <div class="step-inner visible">
        <div class="me-label">// workspace</div>
        <StepDirectory />
      </div>
    </div>

    <!-- STEP 3: Brain -->
    <div :ref="el => setStepRef(el, 3)" class="me-step">
      <div class="step-inner visible">
        <div class="me-label">// brain</div>
        <StepLLM which="llm" />
      </div>
    </div>

    <!-- STEP 4: Cerebellum -->
    <div :ref="el => setStepRef(el, 4)" class="me-step">
      <div class="step-inner visible">
        <div class="me-label">// cerebellum</div>
        <StepLLM which="slm" />
      </div>
    </div>

    <!-- STEP 5: Initialize -->
    <div :ref="el => setStepRef(el, 5)" class="me-step">
      <div class="step-inner visible">
        <button
          class="me-start-btn"
          :disabled="!isStepValid(5) || configStore.isSubmitting"
          @click="handleSubmit"
        >
          <span v-if="configStore.isSubmitting" class="me-btn-spin"></span>
          {{ configStore.isSubmitting ? 'Initializing...' : 'Initialize Matrix' }}
        </button>
        <div class="me-summary" v-if="isStepValid(1) && isStepValid(2) && isStepValid(3)">
          {{ configStore.wizardData.user_name }} // {{ configStore.wizardData.default_llm.model_name }} / {{ configStore.wizardData.default_slm.model_name }}
        </div>
        <div v-if="configStore.submitError" class="me-error">{{ configStore.submitError }}</div>
      </div>
    </div>

    <div class="me-hint" v-if="currentStep > 0 && currentStep < stepRefs.length - 1">
      press enter to continue
    </div>

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
  overflow-y: auto;
  scroll-snap-type: y mandatory;
  background: var(--parchment-50);
  scroll-behavior: smooth;
}

.me-rain {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
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
  position: relative;
  z-index: 1;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px 40px;
  scroll-snap-align: start;
}

.step-inner {
  max-width: 520px;
  width: 100%;
  text-align: center;
  opacity: 0;
  transform: translateY(20px);
  transition: opacity 0.6s ease, transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
}

.step-inner.visible {
  opacity: 1;
  transform: translateY(0);
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
}

.me-glitch {
  position: relative;
  display: inline-block;
}

.me-glitch::before,
.me-glitch::after {
  content: attr(data-text);
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  opacity: 0;
}

.me-glitch.done::before {
  color: var(--vermillion);
  animation: me-g1 3s infinite linear alternate-reverse;
  clip-path: polygon(0 0, 100% 0, 100% 45%, 0 45%);
  opacity: 0.4;
}

.me-glitch.done::after {
  color: var(--amber);
  animation: me-g2 4s infinite linear alternate-reverse;
  clip-path: polygon(0 60%, 100% 60%, 100% 100%, 0 100%);
  opacity: 0.4;
}

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

.me-start-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  background: var(--ink-900);
  color: var(--parchment-50);
  border: none;
  font-family: var(--font-mono);
  font-size: 14px;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  padding: 16px 52px;
  border-radius: 2px;
  cursor: pointer;
  transition: all 0.25s;
  margin-top: 40px;
}

.me-start-btn:hover { background: var(--vermillion) }
.me-start-btn:disabled { opacity: 0.2; cursor: default }

.me-summary {
  font-size: 13px;
  color: var(--ink-ghost);
  margin-top: 20px;
  letter-spacing: 0.05em;
}

.me-error {
  margin-top: 16px;
  padding: 8px 16px;
  background: var(--fault-muted);
  color: var(--fault);
  font-size: 12px;
  border-radius: 2px;
}

.me-hint {
  position: fixed;
  bottom: 28px;
  left: 0;
  right: 0;
  text-align: center;
  font-size: 12px;
  color: var(--ink-ghost);
  letter-spacing: 0.15em;
  z-index: 2;
  opacity: 0.6;
}

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
</style>