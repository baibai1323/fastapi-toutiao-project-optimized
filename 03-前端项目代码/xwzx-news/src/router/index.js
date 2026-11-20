/**
 * 前端路由表：把 URL 路径映射到页面组件。
 *
 * 约定：
 * - component 统一写成 () => import(...)，即“路由懒加载”：只有访问该路径时才下载对应页面代码，
 *   首屏不必加载全部页面，包体积更小；代价是第一次进入某页会多一次网络请求。
 * - meta 是路由的附加信息，不参与匹配。这里用 title 设置浏览器标签标题，
 *   用 keepAlive 告诉根组件 App.vue 是否需要缓存该页面实例。
 * - history 模式使用 createWebHistory，URL 形如 /home 而不是 /#/home；需要服务端把未知路径回退到 index.html。
 *
 * 阅读顺序建议：先看 routes 里的路径与 meta，再看文件末尾的全局守卫。
 * 新增页面时只需在 routes 里加一项，并确认 main.js 已安装 router、App.vue 有 router-view 出口。
 */
import { createRouter, createWebHistory } from 'vue-router'

// 路由数组的顺序只影响可读性，匹配时 Vue Router 会按具体路径优先级处理；
// 但把重定向和登录页放前面，能让配置意图更直观。
// 下面按“公开入口 → 主页面 → 个人中心 → 设置”分组，组与组之间用注释分隔，便于快速定位。
const routes = [
  // 访问根路径时统一跳到首页，避免出现空白页；redirect 不会创建组件实例。
  {
    path: '/',
    redirect: '/home'
  },
  // 登录页：不缓存（keepAlive: false），每次进入都应该是干净的表单，不保留上次输入的密码。
  // 登录/注册是游客入口，不放在 TabBar 里，通过“我的”页或 401 跳转进入。
  {
    path: '/login',
    name: 'Login',
    component: () => import('../views/Login.vue'),
    meta: {
      title: '登录',
      keepAlive: false
    }
  },
  // 注册页：同样不缓存，避免注册成功后返回时还看到旧表单和旧错误提示。
  {
    path: '/register',
    name: 'Register',
    component: () => import('../views/Register.vue'),
    meta: {
      title: '注册',
      keepAlive: false
    }
  },
  // 首页：缓存（keepAlive: true）。从详情页返回时保留已加载的新闻列表和滚动位置，
  // 否则每次返回都重新请求第一页，既慢又浪费流量。
  // 首页和分类页共用新闻列表数据，但路由分开，便于分别控制缓存策略。
  {
    path: '/home',
    name: 'Home',
    component: () => import('../views/Home.vue'),
    meta: {
      title: '首页',
      keepAlive: true
    }
  },
  // 新闻详情：路径里的 :id 是动态参数，详情页通过 route.params.id 读取。
  // 不缓存，保证不同新闻之间切换时重新拉取对应详情，不会残留上一篇的内容。
  {
    path: '/news/detail/:id',
    name: 'NewsDetail',
    component: () => import('../views/NewsDetail.vue'),
    meta: {
      title: '新闻详情',
      keepAlive: false
    }
  },
  // 浏览历史：数据可能随时变化，不缓存，进入时重新拉取最新记录。
  // 历史页依赖登录态，未登录时页面内部会展示引导，而不是由路由直接拦截。
  {
    path: '/history',
    name: 'History',
    component: () => import('../views/History.vue'),
    meta: {
      title: '浏览历史',
      keepAlive: false
    }
  },
  // 我的收藏：同样不缓存，避免取消收藏后返回还看到旧列表。
  {
    path: '/favorite',
    name: 'Favorite',
    component: () => import('../views/Favorite.vue'),
    meta: {
      title: '我的收藏',
      keepAlive: false
    }
  },
  // 分类页：缓存，和首页一样需要保留分类切换后的列表状态。
  {
    path: '/category',
    name: 'Category',
    component: () => import('../views/Category.vue'),
    meta: {
      title: '分类',
      keepAlive: true
    }
  },
  // AI 问答：缓存，保留当前对话内容和滚动位置，返回时不用重新开始提问。
  // 对话内容属于临时状态，未持久化；刷新浏览器仍会丢失，这是当前版本的已知行为。
  {
    path: '/aichat',
    name: 'AIChat',
    component: () => import('../views/AIChat.vue'),
    meta: {
      title: 'AI问答',
      keepAlive: true
    }
  },
  // 我的：缓存，避免每次切回都重新请求用户信息；退出登录时由 store 统一清状态。
  {
    path: '/my',
    name: 'My',
    component: () => import('../views/My.vue'),
    meta: {
      title: '我的',
      keepAlive: true
    }
  },
  // 个人信息编辑页：不缓存，进入时应展示服务端最新资料，而不是上次未保存的输入。
  {
    path: '/profile',
    name: 'Profile',
    component: () => import('../views/Profile.vue'),
    meta: {
      title: '个人信息',
      keepAlive: false
    }
  },
  // 设置页：不缓存，主题/语言每次进入都按当前 store 状态重新渲染。
  // 设置页不要求登录，游客也可以切换主题和语言，偏好保存在 localStorage。
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('../views/Settings.vue'),
    meta: {
      title: '设置',
      keepAlive: false
    }
  },
  // 说明：这里没有配置 path: '/:pathMatch(.*)*' 的 404 兜底路由。
  // 访问未注册路径时页面会没有匹配组件；新增页面务必先在本数组登记，避免线上出现空白。
]

// 创建路由实例。createWebHistory 需要传基础路径：开发时通常是 /，
// 部署到子目录时由 Vite 的 BASE_URL 提供，避免资源路径写死。
// routes 用简写传入，等价于 routes: routes，是 ES6 的对象属性简写。
const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes
})

// 全局前置守卫
// 每次路由跳转前都会执行。to 是目标路由，from 是来源路由，next 用于放行或中断。
// 当前项目不做登录拦截：游客也能浏览首页和详情，涉及个人数据的接口由 http 层 401 统一跳登录。
// 这里只负责把 meta.title 写到浏览器标签页；没有配置 title 时用“新闻资讯”兜底。
// 守卫必须调用 next()，否则导航会一直挂起，表现为点击链接后页面没反应。
router.beforeEach((to, from, next) => {
  // 设置页面标题
  // meta.title 由各路由自己声明，守卫只做兜底，避免每个页面重复写 document.title。
  document.title = to.meta.title || '新闻资讯'
  
  // 直接允许访问所有页面
  // 以后若要做登录拦截，应在这里判断 to.meta.requiresAuth，并 next('/login') 而不是继续放行。
  next()
})

// 导出单例，main.js 通过 app.use(router) 安装。
// 不要在组件里另建 createRouter，否则会出现两份路由状态、守卫重复执行。
export default router