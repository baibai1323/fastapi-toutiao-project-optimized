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
 *
 * 历史记录和收藏一样有“本地/云端”两套数据源：
 * 游客读写本地数组，登录用户以服务端为准；切换账号时应先清空本地旧账号的历史，防止串号。
 */

// 模块约定：
// - 历史记录是“最近看过的新闻”，同一篇只保留一条，再次阅读会把它移到最前面；
// - 最多保留 50 条，超出就丢掉最旧的一条，防止 localStorage 无限增长；
// - 未登录时只在本地记录，登录后才与服务端同步，保证游客也能看到浏览历史。
export const useHistoryStore = defineStore('history', {
  // history 按“最近浏览在前”排序；只存展示所需字段，不存整篇正文，节省本地空间。
  // 没有 loading 标志：历史写入是“顺手记录”，失败也不应打断用户阅读，页面无需展示加载态。
  state: () => ({
    // 数组顺序就是展示顺序，第 0 条永远是最新浏览；排序逻辑集中在 addHistory 里。
    history: [],
  }),

  // 只读 getter，页面通过它拿列表，避免直接改数组导致排序和缓存不一致。
  // 如果页面需要过滤/搜索，应在组件里基于这份数据做 computed，不要改 store 原数组。
  getters: {
    getHistory: (state) => state.history,
  },

  actions: {
    // 和收藏模块一样，userStore 必须在使用时获取，不能在模块顶层实例化。
    // “添加”接口只负责上报，不返回完整列表；本地列表由 addHistory 另行维护。
    // 向服务端添加一条浏览记录。未登录直接拒绝，因为历史是按账户存储的。
    // 同一篇新闻重复阅读由后端决定是更新还是忽略，前端只负责提交。
    async addHistoryApi(newsId) {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录' }
      }

      try {
        // 只上报 newsId，浏览时间由后端统一生成，避免客户端时间不准导致排序错乱。
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

    // 写入本地历史（不请求后端）。
    // 先找到同 id 的旧记录并删除，再 unshift 到最前面，实现“最近阅读置顶”。
    // 最后裁剪到 50 条，并立即持久化，避免刷新页面丢失。
    addHistory(news) {
      // news 可能来自列表页，字段不完整但至少有 id 和 title；这里不做校验，保持记录动作轻量。
      const existingIndex = this.history.findIndex((item) => item.id === news.id)
      if (existingIndex !== -1) {
        this.history.splice(existingIndex, 1)
      }

      this.history.unshift({
        // 先展开新闻字段，再写入 viewTime：同名字段以后者为准，确保展示的是本次浏览时间。
        ...news,
        viewTime: new Date().toLocaleString(),
      })

      // 超出 50 条就丢弃末尾最旧的一条；50 是本地缓存上限，避免 localStorage 无限膨胀。
      // 只 pop 一条而不是截断整个数组，保证每次新增只淘汰最旧记录，其余顺序不变。
      if (this.history.length > 50) {
        this.history.pop()
      }
      this.saveHistory()
    },

    // 清空本地历史并同步到 localStorage；不会调用服务端接口。
    // 这里同步清空是安全的：localStorage.removeItem 失败也不会留下半条记录。
    clearHistory() {
      // 先清内存数组，再清持久化；两步都是同步操作，页面不会看到“列表已空但缓存还在”的中间态。
      this.history = []
      this.saveHistory()
    },

    // 清空服务端历史。未登录时没有云端数据，直接清本地并返回 isLocal，
    // 这样游客点“清空”也能得到成功反馈，而不是“请先登录”。
    async clearHistoryApi() {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        this.clearHistory()
        return { success: true, isLocal: true }
      }

      try {
        const response = await http.delete('/history/clear')
        if (response.data?.code === 200) {
          // 只有服务端确认清空后才动本地，避免接口失败但界面已经变空。
          this.clearHistory()
          return { success: true }
        }
        return { success: false, message: response.data?.message || '清空浏览历史失败' }
      } catch (error) {
        console.error('清空浏览历史请求失败:', error)
        return { success: false, message: errorMessage(error, '清空浏览历史失败') }
      }
    },

    // 从本地列表删除一条，filter 生成新数组以便 Pinia 感知变化，然后立即写回缓存。
    removeHistory(id) {
      this.history = this.history.filter((item) => item.id !== id)
      this.saveHistory()
    },

    // 删除服务端历史。未登录时降级为只删本地，保证按钮始终可用。
    // 登录状态下先删服务端，成功后再删本地，避免本地删了但服务端还在、下次登录又冒出来。
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

    // 序列化后写入 localStorage。键名 news_history 与读取处必须保持一致。
    // 每次变更都立即写入，不等到页面关闭，避免移动端进程被系统回收时丢记录。
    saveHistory() {
      localStorage.setItem('news_history', JSON.stringify(this.history))
    },

    // 从本地缓存恢复历史。JSON.parse 可能因旧格式或手工修改失败，
    // 这里捕获后只告警，保留原缓存不覆盖，避免一次解析失败就永久丢历史。
    // 恢复后不再排序：缓存本身已按浏览顺序保存，二次排序反而可能打乱同一秒内的记录。
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

    // 拉取服务端历史列表，固定取第 1 页 50 条：与本地上限保持一致，
    // 这样“登录后看到的历史”不会因为分页只显示一部分而和退出前不一致。
    // 未登录返回 isLocal，调用方据此继续展示本地历史而不报错。
    async getHistoryListApi() {
      const userStore = useUserStore()
      if (!userStore.getLoginStatus) {
        return { success: false, message: '请先登录', isLocal: true }
      }

      try {
        // 登录用户最多也只取 50 条，和本地上限一致；超出部分对用户没有展示价值。
        const response = await http.get('/history/list', {
          params: { page: 1, pageSize: 50 },
        })
        if (response.data?.code === 200) {
          // 服务端返回空列表时也覆盖本地，表示云端确实没有记录，而不是保留旧账号的缓存。
          const historyList = response.data.data.list || []
          this.history = historyList
          // 立刻写回缓存，下次离线打开也能看到最近一次从服务端同步的历史。
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
