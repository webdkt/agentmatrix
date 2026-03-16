// Component Loader - 组件加载器

/**
 * 组件加载器
 * 用于动态加载 HTML 模板组件
 */
const componentCache = new Map();

/**
 * 加载组件模板
 * @param {string} url - 组件模板 URL
 * @returns {Promise<string>} 组件 HTML 内容
 */
async function loadComponent(url) {
    // 检查缓存
    if (componentCache.has(url)) {
        console.log(`[ComponentLoader] Using cached component: ${url}`);
        return componentCache.get(url);
    }

    try {
        console.log(`[ComponentLoader] Loading component: ${url}`);
        const response = await fetch(url);

        if (!response.ok) {
            throw new Error(`Failed to load component: ${response.status} ${response.statusText}`);
        }

        const text = await response.text();

        // 缓存组件
        componentCache.set(url, text);

        return text;
    } catch (error) {
        console.error(`[ComponentLoader] Error loading component ${url}:`, error);
        throw error;
    }
}

/**
 * 渲染组件到指定容器
 * @param {string} componentUrl - 组件模板 URL
 * @param {string} targetSelector - 目标容器选择器
 * @param {Function} initCallback - 组件初始化回调（可选）
 */
async function mountComponent(componentUrl, targetSelector, initCallback) {
    try {
        const targetElement = document.querySelector(targetSelector);

        if (!targetElement) {
            throw new Error(`Target element not found: ${targetSelector}`);
        }

        // 加载组件模板
        const templateHtml = await loadComponent(componentUrl);

        // 创建临时容器来解析 HTML
        const tempContainer = document.createElement('div');
        tempContainer.innerHTML = templateHtml;

        // 提取 template 标签内容
        const template = tempContainer.querySelector('template');
        if (template) {
            // 克隆模板内容
            const clone = template.content.cloneNode(true);
            targetElement.appendChild(clone);
        } else {
            // 如果没有 template 标签，直接使用 HTML 内容
            targetElement.innerHTML = templateHtml;
        }

        // 调用初始化回调
        if (initCallback && typeof initCallback === 'function') {
            initCallback(targetElement);
        }

        console.log(`[ComponentLoader] Component mounted: ${componentUrl} -> ${targetSelector}`);
    } catch (error) {
        console.error(`[ComponentLoader] Failed to mount component ${componentUrl}:`, error);

        // 显示错误提示
        const targetElement = document.querySelector(targetSelector);
        if (targetElement) {
            targetElement.innerHTML = `
                <div class="p-4 bg-red-50 border border-red-200 rounded-lg">
                    <p class="text-red-700 text-sm">Failed to load component: ${componentUrl}</p>
                    <p class="text-red-500 text-xs mt-1">${error.message}</p>
                </div>
            `;
        }
    }
}

/**
 * 预加载多个组件
 * @param {string[]} urls - 组件 URL 数组
 */
async function preloadComponents(urls) {
    console.log(`[ComponentLoader] Preloading ${urls.length} components...`);
    try {
        await Promise.all(urls.map(url => loadComponent(url)));
        console.log(`[ComponentLoader] All components preloaded successfully`);
    } catch (error) {
        console.error(`[ComponentLoader] Error preloading components:`, error);
    }
}

/**
 * 清除组件缓存
 * @param {string} url - 组件 URL（可选，如果不提供则清除所有缓存）
 */
function clearComponentCache(url) {
    if (url) {
        componentCache.delete(url);
        console.log(`[ComponentLoader] Cache cleared for: ${url}`);
    } else {
        componentCache.clear();
        console.log(`[ComponentLoader] All cache cleared`);
    }
}
