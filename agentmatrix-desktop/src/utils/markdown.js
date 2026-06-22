import { marked } from 'marked'
import { isContainerPath } from '@/utils/pathHelper'

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}

function escapeAttr(s) {
  return s.replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

/**
 * 渲染 Markdown 文本为 HTML。
 * 自动将 `path` 形式的 codespan 标记为可点击的 container-path。
 */
export function renderMarkdown(text) {
  if (!text) return ''
  const renderer = new marked.Renderer()
  renderer.codespan = function (token) {
    const raw = token.text || token
    if (isContainerPath(raw)) {
      return `<code class="container-path" data-path="${escapeAttr(raw)}">${escapeHtml(raw)}</code>`
    }
    return `<code>${escapeHtml(raw)}</code>`
  }
  renderer.code = function (token) {
    const raw = token.text || token
    const lang = token.lang || ''
    const langAttr = lang ? ` data-lang="${escapeAttr(lang)}"` : ''
    return `<pre class="code-block"${langAttr}><button class="code-block__copy" title="Copy">Copy</button><code>${escapeHtml(raw)}</code></pre>`
  }
  // Agent 输出一律当文本：raw HTML 标签全部 escape 显示为字面，不被 v-html
  // 解释/注入/污染。原则：agent 想展示标签字面，要么自己写 markdown code block，
  // 要么我们兜底把它显示成 code block。ChatMessage 用 v-html 直接注入主 app DOM，
  // raw HTML 透传会全局污染（实测：Designer 贴 deck 的 <style> 把整个窗口底色
  // 变黑、字不可读），<script> 会触发 XSS。
  // marked v17 里 block + inline HTML 都走 renderer.html，token.block 区分。
  renderer.html = function (token) {
    const raw = (token.text || '').trim()
    if (!raw) return ''
    if (token.block) {
      return `<pre class="code-block"><code>${escapeHtml(raw)}</code></pre>`
    }
    return `<code>${escapeHtml(raw)}</code>`
  }
  try {
    return marked.parse(String(text), { renderer }).trim()
  } catch {
    return text
  }
}