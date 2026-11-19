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

export const useUserStore = defineStore('user', {
  state: () => ({
    userInfo: null,
    token: '',
    isLogin: false,
    userBio: '这是我的个人简介',
  }),

  getters: {
    getUserInfo: (state) => state.userInfo,
    getToken: (state) => state.token,
    getLoginStatus: (state) => state.isLogin,
    getUserBio: (state) => state.userInfo?.bio || state.userBio,
  },

  actions: {
    async login(userData) {
      try {
        const response = await http.post('/user/login', {
          username: userData.username,
          password: userData.password,
        })

        if (response.data?.code === 200) {
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

    async register(userData) {
      try {
        const response = await http.post('/user/register', {
          username: userData.username,
          password: userData.password,
        })

        if (response.data?.code === 200) {
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

    logout() {
      // [优化] 原代码只清本地，服务端 Token 仍然有效。
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

    async getUserInfoDetail() {
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

    async updateUserBio(bio) {
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

    async updatePassword(oldPassword, newPassword) {
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
  persist: {
    key: 'user-store',
    storage: localStorage,
    pick: ['userInfo', 'token', 'isLogin', 'userBio'],
  },
})
