import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { useThemeStore } from './stores/theme'
import { installDiagnostics, setCurrentRoute } from './utils/diagnostics'
import './styles/tokens.css'

const app = createApp(App)
const pinia = createPinia()

// 诊断采集要先于路由挂载，否则首个页面的报错会漏掉
installDiagnostics()
router.afterEach((to) => setCurrentRoute(to.fullPath))

app.use(pinia)

// 主题要在挂载前落到 <html> 上，避免深色模式用户先看到一帧浅色
useThemeStore().init()

app.use(router)
app.mount('#app')
