import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { installDiagnostics, setCurrentRoute } from './utils/diagnostics'
import './styles/tokens.css'

const app = createApp(App)

// 诊断采集要先于路由挂载，否则首个页面的报错会漏掉
installDiagnostics()
router.afterEach((to) => setCurrentRoute(to.fullPath))

app.use(createPinia())
app.use(router)
app.mount('#app')
