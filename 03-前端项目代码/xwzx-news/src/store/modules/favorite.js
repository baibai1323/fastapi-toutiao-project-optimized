import { defineStore } from 'pinia'
import http, { errorMessage } from '../../config/http'
import { useUserStore } from '../user'

/**
 * 收藏。
 *
 * [优化] 原代码问题：
 *   1. 手写 `Authorization: userStore.token`，没有 Bearer，后端全部 401；
 *   2. 列表接口因后端先 validate 后赋 favoriteId/favoriteTime 而 500；
 *   3. 错误统一吞成“网络请求失败”，看不到真实原因。
 * 修复：统一 http；后端已按完整字段构造响应；错误信息透传后端 message。
 */

export const useFavoriteStore = defineStore('favorite', {
  state: () => ({
    favorites: [],
    loading: false,
  }),

  getters: {
    getFavorites: (state) => state.favorites,
    isFavorite: (state) => (id) => state.favorites.some((item) => item.id === id),
  },

  actions: {
    async checkFavoriteStatusApi(newsId) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: true, isFavorite: this.isFavorite(newsId), isLocal: true }
      }

      try {
        const response = await http.get('/favorite/check', { params: { newsId } })
        if (response.data?.code === 200) {
          return { success: true, isFavorite: response.data.data.isFavorite }
        }
        return { success: false, message: response.data?.message || '获取收藏状态失败' }
      } catch (error) {
        console.error('检查收藏状态请求失败:', error)
        return { success: true, isFavorite: this.isFavorite(newsId), isLocal: true }
      }
    },

    async addFavoriteApi(newsId) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录' }
      }

      try {
        this.loading = true
        const response = await http.post('/favorite/add', { newsId })
        if (response.data?.code === 200) {
          return { success: true, data: response.data.data }
        }
        return { success: false, message: response.data?.message || '收藏失败' }
      } catch (error) {
        console.error('添加收藏请求失败:', error)
        return { success: false, message: errorMessage(error, '收藏失败') }
      } finally {
        this.loading = false
      }
    },

    async removeFavoriteApi(newsId) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录' }
      }

      try {
        this.loading = true
        const response = await http.delete('/favorite/remove', { params: { newsId } })
        if (response.data?.code === 200) {
          return { success: true }
        }
        return { success: false, message: response.data?.message || '取消收藏失败' }
      } catch (error) {
        console.error('取消收藏请求失败:', error)
        return { success: false, message: errorMessage(error, '取消收藏失败') }
      } finally {
        this.loading = false
      }
    },

    addFavorite(news) {
      if (!this.isFavorite(news.id)) {
        this.favorites.unshift({
          ...news,
          favoriteTime: new Date().toLocaleString(),
        })
        this.saveFavorites()
      }
    },

    removeFavorite(id) {
      this.favorites = this.favorites.filter((item) => item.id !== id)
      this.saveFavorites()
    },

    async toggleFavorite(news) {
      if (!news || !news.id) {
        console.error('无效的新闻对象:', news)
        return null
      }

      if (this.isFavorite(news.id)) {
        const result = await this.removeFavoriteApi(news.id)
        if (result.success) {
          this.removeFavorite(news.id)
          return false
        }
        return null
      }

      const result = await this.addFavoriteApi(news.id)
      if (result.success) {
        this.addFavorite(news)
        return true
      }
      return null
    },

    clearFavorites() {
      this.favorites = []
      this.saveFavorites()
    },

    async clearFavoritesApi() {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录' }
      }

      try {
        this.loading = true
        const response = await http.delete('/favorite/clear')
        if (response.data?.code === 200) {
          this.clearFavorites()
          return { success: true }
        }
        return { success: false, message: response.data?.message || '清空收藏失败' }
      } catch (error) {
        console.error('清空收藏请求失败:', error)
        return { success: false, message: errorMessage(error, '清空收藏失败') }
      } finally {
        this.loading = false
      }
    },

    saveFavorites() {
      localStorage.setItem('news_favorites', JSON.stringify(this.favorites))
    },

    loadFavorites() {
      try {
        const savedFavorites = localStorage.getItem('news_favorites')
        if (savedFavorites) {
          this.favorites = JSON.parse(savedFavorites)
        }
      } catch (error) {
        console.warn('读取本地收藏失败:', error)
      }
    },

    async getFavoriteListApi(page = 1, pageSize = 10) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录' }
      }

      try {
        this.loading = true
        const response = await http.get('/favorite/list', { params: { page, pageSize } })
        if (response.data?.code === 200) {
          const data = response.data.data
          const list = data.list || []
          this.favorites = page === 1 ? list : [...this.favorites, ...list]
          this.saveFavorites()
          return { success: true, data }
        }
        return { success: false, message: response.data?.message || '获取收藏列表失败' }
      } catch (error) {
        console.error('获取收藏列表请求失败:', error)
        return { success: false, message: errorMessage(error, '获取收藏列表失败') }
      } finally {
        this.loading = false
      }
    },
  },
})
