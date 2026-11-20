/**
 * Pinia 状态管理入口。
 * Pinia 是 Vue 官方推荐的状态库：把多个页面都要用的数据集中存放，任何组件都能读写同一份状态。
 * 这里只创建实例并安装持久化插件，具体业务状态放在 store/ 下的各个模块里。
 */
import { createPinia } from 'pinia'
import { createPersistedState } from 'pinia-plugin-persistedstate'

// 创建 Pinia 实例，main.js 会通过 app.use(pinia) 把它接入 Vue。
const pinia = createPinia()

// 添加持久化插件
// 插件让声明了 persist 的 store 自动把指定字段写入 localStorage，刷新页面后还能恢复。
// 存储介质显式传 localStorage，不依赖插件在不同版本里的默认行为。
pinia.use(createPersistedState({
  storage: localStorage
}))

// 导出单例，保证全项目共用同一个 Pinia 实例。
export default pinia