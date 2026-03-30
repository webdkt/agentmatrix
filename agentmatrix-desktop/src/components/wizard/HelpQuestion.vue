<script setup>
import { ref, computed } from 'vue'
import { open } from '@tauri-apps/plugin-shell'

const props = defineProps({
  type: {
    type: String,
    required: true,
    validator: (value) => ['brain', 'cerebellum'].includes(value)
  }
})

const showModal = ref(false)

// Detect language: 'zh' for Chinese, 'en' for English
const currentLang = computed(() => {
  const lang = navigator.language || navigator.userLanguage
  return lang.startsWith('zh') ? 'zh' : 'en'
})

// Help content in both languages
const helpContent = {
  brain: {
    en: {
      title: 'Brain Configuration',
      html: `
        <p>The <strong>Brain</strong> is AgentMatrix's primary reasoning engine — the large language model (LLM) that handles complex thinking, analysis, and decision-making.</p>
        <p><strong>What you need to provide:</strong></p>
        <p>• <span class="highlight">Model Name</span> — The specific model name</p>
        <p>• <span class="highlight">API Key</span> — Your authentication key for the model provider</p>
        <p><strong>Where to get API keys:</strong></p>
        <div class="api-links">
          <p>• <a href="https://www.bigmodel.cn/glm-coding" target="_blank" rel="noopener">智谱 GLM (Zhipu AI)</a></p>
          <p>• <a href="https://www.kimi.com/membership/pricing" target="_blank" rel="noopener">Kimi (Moonshot AI)</a></p>
          <p>• <a href="https://platform.minimaxi.com/subscribe/token-plan" target="_blank" rel="noopener">MiniMax</a></p>
          <p>• <a href="https://platform.xiaomimimo.com/" target="_blank" rel="noopener">Xiaomi Mimo</a></p>
          <p>• <a href="https://console.anthropic.com/" target="_blank" rel="noopener">Anthropic Claude</a></p>
          <p>• <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">OpenAI</a></p>
        </div>
        <p>This model will be used for tasks requiring deep understanding, creative problem-solving, and nuanced responses.</p>
      `
    },
    zh: {
      title: '大脑配置',
      html: `
        <p><strong>大脑</strong>是AgentMatrix的主要推理引擎——负责复杂思维、分析和决策的大语言模型（LLM）。</p>
        <p><strong>您需要提供：</strong></p>
        <p>• <span class="highlight">模型名称</span> — 具体的模型名字</p>
        <p>• <span class="highlight">API密钥</span> — 您在模型提供商处的认证密钥</p>
        <p><strong>如何获取API密钥：</strong></p>
        <div class="api-links">
          <p>• <a href="https://www.bigmodel.cn/glm-coding" target="_blank" rel="noopener">智谱 GLM</a></p>
          <p>• <a href="https://www.kimi.com/membership/pricing" target="_blank" rel="noopener">Kimi (月之暗面)</a></p>
          <p>• <a href="https://platform.minimaxi.com/subscribe/token-plan" target="_blank" rel="noopener">MiniMax</a></p>
          <p>• <a href="https://platform.xiaomimimo.com/" target="_blank" rel="noopener">小米 Mimo</a></p>
          <p>• <a href="https://console.anthropic.com/" target="_blank" rel="noopener">Anthropic Claude</a></p>
          <p>• <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener">OpenAI</a></p>
        </div>
        <p>该模型将用于需要深度理解、创造性解决问题和细致回应的任务。</p>
      `
    }
  },
  cerebellum: {
    en: {
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
    },
    zh: {
      title: '小脑配置',
      html: `
        <p><strong>小脑</strong>处理日常、机械性任务——不需要复杂推理但需要速度和效率的简单操作。</p>
        <p><strong>主要用途：</strong></p>
        <p>• 快速响应和简单查询</p>
        <p>• 基础信息检索</p>
        <p>• 常规代理协调</p>
        <p><strong>建议：</strong> 选择比大脑模型<span class="highlight">更快更便宜</span>的模型。默认设置与大脑相同，但我们推荐使用<strong>小米的Mimo Flash V2</strong>以获得最佳性价比。</p>
        <p>由于小脑任务相对简单，使用较弱的模型也能获得优秀结果，同时<span class="highlight">显著降低成本</span>。</p>
      `
    }
  }
}

// Get content for current type and language
const currentContent = computed(() => {
  return helpContent[props.type][currentLang.value]
})



// Handle link clicks to open in external browser
async function handleLinkClick(e) {
  const target = e.target;
  if (target.tagName === 'A' && target.href) {
    e.preventDefault();
    e.stopPropagation();
    try {
      await open(target.href);
    } catch (error) {
      console.error('Failed to open URL:', error);
    }
  }
}

function onClick() {
  showModal.value = true
}

function closeModal() {
  showModal.value = false
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
              <h2 class="modal-title">{{ currentContent.title }}</h2>
              <button class="modal-close" @click="closeModal">×</button>
            </div>

            <!-- Modal Body -->
            <div class="modal-body">
              <div class="modal-content" v-html="currentContent.html" @click="handleLinkClick"></div>
            </div>

            <!-- Modal Footer -->
            <div class="modal-footer">
              <button class="modal-btn" @click="closeModal">
                {{ currentLang === 'zh' ? '明白了' : 'Understood' }}
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
  z-index: 100;
  cursor: pointer;
  width: 140px;
  height: 140px;
  display: flex;
  align-items: center;
  justify-content: center;
  animation: float 4s ease-in-out infinite;
  pointer-events: auto;
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

.modal-content :deep(.api-links) {
  margin: 16px 0;
  padding: 16px;
  background: var(--parchment-100);
  border-radius: 4px;
  border-left: 3px solid var(--accent);
}

.modal-content :deep(.api-links p) {
  margin: 8px 0;
  font-size: 14px;
}

.modal-content :deep(a) {
  color: var(--accent);
  text-decoration: none;
  transition: text-decoration 0.2s;
}

.modal-content :deep(a:hover) {
  text-decoration: underline;
}
