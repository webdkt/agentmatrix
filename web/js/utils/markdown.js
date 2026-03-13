// Markdown 渲染工具

/**
 * 渲染 Markdown 为 HTML
 * @param {string} content - Markdown 格式文本
 * @returns {string} HTML 字符串
 */
export function renderMarkdown(content) {
    if (!content) return '';

    try {
        // Configure marked options for better rendering
        marked.setOptions({
            breaks: true,      // Convert \n to <br>
            gfm: true,         // GitHub Flavored Markdown
            headerIds: false,  // Don't generate header IDs
            mangle: false      // Don't mangle email addresses
        });
        return marked.parse(content);
    } catch (error) {
        console.error('Markdown rendering error:', error);
        // Fallback to plain text with line breaks
        return content.replace(/\n/g, '<br>');
    }
}
