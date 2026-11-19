/**
 * 统一 axios 实例。
 *
 * [优化] 原代码每个 store 直接 import axios、手写完整 URL、手写 Authorization：
 *     Authorization: userStore.token          // 少了 Bearer
 *     `${apiConfig.baseURL}/api/news/list`    // 路径散落各处
 * 问题：
 *     1. 后端要求 Bearer Token，原代码发裸 token，所有需要登录的接口都会 401；
 *     2. 没有统一 401 处理，Token 过期后页面一直报“网络请求失败”；
 *     3. baseURL/前缀散落，改版本号要全项目搜索。
 * 修复：统一实例 + 请求拦截器注入 Bearer + 响应拦截器处理 401。
 */

import axios from 'axios'
import { apiConfig } from './api'

const http = axios.create({
  baseURL: `${apiConfig.baseURL}${apiConfig.apiPrefix}`,
  timeout: 15000,
})

function readToken() {
  try {
    const raw = localStorage.getItem('user-store')
    if (!raw) return ''
    return JSON.parse(raw)?.token || ''
  } catch {
    return ''
  }
}

http.interceptors.request.use((config) => {
  const token = readToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const url = error.config?.url || ''
    // 登录/注册本身的 401/409 交给页面提示，不要触发全局跳转。
    const isAuthRequest = url.includes('/user/login') || url.includes('/user/register')

    if (status === 401 && !isAuthRequest) {
      localStorage.removeItem('user-store')
      if (window.location.pathname !== '/login') {
        // 用整页跳转清空 Pinia 内存状态，避免半登录状态继续发请求。
        window.location.assign('/login')
      }
    }
    return Promise.reject(error)
  }
)

export function errorMessage(error, fallback = '网络请求失败，请稍后再试') {
  return (
    error.response?.data?.message ||
    error.response?.data?.detail ||
    error.message ||
    fallback
  )
}

export default http
