<script setup>
import { ref } from 'vue'

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (value) => ['brain', 'cerebellum'].includes(value)
  }
})

const emit = defineEmits(['click'])

const showModal = ref(false)

function onClick() {
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

// Help content
const helpContent = {
  brain: {
    title: 'Brain Configuration',
    html: `
      <p>The <strong>Brain</strong> is AgentMatrix's primary reasoning engine — the large language model (LLM) that handles complex thinking, analysis, and decision-making.</p>
      <p><strong>What you need to provide:</strong></p>
      <p>• <span class="highlight">Model Name</span> — The specific model identifier (e.g., <code>claude-3-5-sonnet-20241022</code>)</p>
      <p>• <span class="highlight">API Key</span> — Your authentication key for the model provider</p>
      <p><strong>Recommended providers:</strong> Anthropic Claude, OpenAI GPT-4, Google Gemini, or other high-end models for best reasoning capabilities.</p>
      <p>This model will be used for tasks requiring deep understanding, creative problem-solving, and nuanced responses.</p>
    `
  },
  cerebellum: {
    title: 'Cerebellum Configuration',
    html: `
      <p>The <strong>Cerebellum</strong> (小脑) handles routine, mechanical tasks — simple operations that don't require complex reasoning but need speed and efficiency.</p>
      <p><strong>What it's used for:</strong></p>
      <p>• Quick responses and simple queries</p>
      <p>• Basic information retrieval</p>
      <p>• Routine agent coordination</p>
      <p><strong>Recommendation:</strong> Choose a model that is <span class="highlight">faster and cheaper</span> than your Brain model. Default is set to match Brain, but we recommend <strong>Xiaomi's Mimo Flash V2</strong> for optimal cost-performance.</p>
      <p>Since Cerebellum tasks are straightforward, a less powerful model delivers excellent results while <strong>significantly reducing costs</strong>.</p>
    `
  }
}
</script>

<template>
    <!-- Help Question -->
    <Teleport to="body">
      <div class="help-question" @click="onClick">
        <!-- 光晕背景 -->
        <div class="help-question__glow"></div>

        <!-- 问号主体 -->
        <div class="help-question__mark">?</div>

        <!-- 扫描线遮罩 -->
        <div class="help-question__scanlines"></div>

        <!-- 网点遮罩 -->
        <div class="help-question__grid"></div>

        <!-- 边缘暗角遮罩 -->
        <div class="help-question__vignette"></div>
      </div>
    </Teleport><!---->

    <!-- Help Modal -->
    <Teleport to="body"><!---->
      <Transition name="modal">
        <div v-if="showModal" class="modal-overlay" :class="{ active: showModal }" @click.self="closeModal">
          <div class="modal-container" @click.stop>
            <!-- Modal Header -->
            <div class="modal-header">
              <div class="modal-header-line"></div>
              <h2 class="modal-title">{{ helpContent[type].title }}</h2>
              <button class="modal-close" @click="closeModal">×</button>
            </div>

            <!-- Modal Body -->
            <div class="modal-body">
              <div class="modal-content" v-html="helpContent[type].html"></div>
            </div>

            <!-- Modal Footer -->
            <div class="modal-footer">
              <button class="modal-btn" @click="closeModal">
                Understood
              </button>
            </div>
          </div>
        </div>
      </Transition>
    </Teleport><!---->
  </template>
<style scoped>
.help-question {
  position: fixed;
  top: 120px;
  right: 120px;
  z-index: 10;
  cursor: pointer;
  width: 140px;
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: float 4s ease-in-out infinite;
}

@keyframes float {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-6px); }
}

/* 光晕背景 */
.help-question__glow {
  position: absolute;
  width: 140px;
  height: 140px;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(212, 168, 67, 0.2) 0%,
    rgba(212, 168, 67, 0.1) 50%,
    transparent 70%
  );
  animation: glow-pulse 2.5s ease-in-out infinite;
  pointer-events: none;
}

@keyframes glow-pulse {
  0%, 100% { opacity: 0.5; transform: scale(1); }
  50% { opacity: 0.8; transform: scale(1.1); }
}

/* 问号主体 */
.help-question__mark {
  position: relative;
  font-family: Georgia, serif;
  font-size: 90px;
  font-weight: 700;
  color: #D4A843;
  user-select: none;

  /* 垂直拉丝纹理 */
  background: repeating-linear-gradient(
    90deg,
    transparent,
    transparent 1px,
    rgba(255, 255, 255, 0.12) 1px,
    rgba(255, 255, 255, 0.12) 2px
  );
  -webkit-background-clip: text;
  background-clip: text;

  /* 金色荧光 */
  text-shadow:
    0 0 8px rgba(212, 168, 67, 0.8),
    0 0 16px rgba(212, 168, 67, 0.6),
    0 0 32px rgba(212, 168, 67, 0.4),
    0 0 48px rgba(180, 140, 50, 0.25);

  /* CRT闪烁 */
  animation: crt-flicker 0.12s infinite;
}

@keyframes crt-flicker {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.97; }
}

/* 磷光余辉 */
.help-question__mark::before {
  content: '?';
  position: absolute;
  color: #D4A843;
  filter: blur(0.5px);
  opacity: 0.4;
  animation: crt-flicker 0.12s infinite 0.02s;
  pointer-events: none;
}

