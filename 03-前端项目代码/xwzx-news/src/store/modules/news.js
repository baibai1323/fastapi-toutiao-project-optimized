import { defineStore } from 'pinia'
import http, { errorMessage } from '../../config/http'

/**
 * 新闻列表 / 详情。
 *
 * [优化] 原代码问题：
 *   1. 文件在 :230 已经结束 store，却又多写了一个 changeCategory，
 *      形成语法级重复定义，构建/维护都容易出错；
 *   2. 请求全部手写完整 URL；
 *   3. 分类写死追加 {id:10,name:'更多'}，和 Home 的“更多”入口重复；
 *   4. 详情 GET 曾经顺带 +1 浏览量，GET 不幂等；
 *   5. 用 newsData.length < pageSize 判断结束，遇到后端过滤/限流会误判。
 * 修复：统一 http、去掉 mock 死代码、用后端 hasMore 判断、浏览单独 POST。
 */

export const useNewsStore = defineStore('news', {
  state: () => ({
    newsList: [],
    newsDetail: {},
    categories: [],
    currentCategory: 1,
    loading: false,
    refreshing: false,
    finished: false,
    categoriesLoading: false,
  }),

  actions: {
    async getCategories() {
      if (this.categoriesLoading) return

      this.categoriesLoading = true
      try {
        const response = await http.get('/news/categories')
        if (response.data?.code === 200) {
          this.categories = response.data.data || []
          if (!this.currentCategory && this.categories.length > 0) {
            this.currentCategory = this.categories[0].id
          }
        }
      } catch (error) {
        console.error('获取新闻分类失败:', error)
        // 后端不可用时至少保证页面还能渲染出 Tab。
        this.categories = [
          { id: 1, name: '头条' },
          { id: 2, name: '社会' },
          { id: 3, name: '国内' },
          { id: 4, name: '国际' },
          { id: 5, name: '娱乐' },
          { id: 6, name: '体育' },
          { id: 7, name: '科技' },
          { id: 8, name: '财经' },
        ]
      } finally {
        this.categoriesLoading = false
      }
    },

    changeCategory(categoryId) {
      if (this.currentCategory === categoryId) return
      this.currentCategory = categoryId
      this.newsList = []
      this.finished = false
      return this.getNewsList(true)
    },

    async getNewsList(isRefresh = false) {
      // 注意：不要在这里判断 this.loading/this.refreshing。
      // Vant 的 van-list / van-pull-refresh 会先通过 v-model 把标志置为 true，
      // 再触发 @load/@refresh；如果这里提前 return，列表永远加载不出下一页。
      if (isRefresh) {
        this.refreshing = true
        this.newsList = []
        this.finished = false
      } else {
        this.loading = true
      }

      try {
        const page = isRefresh ? 1 : Math.floor(this.newsList.length / 10) + 1
        const response = await http.get('/news/list', {
          params: {
            categoryId: this.currentCategory || undefined,
            page,
            pageSize: 10,
          },
        })

        if (response.data?.code === 200) {
          const data = response.data.data
          const newsData = data.list || []
          this.newsList = isRefresh ? newsData : [...this.newsList, ...newsData]
          // 后端按 total 计算，不会因为某页刚好 10 条就误判结束。
          this.finished = !data.hasMore
        }
      } catch (error) {
        console.error('获取新闻列表失败:', error)
      } finally {
        this.loading = false
        this.refreshing = false
      }
    },

    async getNewsDetail(id) {
      try {
        const response = await http.get('/news/detail', { params: { id } })
        if (response.data?.code === 200) {
          this.newsDetail = response.data.data
          return { success: true, data: this.newsDetail }
        }
        return { success: false, message: response.data?.message || '获取新闻详情失败' }
      } catch (error) {
        console.error('获取新闻详情失败:', error)
        return { success: false, message: errorMessage(error, '获取新闻详情失败') }
      }
    },

    /**
     * 显式记录浏览。
     * [优化] 原来浏览量的 +1 藏在 GET /detail 里：
     *   爬虫、预取、刷新都会灌水，而且 GET 不是幂等操作。
     *   现在拆成 POST，并且失败不影响详情展示。
     */
    async recordView(id) {
      try {
        const response = await http.post(`/news/${id}/view`)
        if (response.data?.code === 200) {
          const views = response.data.data.views
          if (this.newsDetail?.id === Number(id)) {
            this.newsDetail = { ...this.newsDetail, views }
          }
          return views
        }
      } catch (error) {
        // 浏览量失败不打断阅读，只记日志。
        console.warn('记录浏览量失败:', error)
      }
      return null
    },

    getCategoryName(categoryId) {
      const category = this.categories.find((item) => item.id === categoryId)
      return category ? category.name : '未知'
    },
  },
})
