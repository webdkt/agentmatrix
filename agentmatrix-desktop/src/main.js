import { createApp } from 'vue'
import { createPinia } from 'pinia'
// 导入全局样式（按顺序）
import './styles/fonts.css'       // 本地字体（必须在 tokens 之前）
import './styles/tabler-icons.css' // 本地 Tabler Icons
import './styles/tokens.css'      // 设计令牌
import './styles/global.css'      // 全局样式
import './styles/animations.css'  // 全局动画
import './styles/utilities.css'   // 工具类
import './styles/components.css'  // 通用组件样式
import i18n from './i18n'
import App from './App.vue'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(i18n)
app.mount('#app')