/* 扫描线遮罩 */
.help-question__scanlines {
  position: absolute;
  inset: 0;
  background: repeating-linear-gradient(
    0deg,
    transparent,
    transparent 2px,
    rgba(253, 252, 249, 0.3) 2px,
    rgba(253, 252, 249, 0.3) 4px
  );
  pointer-events: none;
  border-radius: 8px;
}

/* 网点遮罩 */
.help-question__grid {
  position: absolute;
  inset: 0;
  background-image: radial-gradient(circle, rgba(253, 252, 249, 0.15) 1px, transparent 1px);
  background-size: 4px 4px;
  pointer-events: none;
  opacity: 0.3;
  border-radius: 8px;
}

/* 边缘暗角遮罩 */
.help-question__vignette {
  position: absolute;
  inset: 0;
  box-shadow: inset 0 0 40px rgba(253, 252, 249, 0.6);
  border-radius: 10px;
  pointer-events: none;
}

/* 悬浮状态 */
.help-question:hover .help-question__glow {
  background: radial-gradient(
    circle,
    rgba(240, 200, 96, 0.4) 0%,
    rgba(240, 200, 96, 0.2) 50%,
    transparent 70%
  );
  animation: glow-breathe 1.5s ease-in-out infinite;
}

@keyframes glow-breathe {
  0%, 100% {
    opacity: 0.8;
    transform: scale(1);
  }
  50% {
    opacity: 1;
    transform: scale(1.15);
  }
}

.help-question:hover .help-question__mark {
  color: #F0C860;
  text-shadow:
    0 0 12px rgba(240, 200, 96, 1),
    0 0 24px rgba(240, 200, 96, 0.8),
    0 0 36px rgba(240, 200, 96, 0.6),
    0 0 60px rgba(240, 200, 96, 0.4);
}

/* ========== HELP MODAL ========== */
.modal-overlay {
  position: fixed;
  inset: 0;
  z-index: 1000;
  background: rgba(26, 26, 26, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  backdrop-filter: blur(3px);
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease, visibility 0.3s ease;
}

.modal-overlay.active {
  opacity: 1;
  visibility: visible;
}

.modal-container {
  position: relative;
  max-width: 560px;
  width: 100%;
  background: var(--parchment-50);
  border: 1px solid var(--parchment-300);
  border-radius: 4px;
  box-shadow: 0 12px 48px rgba(0, 0, 0, 0.25);
  transform: translateY(20px) scale(0.98);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
}

.modal-overlay.active .modal-container {
  transform: translateY(0) scale(1);
}

.modal-header {
  position: relative;
  padding: 24px 32px 20px;
  border-bottom: 1px solid var(--parchment-300);
}

.modal-header-line {
  position: absolute;
  top: 0;
  left: 32px;
  right: 32px;
  height: 3px;
  background: var(--accent);
}

.modal-title {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 600;
  color: var(--ink-900);
  margin: 0;
  line-height: 1.4;
}

.modal-close {
  position: absolute;
  top: 20px;
  right: 16px;
  width: 32px;
  height: 32px;
  border: none;
  background: transparent;
  font-size: 28px;
  color: var(--ink-400);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 2px;
  font-family: Georgia, serif;
  font-weight: 300;
  line-height: 1;
  padding: 0;
  transition: color 0.2s, background 0.2s;
}

.modal-close:hover {
  color: var(--ink-900);
  background: var(--parchment-200);
}

.modal-body {
  padding: 24px 32px;
  max-height: 60vh;
  overflow-y: auto;
}

.modal-content {
  font-family: var(--font-serif);
  font-size: 15px;
  line-height: 1.8;
  color: var(--ink-700);
}

.modal-content :deep(p) {
  margin: 0 0 16px 0;
}

.modal-content :deep(p:last-child) {
  margin-bottom: 0;
}

.modal-content :deep(strong) {
  font-weight: 600;
  color: var(--ink-900);
}

.modal-content :deep(code) {
  font-family: var(--font-mono);
  font-size: 14px;
  background: var(--parchment-200);
  padding: 2px 6px;
  border-radius: 2px;
  color: var(--ink-900);
}

.modal-content :deep(.highlight) {
  background: var(--accent-muted);
  padding: 2px 4px;
  border-radius: 2px;
  color: var(--accent);
  font-weight: 500;
}

.modal-footer {
  padding: 16px 32px 20px;
  border-top: 1px solid var(--parchment-300);
  display: flex;
  justify-content: flex-end;
}

.modal-btn {
  background: #1A1A1A;
  color: #FDFCF9;
  border: none;
  font-family: var(--font-mono);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.15em;
  text-transform: uppercase;
  padding: 12px 24px;
  border-radius: 2px;
  cursor: pointer;
  transition: background 0.2s;
}

.modal-btn:hover {
  background: var(--accent);
}

/* Modal Transitions */
.modal-enter-active,
.modal-leave-active {
  transition: opacity 0.3s ease;
}

.modal-enter-active .modal-container,
.modal-leave-active .modal-container {
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1), opacity 0.3s ease;
}

.modal-enter-from,
.modal-leave-to {
  opacity: 0;
}

.modal-enter-from .modal-container,
.modal-leave-to .modal-container {
  transform: translateY(20px) scale(0.98);
  opacity: 0;
}
</style>
