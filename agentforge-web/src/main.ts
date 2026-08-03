import { createApp } from 'vue'
import { createPinia } from 'pinia'
// Element Plus 按需引入（M4：仅注册实际使用的组件，替代全量包，构建产物从 ~1MB 降至 ~300KB）
import { ElButton, ElForm, ElFormItem, ElInput } from 'element-plus'
import 'element-plus/es/components/form/style/css'
import 'element-plus/es/components/form-item/style/css'
import 'element-plus/es/components/input/style/css'
import 'element-plus/es/components/button/style/css'
import 'element-plus/es/components/message/style/css'
import App from './App.vue'
import router from './router'
import './assets/main.css'

const app = createApp(App)
app.use(createPinia())
for (const comp of [ElButton, ElForm, ElFormItem, ElInput]) app.use(comp)
app.use(router)
app.mount('#app')
