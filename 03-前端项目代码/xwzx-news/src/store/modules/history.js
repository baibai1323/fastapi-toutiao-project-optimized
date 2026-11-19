import { defineStore } from 'pinia'
import http, { errorMessage } from '../../config/http'
import { useUserStore } from '../user'

/**
 * 浏览历史。
 *
 * [优化] 原代码问题：
 *   1. 手写裸 Token，后端 401；
 *   2. 删除接口写成 /api/history/delete/{id}，后端实际是 DELETE /api/v1/history/{id}；
 *   3. 请求失败只提示“网络请求失败”，无法定位。
 * 修复：统一 http、修正 REST 路径、透传后端错误。
 */

export const useHistoryStore = defineStore('history', {
  state: () => ({
    history: [],
  }),

  getters: {
    getHistory: (state) => state.history,
  },

  actions: {
    async addHistoryApi(newsId) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录' }
      }

      try {
        const response = await http.post('/history/add', { newsId })
        if (response.data?.code === 200) {
          return { success: true, data: response.data.data }
        }
        return { success: false, message: response.data?.message || '添加浏览历史失败' }
      } catch (error) {
        console.error('添加浏览历史请求失败:', error)
        return { success: false, message: errorMessage(error, '添加浏览历史失败') }
      }
    },

    addHistory(news) {
      const existingIndex = this.history.findIndex((item) => item.id === news.id)
      if (existingIndex !== -1) {
        this.history.splice(existingIndex, 1)
      }

      this.history.unshift({
        ...news,
        viewTime: new Date().toLocaleString(),
      })

      if (this.history.length > 50) {
        this.history.pop()
      }
      this.saveHistory()
    },

    clearHistory() {
      this.history = []
      this.saveHistory()
    },

    async clearHistoryApi() {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        this.clearHistory()
        return { success: true, isLocal: true }
      }

      try {
        const response = await http.delete('/history/clear')
        if (response.data?.code === 200) {
          this.clearHistory()
          return { success: true }
        }
        return { success: false, message: response.data?.message || '清空浏览历史失败' }
      } catch (error) {
        console.error('清空浏览历史请求失败:', error)
        return { success: false, message: errorMessage(error, '清空浏览历史失败') }
      }
    },

    removeHistory(id) {
      this.history = this.history.filter((item) => item.id !== id)
      this.saveHistory()
    },

    async removeHistoryApi(id) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        this.removeHistory(id)
        return { success: true, isLocal: true }
      }

      try {
        // [优化] 后端是标准的 DELETE /history/{news_id}，不是 /history/delete/{id}
        const response = await http.delete(`/history/${id}`)
        if (response.data?.code === 200) {
          this.removeHistory(id)
          return { success: true }
        }
        return { success: false, message: response.data?.message || '删除浏览历史失败' }
      } catch (error) {
        console.error('删除浏览历史请求失败:', error)
        return { success: false, message: errorMessage(error, '删除浏览历史失败') }
      }
    },

    saveHistory() {
      localStorage.setItem('news_history', JSON.stringify(this.history))
    },

    loadHistory() {
      try {
        const savedHistory = localStorage.getItem('news_history')
        if (savedHistory) {
          this.history = JSON.parse(savedHistory)
        }
      } catch (error) {
        console.warn('读取本地浏览历史失败:', error)
      }
    },

    async getHistoryListApi() {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录', isLocal: true }
      }

      try {
        const response = await http.get('/history/list', {
          params: { page: 1, pageSize: 50 },
        })
        if (response.data?.code === 200) {
          const historyList = response.data.data.list || []
          this.history = historyList
          this.saveHistory()
          return { success: true, data: historyList }
        }
        return { success: false, message: response.data?.message || '获取浏览历史失败' }
      } catch (error) {
        console.error('获取浏览历史请求失败:', error)
        return { success: false, message: errorMessage(error, '获取浏览历史失败') }
      }
    },
  },
})
