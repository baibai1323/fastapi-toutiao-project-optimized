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
 *
 * 本模块只负责“新闻数据”本身：分类、列表、详情、浏览量。
 * 收藏和浏览历史各自独立成 store，避免新闻模块越来越臃肿，也方便单独复用。
 */

// 业务约定：
// - currentCategory 用数字 id 表示当前栏目，1 是默认“头条”；
// - 列表分页由后端 hasMore 决定是否还有下一页，前端不靠“返回条数是否满 10 条”猜测；
// - 所有接口失败都只影响当前模块，页面仍尽量用兜底数据渲染，不把异常抛到全局。
export const useNewsStore = defineStore('news', {
  // state 同时保存列表、详情和加载标志；loading / refreshing 分开，是为了让 Vant 的下拉刷新和上拉加载互不干扰。
  // finished 为 true 时列表底部显示“没有更多了”，并停止继续触发加载。
  state: () => ({
    // 列表与详情分开存：列表用于滚动渲染，详情用于详情页，互不覆盖。
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
    // 获取栏目分类。categoriesLoading 起到“请求锁”的作用：
    // 页面可能在多个组件里同时调用，重复请求既浪费流量，也可能让后返回的旧数据覆盖新数据。
    // 分类是全局导航的基础数据，失败时用内置列表兜底，保证首屏至少有可点的栏目。
    async getCategories() {
      if (this.categoriesLoading) return

      this.categoriesLoading = true
      try {
        const response = await http.get('/news/categories')
        if (response.data?.code === 200) {
          // 后端返回空数组时保留当前分类，不要把它改成 undefined，否则列表请求会丢掉分类条件。
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

    // 切换栏目：同一个栏目重复点击直接返回，避免无意义地清空列表重新请求。
    // 切换后必须清空旧列表并把 finished 复位，否则新栏目会接着旧页码加载、或直接显示“没有更多”。
    // 这里返回 Promise，页面可以 await 后在 finally 里关闭自己的 loading 状态。
    changeCategory(categoryId) {
      if (this.currentCategory === categoryId) return
      this.currentCategory = categoryId
      this.newsList = []
      this.finished = false
      return this.getNewsList(true)
    },

    // 获取新闻列表。isRefresh 为 true 表示下拉刷新（回到第 1 页并清空旧数据），
    // 为 false 表示上拉加载下一页（把新数据追加到现有列表后面）。
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
        // 页码按“已加载条数 / 每页 10 条”反推：第 1 页加载 10 条后，下一请求就是第 2 页。
        // 10 必须和下面 pageSize 保持一致，否则会出现跳页或重复数据。
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

    // 获取新闻详情。只负责取数据，不在这里记浏览量；
    // 浏览量拆到 recordView()，因为 GET 应当幂等，刷新详情页不应该把阅读数越刷越高。
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
      // 详情页拿到 id 后调用一次即可；重复调用会产生多条浏览记录，计数由后端按用户/时间去重。
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

    // 把分类 id 翻译成显示名称。找不到时返回“未知”而不是抛错，
    // 因为分类列表可能还没加载完，详情页不应因此白屏。
    getCategoryName(categoryId) {
      const category = this.categories.find((item) => item.id === categoryId)
      return category ? category.name : '未知'
    },
  },
})
