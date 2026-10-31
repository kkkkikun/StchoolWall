import { createApp } from 'vue'
import { createPinia } from 'pinia'
import { provideGlobalConfig } from 'element-plus'
// 暗色模式 CSS 变量（仅 3KB，必须保留）；组件样式由 unplugin-vue-components 按需注入
import 'element-plus/theme-chalk/dark/css-vars.css'
// 服务型 API（ElMessage / ElMessageBox）的样式：它们由 AutoImport 注入到各视图 chunk，
// 但 request.ts 在主 chunk 里就要用 ElMessage，样式必须进主 chunk，否则首屏报错提示无样式
import 'element-plus/es/components/message/style/css'
import 'element-plus/es/components/message-box/style/css'
import './styles/theme.css'
import { initTheme } from './stores/theme'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import App from './App.vue'
import router from './router'

// 玫瑰红品牌双模式：白天/夜晚（Element Plus dark 机制 + theme.css 覆写），持久化见 stores/theme.ts
initTheme()

const app = createApp(App)
app.use(createPinia())
app.use(router)
// 按需引入模式下不能再 app.use(ElementPlus)（那会注册全部组件），
// 用 provideGlobalConfig 把中文 locale 挂到 app 上，ElMessageBox 按钮文案仍是中文
provideGlobalConfig({ locale: zhCn }, app)
app.mount('#app')
