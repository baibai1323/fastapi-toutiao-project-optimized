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

// 创建全局唯一实例：
// - baseURL 由“环境变量里的后端域名 + /api/v1 前缀”拼成，业务代码只写 /news/list 这样的相对路径；
// - timeout 设为 15 秒，避免后端无响应时请求一直挂着、页面永远转圈。
const http = axios.create({
  baseURL: `${apiConfig.baseURL}${apiConfig.apiPrefix}`,
  timeout: 15000,
})

// 从 localStorage 读取登录 token。
// token 由 user store 持久化在 user-store 这个 JSON 字符串里，所以要先 parse 再取字段。
// 任何解析失败（缓存损坏、旧格式）都返回空字符串，让请求以“未登录”身份继续，而不是直接抛错。
function readToken() {
  try {
    const raw = localStorage.getItem('user-store')
    if (!raw) return ''
    return JSON.parse(raw)?.token || ''
  } catch {
    return ''
  }
}

// 请求拦截器：每个请求发出前都会经过这里，统一补上 Authorization 头。
// 后端约定格式是 Bearer <token>，少了 Bearer 会被当成非法凭证而返回 401。
// 这里不直接 import user store，是为了避免 http 与 store 互相依赖形成循环引用。
http.interceptors.request.use((config) => {
  const token = readToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器：成功响应原样返回，失败响应先做全局兜底，再交给调用方处理。
// 401 表示“未登录或 token 失效”，此时清掉本地登录缓存并整页跳到登录页。
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

// 把 axios 异常整理成可展示的中文提示。
// 优先级：后端业务 message → 后端 detail（FastAPI 校验错误常用）→ 浏览器错误信息 → 调用方兜底文案。
// fallback 让每个页面能给出更贴合场景的提示，例如“登录失败”而不是笼统的“网络异常”。
export function errorMessage(error, fallback = '网络请求失败，请稍后再试') {
  return (
    error.response?.data?.message ||
    error.response?.data?.detail ||
    error.message ||
    fallback
  )
}

// 默认导出实例，业务模块统一 import http from '@/config/http'。
export default http
