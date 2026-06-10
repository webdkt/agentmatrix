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
  try {
    return marked.parse(String(text), { renderer }).trim()
  } catch {
    return text
  }
}