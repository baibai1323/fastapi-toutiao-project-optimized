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
 *
 * 这个 store 同时管理“登录后的云端收藏”和“游客的本地收藏”，因此方法分成两类：
 * 以 Api 结尾的会请求后端，没有 Api 后缀的只操作本地数组和 localStorage。
 * 页面不应混用两类方法，否则会出现“界面已收藏、服务端却没有”的不一致。
 */

// 模块约定：
// - “收藏”在登录后以服务端为准，未登录时退回本地收藏，保证游客也能试用；
// - 本地缓存键固定为 news_favorites，存的是新闻对象数组，刷新页面后可立即展示；
// - API 方法统一返回 { success, message }，组件据此决定是否弹 Toast，不直接 catch axios 错误。
export const useFavoriteStore = defineStore('favorite', {
  // favorites 同时服务于“游客本地收藏”和“登录用户服务端收藏”，两种模式共用同一份列表结构。
  // loading 表示有写操作正在进行，页面可用它禁用按钮，防止连续点击重复提交。
  // 不持久化 loading：它只是请求过程中的临时标志，刷新后应回到 false。
  state: () => ({
    // 数组元素是完整新闻对象，列表页可直接复用 NewsItem 渲染，不必再按 id 回查。
    favorites: [],
    loading: false,
  }),

  // getters 里不直接改 favorites：isFavorite 返回一个函数，调用时才按 id 判断，
  // 这样模板里可以写成 isFavorite(news.id)，而不必每次手动遍历。
  // 注意使用方法式 getter 会失去缓存，但收藏列表很小，可读性比这点性能更重要。
  getters: {
    getFavorites: (state) => state.favorites,
    // 返回数组本身而不是副本：列表页只读渲染，复制反而增加一次遍历。
    // some 找到第一条就返回，比 filter 后再判断 length 更省内存。
    isFavorite: (state) => (id) => state.favorites.some((item) => item.id === id),
  },

  actions: {
    // 每个 action 内部自行获取 userStore，而不是在文件顶部创建：
    // Pinia 要求 store 在 app.use(pinia) 之后才能实例化，模块加载阶段调用会报错。
    // 查询某条新闻是否已收藏。
    // 未登录时不请求后端，直接用本地列表判断，并通过 isLocal 告诉调用方“这是本地结果”。
    // 请求异常也退回本地判断：收藏状态是弱一致数据，不值得让页面报错。
    async checkFavoriteStatusApi(newsId) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: true, isFavorite: this.isFavorite(newsId), isLocal: true }
      }

      try {
        // 成功分支不返回 isLocal，调用方据此区分“服务端权威结果”和“本地兜底结果”。
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

    // 添加收藏（服务端）。必须先登录：后端按 token 识别用户，游客没有可写入的账户。
    // loading 在 finally 中复位，保证即使请求抛异常，按钮也不会永久卡在禁用状态。
    async addFavoriteApi(newsId) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录' }
      }

      try {
        this.loading = true
        // 只传 newsId 而不是整个 news 对象：后端只需 id 就能定位新闻，传多余字段会扩大接口契约。
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

    // 取消收藏（服务端）。用 DELETE 并把 newsId 放在 query 参数里，与后端路由定义保持一致。
    // 同样用 loading 包裹写操作，避免用户快速连点导致重复删除。
    async removeFavoriteApi(newsId) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录' }
      }

      try {
        this.loading = true
        // DELETE 的 query 参数用 { params } 传递，axios 会拼成 /favorite/remove?newsId=1。
        // 若写成请求体，部分后端框架不会解析 DELETE body，导致 newsId 收不到。
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

    // 写入本地收藏列表（不请求后端）。
    // unshift 把最新收藏放到最前面，符合“刚收藏的应该先看到”的预期；
    // favoriteTime 只用于本地展示，服务端列表会用自己的时间字段覆盖。
    addFavorite(news) {
      if (!this.isFavorite(news.id)) {
        this.favorites.unshift({
          // 列表接口返回的字段可能比本地缓存多，整体展开可保留服务端的收藏时间等元数据。
          ...news,
          favoriteTime: new Date().toLocaleString(),
        })
        this.saveFavorites()
      }
    },

    // 从本地列表移除：filter 会生成新数组再赋回，Pinia 能感知整体替换并触发视图更新。
    // 这里只删内存和本地缓存；要同步服务端请调用 removeFavoriteApi。
    removeFavorite(id) {
      // 用 !== 过滤，兼容 id 为数字或字符串两种来源（本地缓存与接口返回可能类型不同）。
      this.favorites = this.favorites.filter((item) => item.id !== id)
      this.saveFavorites()
    },

    // 收藏/取消收藏的总入口，供页面按钮直接调用。
    // 先看本地状态决定这次是“加”还是“减”，再等接口成功后才更新本地：
    // 接口失败返回 null，页面就不应改变心形图标，避免“界面显示已收藏、服务端其实没有”。
    async toggleFavorite(news) {
      // 先做入参校验：列表项偶尔可能来自缓存而缺少 id，直接发请求会得到 422。
      if (!news || !news.id) {
        console.error('无效的新闻对象:', news)
        return null
      }

      if (this.isFavorite(news.id)) {
        // 已收藏则走取消；只有接口成功才移除本地项，失败保持原状让用户重试。
        const result = await this.removeFavoriteApi(news.id)
        if (result.success) {
          this.removeFavorite(news.id)
          return false
        }
        return null
      }

      const result = await this.addFavoriteApi(news.id)
      if (result.success) {
        // 服务端写入成功后才落本地，避免离线时产生“仅本地可见”的收藏。
        // addFavorite 内部还会按 id 去重，防止快速连点导致列表出现两条相同新闻。
        this.addFavorite(news)
        return true
      }
      return null
    },

    // 清空本地收藏。只影响当前设备，不会删除服务端数据；
    // 登录用户要清空云端收藏应调用 clearFavoritesApi。
    // 先赋空数组再写缓存，两步都同步执行，不存在只清一半的中间态。
    clearFavorites() {
      this.favorites = []
      this.saveFavorites()
    },

    // 清空服务端收藏。未登录直接拒绝，因为没有账户可清空。
    // 后端成功后才调用 clearFavorites() 同步本地，保证两边不会一边空一边有。
    async clearFavoritesApi() {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录' }
      }

      try {
        this.loading = true
        // 先清服务端再清本地：如果顺序反过来，服务端失败时本地已空，用户会以为收藏丢了。
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

    // 把收藏数组序列化成 JSON 存入 localStorage。
    // localStorage 只能存字符串，所以必须先 JSON.stringify；读取时再 parse 回来。
    // 每次增删后立即写入，不依赖页面卸载事件，避免用户直接关标签页导致最后一步丢失。
    saveFavorites() {
      localStorage.setItem('news_favorites', JSON.stringify(this.favorites))
    },

    // 从 localStorage 恢复收藏。
    // 解析可能因为旧版本数据格式或手工改动而失败，因此 try/catch 后只告警不清空：
    // 保留原缓存，用户还有机会通过清缓存或重新收藏恢复，不会静默丢数据。
    // 读取只发生在应用启动时，不需要额外加锁。
    loadFavorites() {
      try {
        // key 必须和 saveFavorites 中的 'news_favorites' 完全一致，拼错会表现为“收藏刷新后消失”。
        const savedFavorites = localStorage.getItem('news_favorites')
        if (savedFavorites) {
          this.favorites = JSON.parse(savedFavorites)
        }
      } catch (error) {
        console.warn('读取本地收藏失败:', error)
      }
    },

    // 分页拉取服务端收藏列表。
    // page === 1 视为刷新，直接替换列表；否则把新一页追加到后面，供上拉加载更多使用。
    // 拉取成功后立刻 saveFavorites()，让离线/刷新场景也能看到最近一次的服务端数据。
    async getFavoriteListApi(page = 1, pageSize = 10) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录' }
      }

      try {
        this.loading = true
        // 服务端分页参数与列表页保持一致（默认第 1 页、每页 10 条），避免两处页大小不同步。
        const response = await http.get('/favorite/list', { params: { page, pageSize } })
        if (response.data?.code === 200) {
          const data = response.data.data
          const list = data.list || []
          // 第一页用服务端结果覆盖本地，避免旧缓存残留；后续页只追加，保留已加载内容。
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
