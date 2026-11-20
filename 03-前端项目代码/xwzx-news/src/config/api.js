/**
 * API 配置。
 *
 * [优化] 原代码把后端地址写死成 http://127.0.0.1:8000：
 *     baseURL: 'http://127.0.0.1:8000'
 * 问题：换环境要改代码，部署后也可能请求到用户自己的 localhost。
 * 修复：开发环境留空，走 Vite 的 /api 代理；生产用 VITE_API_BASE_URL 注入。
 */

const rawBaseURL = import.meta.env.VITE_API_BASE_URL || ''

// 后端接口的公共配置：http.js 会把 baseURL 和 apiPrefix 拼成完整前缀。
// baseURL 去掉末尾斜杠，避免出现 https://host//api/v1 这种双斜杠路径。
export const apiConfig = {
  // 例如 https://api.example.com；为空时使用同源 + Vite 代理
  baseURL: rawBaseURL.replace(/\/$/, ''),
  apiPrefix: '/api/v1',
}

// AI 对话使用的模型配置。
// model 是通义千问（Qwen）的模型标识，后端收到后会透传给大模型服务。
// 换模型（qwen-turbo 更便宜、qwen-max 更强）只改这一处，聊天组件无需改动。
export const aiChatConfig = {
  model: 'qwen-plus',
}
