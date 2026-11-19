/**
 * API 配置。
 *
 * [优化] 原代码把后端地址写死成 http://127.0.0.1:8000：
 *     baseURL: 'http://127.0.0.1:8000'
 * 问题：换环境要改代码，部署后也可能请求到用户自己的 localhost。
 * 修复：开发环境留空，走 Vite 的 /api 代理；生产用 VITE_API_BASE_URL 注入。
 */

const rawBaseURL = import.meta.env.VITE_API_BASE_URL || ''

export const apiConfig = {
  // 例如 https://api.example.com；为空时使用同源 + Vite 代理
  baseURL: rawBaseURL.replace(/\/$/, ''),
  apiPrefix: '/api/v1',
}

export const aiChatConfig = {
  model: 'qwen-plus',
}
