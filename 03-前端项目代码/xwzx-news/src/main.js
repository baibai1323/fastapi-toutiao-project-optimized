/**
 * 前端入口文件：创建 Vue 应用、安装路由 / 状态管理 / 组件库 / 国际化，最后挂载到页面。
 * 入口只做“组装”，不写业务逻辑；这样排查“某个全局能力没生效”时只需看这一个文件。
 *
 * 术语说明：
 * - Vue 应用实例：由 createApp 创建，所有插件都要 app.use() 注册后才全局可用；
 * - SPA（单页应用）：整站只有一个 index.html，页面切换由前端路由完成，不重新请求整页。
 */
import { createApp } from 'vue'
// 根组件与全局插件：路由负责页面切换，pinia 负责跨页面共享状态。
import App from './App.vue'
import router from './router'
import pinia from './store'

// 导入Vant组件库
// 这里采用“按需引入”：只注册项目真正用到的组件，避免把整个 Vant 打进包里。
// 逐个注册虽然啰嗦，但能直接看出项目依赖哪些 UI 组件，新增组件时也不容易漏。
import { 
  Button, 
  NavBar, 
  Tabbar, 
  TabbarItem, 
  Tab, 
  Tabs, 
  List, 
  PullRefresh, 
  Cell, 
  CellGroup,
  Grid,
  GridItem,
  Empty,
  Form,
  Field,
  Image,
  Toast,
  Icon,
  Popup
} from 'vant'

// 导入Vant样式
// Vant 的组件样式是独立 CSS，必须显式引入，否则组件有结构但没有外观。
import 'vant/lib/index.css'

// 导入全局样式
// style.css 里放重置样式和 CSS 变量，保证所有页面视觉基线一致。
import './style.css'

// 引入国际化
// i18n 让界面文案按语言包切换，避免中文写死在模板里。
import { setupI18n } from './i18n'

// 创建应用实例。此时还没有挂载，下面的 app.use 都是往实例上装插件。
const app = createApp(App)

// 设置i18n
// 先安装 i18n，模板里的 $t('nav.home') 才能在首次渲染时找到翻译函数。
const i18n = setupI18n()
app.use(i18n)

// 注册Vant组件
// app.use(组件) 是 Vant 的全局注册方式，注册后任意页面都能直接写 <van-button> 等标签。
app.use(Button)
app.use(NavBar)
app.use(Tabbar)
app.use(TabbarItem)
app.use(Tab)
app.use(Tabs)
app.use(List)
app.use(PullRefresh)
app.use(Cell)
app.use(CellGroup)
app.use(Grid)
app.use(GridItem)
app.use(Empty)
app.use(Form)
app.use(Field)
app.use(Image)
app.use(Toast)
app.use(Icon)
app.use(Popup)

// 使用路由和状态管理
// 路由决定当前 URL 渲染哪个页面；pinia 必须先安装，后面 useThemeStore() 才能拿到已激活的实例。
app.use(router)
app.use(pinia)

// 挂载到 index.html 里 id="app" 的节点，Vue 从这里接管页面渲染。
app.mount('#app')

// 初始化主题
// ES 模块的 import 会被提升到文件顶部执行，所以写在 mount 之后也能正常导入。
// 挂载后调用 initTheme()，把 localStorage 中保存的主题写回 CSS 变量，页面一启动就是用户上次的选择。
import { useThemeStore } from './store/theme'
const themeStore = useThemeStore()
themeStore.initTheme()
