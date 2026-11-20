/**
 * 用户 store（Pinia 状态仓库）。
 * 负责登录态、用户资料和账号相关请求；页面只调用这里的 action，不直接写 axios。
 * 这样 token 的写入/清理只有一处，避免各页面各自维护登录状态。
 */
import { defineStore } from 'pinia'
import http, { errorMessage } from '../config/http'

/**
 * 用户状态。
 *
 * [优化] 原代码问题：
 *   1. 请求头写 `Authorization: this.token`，缺 Bearer，后端一律 401；
 *   2. 每个请求都手写完整 URL 和 headers；
 *   3. `persist` 用的是旧版 pinia-plugin-persist 的 enabled/strategies 写法，
 *      而项目装的是 pinia-plugin-persistedstate v4，配置实际不生效。
 * 修复：统一 http 实例注入 Bearer；persist 改成 v4 的 { key, storage, pick }。
 */

// 领域约定：
// - token 是后端签发的登录凭证，后续请求由 http 拦截器自动放进 Authorization 头；
// - userInfo 为 null、token 为空、isLogin 为 false 三者必须同步变化，避免“显示已登录却请求 401”；
// - 每个 action 都返回 { success, message, data? }，页面只根据 success 弹提示，不直接处理 axios 异常。
// 使用 Options 写法（state/getters/actions 分块），便于把同一类逻辑放在一起阅读；
// store id 'user' 也是持久化插件和 Vue Devtools 识别这个仓库的名字。
export const useUserStore = defineStore('user', {
  // state 只存跨页面共享的登录数据；表单临时输入放在组件里，不往全局塞。
  // userBio 是“未填写简介”时的兜底文案，getUserBio 会优先返回服务端的真实简介。
  state: () => ({
    // userInfo 保存后端返回的用户对象（用户名、头像、简介等），未登录时为 null。
    // token 只存字符串，真正的请求头拼接交给 http.js，store 不关心传输细节。
    // isLogin 是给模板做 v-if 的便捷布尔值，必须与 token 同时更新。
    userInfo: null,
    token: '',
    isLogin: false,
    userBio: '这是我的个人简介',
  }),

  // getters 是只读派生值，组件通过它们读状态，避免直接改 state 绕过 action 的同步逻辑。
  getters: {
    // 读取用户对象；组件用 computed 包一层即可保持响应式。
    getUserInfo: (state) => state.userInfo,
    // 读取 token，供需要手动拼请求头的少数场景使用（正常请求由拦截器自动加）。
    getToken: (state) => state.token,
    // 布尔登录态，专门给 v-if / v-show 使用，避免模板里写 !!token。
    getLoginStatus: (state) => state.isLogin,
    // 优先用服务端简介；为空时回退到 state 里的默认文案，保证页面不出现空白。
    getUserBio: (state) => state.userInfo?.bio || state.userBio,
  },

  // 所有 action 都返回统一结构 { success, message, data? }：
  // 页面只判断 success 并展示 message，避免每个页面重复解析 axios 错误结构。
  actions: {
    // 登录：把用户名密码交给后端，成功时一次性写入 userInfo、token、isLogin。
    // 只有 code === 200 才算成功；业务失败也走正常 HTTP 200，所以不能只看 try/catch。
    async login(userData) {
      try {
        const response = await http.post('/user/login', {
          username: userData.username,
          password: userData.password,
        })

        if (response.data?.code === 200) {
          // 三个字段同一时刻赋值，模板不会看到“有 token 但 isLogin 还是 false”的中间态。
          this.userInfo = response.data.data.userInfo
          this.token = response.data.data.token
          this.isLogin = true
          return { success: true, message: '登录成功' }
        }
        return { success: false, message: response.data?.message || '登录失败' }
      } catch (error) {
        console.error('登录请求失败:', error)
        return { success: false, message: errorMessage(error, '登录请求失败，请稍后再试') }
      }
    },

    // 注册：后端注册成功后直接返回 token，因此这里复用登录态写入逻辑，用户无需再登录一次。
    // 注册失败（如用户名重复）时透传后端 message，页面负责展示具体原因。
    async register(userData) {
      try {
        const response = await http.post('/user/register', {
          username: userData.username,
          password: userData.password,
        })

        // 注册接口同样用 code 判断业务结果，HTTP 200 不代表注册成功。
        if (response.data?.code === 200) {
          // 后端注册后直接签发 token，这里按登录态写入，用户无需再登录一次。
          this.userInfo = response.data.data.userInfo
          this.token = response.data.data.token
          this.isLogin = true
          return { success: true, message: '注册成功' }
        }
        return { success: false, message: response.data?.message || '注册失败' }
      } catch (error) {
        console.error('注册请求失败:', error)
        return { success: false, message: errorMessage(error, '注册请求失败，请稍后再试') }
      }
    },

    // 退出登录：先尽力通知服务端吊销 token，再清空本地状态。
    // 服务端请求不 await，是因为即使网络失败，用户也应当能立即退出；本地清理不能被网络阻塞。
    logout() {
      // [优化] 原代码只清本地，服务端 Token 仍然有效。
      // 服务端吊销失败也不影响本地退出：登录态以本地 token 为准。
      const token = this.token
      if (token) {
        http
          .post('/user/logout', null, {
            headers: { Authorization: `Bearer ${token}` },
          })
          .catch(() => {})
      }

      this.userInfo = null
      this.token = ''
      this.isLogin = false
      localStorage.removeItem('user-store')
    },

    // 拉取当前用户详情：用于刷新页面后补全 userInfo（本地只持久化了少量字段）。
    // 没有 token 直接返回“未登录”，避免发一个注定 401 的请求。
    async getUserInfoDetail() {
      // 刷新页面后 Pinia 只恢复持久化字段，userInfo 可能不完整，这里按需补拉。
      // 失败不自动 logout：可能是临时网络问题，保留 token 让用户重试。
      if (!this.token) {
        return { success: false, message: '未登录' }
      }

      try {
        const response = await http.get('/user/info')
        if (response.data?.code === 200) {
          this.userInfo = response.data.data
          return { success: true, message: '获取用户信息成功', data: response.data.data }
        }
        return { success: false, message: response.data?.message || '获取用户信息失败' }
      } catch (error) {
        console.error('获取用户信息请求失败:', error)
        return { success: false, message: errorMessage(error, '获取用户信息失败') }
      }
    },

    // 更新个人简介：用 PUT 提交 bio，成功后用后端返回的最新用户对象整体替换 userInfo。
    // 不做本地拼接，避免后端做了字段清洗时前端显示与数据库不一致。
    async updateUserBio(bio) {
      // 只提交 bio 一个字段，后端按字段做部分更新，不会覆盖用户名等其它资料。
      // 成功后用返回值整体替换，响应里若少了字段也能及时发现接口契约变化。
      if (!this.token) {
        return { success: false, message: '未登录' }
      }

      try {
        const response = await http.put('/user/update', { bio })
        if (response.data?.code === 200) {
          this.userInfo = response.data.data
          return { success: true, message: '更新个人简介成功' }
        }
        return { success: false, message: response.data?.message || '更新个人简介失败' }
      } catch (error) {
        console.error('更新个人简介请求失败:', error)
        return { success: false, message: errorMessage(error, '更新个人简介失败') }
      }
    },

    // 修改密码：需要同时提交旧密码和新密码，由后端校验旧密码是否正确。
    // 改密成功后后端会吊销旧 token，所以这里主动 logout，避免前端还拿着失效凭证继续发请求。
    async updatePassword(oldPassword, newPassword) {
      // 旧密码用于服务端鉴权，新密码强度校验也在后端，前端不重复实现规则。
      // 改密属于敏感操作，失败时保留登录态，用户可检查旧密码后重试。
      if (!this.token) {
        return { success: false, message: '未登录' }
      }

      try {
        const response = await http.put('/user/password', {
          oldPassword,
          newPassword,
        })
        if (response.data?.code === 200) {
          // 后端改密后会吊销所有 Token，前端同步退出登录。
          this.logout()
          return { success: true, message: '密码修改成功，请重新登录' }
        }
        return { success: false, message: response.data?.message || '密码修改失败' }
      } catch (error) {
        console.error('修改密码请求失败:', error)
        return { success: false, message: errorMessage(error, '修改密码失败') }
      }
    },
  },

  // pinia-plugin-persistedstate v4 的写法
  // pick 只持久化白名单字段：userInfo 可能含手机号等隐私，仍要存；但派生 getter 不存。
  // storage 默认是 localStorage（刷新后仍在），key 改成 user-store，http.js 读取 token 时也用这个键。
  // 只持久化必要字段，刷新后由 getUserInfoDetail 补齐；缓存过大也会拖慢启动。
  // 注意：localStorage 是明文，不能在这里存密码等敏感信息。
  persist: {
    key: 'user-store',
    storage: localStorage,
    pick: ['userInfo', 'token', 'isLogin', 'userBio'],
  },
})
