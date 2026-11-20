<template>
  <div class="news-detail">
    <van-nav-bar
      title="新闻详情"
      left-text="返回"
      left-arrow
      @click-left="onClickLeft"
      fixed
    />
    
    <div class="detail-content" v-if="newsStore.newsDetail.id">
      <div class="title-container">
        <h1 class="title">{{ newsStore.newsDetail.title }}</h1>
        <van-button 
          class="favorite-btn" 
          :icon="isFavorite ? 'star' : 'star-o'" 
          :class="{ 'is-favorite': isFavorite }"
          @click="toggleFavorite"
        />
      </div>
      
      <div class="info">
        <span>{{ newsStore.newsDetail.author }}</span>
        <span>{{ newsStore.newsDetail.publishTime }}</span>
        <span>{{ newsStore.newsDetail.views }} 阅读</span>
      </div>
      
      <div class="cover" v-if="newsStore.newsDetail.image">
        <img :src="newsStore.newsDetail.image" :alt="newsStore.newsDetail.title">
      </div>
      
      <div class="content">
        <p v-for="(paragraph, index) in contentParagraphs" :key="index">
          {{ paragraph }}
        </p>
      </div>
      
      <div class="related-news" v-if="newsStore.newsDetail.relatedNews?.length">
        <h3>相关推荐</h3>
        <div class="related-list">
          <div 
            class="related-item" 
            v-for="item in newsStore.newsDetail.relatedNews" 
            :key="item.id"
            @click="goToRelatedNews(item.id)"
          >
            <div class="related-image">
              <img :src="item.image" :alt="item.title">
            </div>
            <div class="related-title">{{ item.title }}</div>
          </div>
        </div>
      </div>
    </div>
    
    <van-empty v-else description="加载中..." />
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useNewsStore } from '../store/modules/news'
import { useHistoryStore } from '../store/modules/history'
import { useFavoriteStore } from '../store/modules/favorite'
import { useUserStore } from '../store/user'
import { showToast } from 'vant'

// 详情页依赖四块共享状态：新闻详情、浏览历史、收藏、登录用户。
// 它们都由 Pinia 仓库统一管理，所以别的页面加过的收藏/历史，这里能立刻读到。
const route = useRoute()
const router = useRouter()
const newsStore = useNewsStore()
const historyStore = useHistoryStore()
const favoriteStore = useFavoriteStore()
const userStore = useUserStore()

// 获取路由参数中的新闻ID
// 地址栏里的参数都是字符串，Number(...) 转成数字后和后端 id 类型一致，比较才不会失败。
const newsId = computed(() => Number(route.params.id))

// 将内容拆分为段落
// 后端正文用两个换行分段，这里按 "\n\n" 切开，模板就能一段一个 <p> 排版。
const contentParagraphs = computed(() => {
  if (!newsStore.newsDetail.content) return []
  // filter 去掉空段落，否则页面上会出现没有文字的空行。
  return newsStore.newsDetail.content.split('\n\n').filter(p => p.trim())
})

// 返回上一页
// 用 back() 而不是 push('/')，用户按返回键能回到原来那一页，不会多一层历史。
const onClickLeft = () => {
  router.back()
}

// 跳转到相关新闻
// 相关新闻仍是详情页，只是路由里的 id 换成另一篇，组件会复用、重新发请求。
const goToRelatedNews = (id) => {
  router.push(`/news/detail/${id}`)
}

// 判断当前新闻是否已收藏
// 用计算属性是因为收藏列表一变就要重算，模板里的星星图标才能跟着切换。
const isFavorite = computed(() => {
  return favoriteStore.isFavorite(newsId.value)
})

// 切换收藏状态
// 收藏属于个人数据，服务端要求带上登录凭证，所以未登录必须先拦下来，不然请求会 401。
const toggleFavorite = async () => {
  // 判断用户是否已登录
  if (!userStore.getLoginStatus) {
    // 未登录则跳转到登录页
    showToast({
      message: '请先登录后再收藏',
      position: 'bottom',
    })
    router.push('/login')
    return
  }
  
  // 已登录则调用API切换收藏状态
  // 返回值有三种：true=刚收藏、false=刚取消、null=请求失败，下面据此给不同提示。
  const status = await favoriteStore.toggleFavorite(newsStore.newsDetail)
  
  if (status === true) {
    showToast({
      message: '已添加到收藏',
      position: 'bottom',
    })
  } else if (status === false) {
    showToast({
      message: '已取消收藏',
      position: 'bottom',
    })
  } else {
    // status为null表示操作失败
    showToast({
      message: '操作失败，请稍后重试',
      position: 'bottom',
    })
  }
}

