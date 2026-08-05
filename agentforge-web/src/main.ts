import { createApp } from 'vue'
import { createPinia } from 'pinia'
// 全站已回归原生控件（锻造工坊设计系统），不再引入第三方 UI 库
import App from './App.vue'
import router from './router'
import './assets/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)
app.mount('#app')