// 组件挂载时获取新闻详情并添加到浏览历史
// onMounted 是“页面显示到屏幕上之后执行一次”的钩子，适合放首屏请求。
onMounted(async () => {
  // 先拿详情：模板只有拿到 id 才渲染正文，没拿到就一直显示“加载中...”。
  await newsStore.getNewsDetail(newsId.value)
  
  // [优化] 浏览量从 GET /detail 中拆出来，改为显式 POST /news/{id}/view。
  // GET 保持幂等，爬虫/预取不会灌水；失败也不影响阅读。
  if (newsStore.newsDetail.id) {
    await newsStore.recordView(newsStore.newsDetail.id)
  }

  // 添加到浏览历史
  if (newsStore.newsDetail.id) {
    // 先调用API记录浏览历史
    // 历史记录分两路：登录用户存到服务端（换设备也能看到），未登录只留本地。
    if (userStore.getLoginStatus) {
      try {
        const result = await historyStore.addHistoryApi(newsStore.newsDetail.id);
        console.log('记录浏览历史API结果:', result);
      } catch (error) {
        // 上报失败只打日志：历史只是辅助功能，不能因为它出错就不让用户看新闻。
        console.error('记录浏览历史API失败:', error);
      }
    }
    
    // 无论API是否成功，都添加到本地浏览历史
    // historyStore.addHistory(newsStore.newsDetail);
  }
  
  // 加载收藏数据
  // 先把本地缓存的收藏读出来，页面立刻能显示正确的星星状态，不用等下面接口。
  favoriteStore.loadFavorites()
  
  // 检查文章收藏状态
  // 再用服务端结果校正本地：用户可能换了设备，本地缓存未必是准确的。
  if (userStore.getLoginStatus && newsStore.newsDetail.id) {
    const result = await favoriteStore.checkFavoriteStatusApi(newsStore.newsDetail.id)
    // isLocal=true 表示这只是本地兜底结果，并不代表服务端真实状态，不能拿来覆盖。
    if (result.success && !result.isLocal) {
      // 如果API请求成功且不是本地状态，更新本地收藏状态
      // 服务端说已收藏而本地没有，就补一条；反过来就删掉，保证两边最终一致。
      if (result.isFavorite && !favoriteStore.isFavorite(newsStore.newsDetail.id)) {
        favoriteStore.addFavorite(newsStore.newsDetail)
      } else if (!result.isFavorite && favoriteStore.isFavorite(newsStore.newsDetail.id)) {
        favoriteStore.removeFavorite(newsStore.newsDetail.id)
      }
    }
  }
})
</script>

<style scoped>
.news-detail {
  padding-top: 46px;
  background-color: #fff;
  min-height: 100vh;
}

.detail-content {
  padding: 16px;
}

.title-container {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 12px;
}

.title {
  font-size: 22px;
  font-weight: bold;
  line-height: 1.4;
  margin: 0;
  flex: 1;
}

.favorite-btn {
  flex-shrink: 0;
  margin-left: 10px;
  padding: 0;
  width: 36px;
  height: 36px;
  border-radius: 50%;
}

.favorite-btn.is-favorite {
  color: #ff9500;
}

.info {
  display: flex;
  font-size: 12px;
  color: #999;
  margin-bottom: 16px;
}

.info span {
  margin-right: 12px;
}

.cover {
  margin-bottom: 16px;
}

.cover img {
  width: 100%;
  border-radius: 4px;
}

.content {
  font-size: 16px;
  line-height: 1.8;
  color: #333;
}

.content p {
  margin-bottom: 16px;
  text-align: justify;
}

.related-news {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 8px solid #f5f5f5;
}

.related-news h3 {
  font-size: 18px;
  margin: 0 0 16px;
}

.related-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.related-item {
  display: flex;
  align-items: center;
}

.related-image {
  width: 80px;
  height: 60px;
  margin-right: 12px;
  flex-shrink: 0;
}

.related-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
}

.related-title {
  font-size: 14px;
  line-height: 1.4;
  flex: 1;
}
</style>