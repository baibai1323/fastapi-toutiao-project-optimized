<template>
  <div class="news-item" @click="goToDetail">
    <div class="news-content">
      <h3 class="news-title">{{ news.title }}</h3>
      <p class="news-desc">{{ news.description }}</p>
      <div class="news-info">
        <span>{{ news.author }}</span>
        <span>{{ news.publishTime }}</span>
        <span>{{ news.views }} 阅读</span>
      </div>
    </div>
    <div class="news-image">
      <img :src="news.image" :alt="news.title">
    </div>
  </div>
</template>

/**
 * 新闻列表项组件：展示一条新闻的标题、摘要、作者、时间和阅读量。
 * 组件只负责“展示 + 点击跳转”，不请求接口；数据由父组件通过 props 传入。
 *
 * props（属性）：父组件传给子组件的数据，单向流动，子组件不应直接修改，
 * 这样数据来源始终唯一，列表刷新时不会出现父子状态不一致。
 *
 * 布局约定：左侧文字自适应剩余宽度，右侧图片固定 110×80，标题和摘要都限制两行，
 * 保证不同长度的新闻在列表中高度一致，滚动时不会忽高忽低。
 */
<script setup>
// 该组件是纯展示组件：不持有列表状态，也不发请求，父组件传什么就渲染什么。
// 这样同一个组件可以复用于首页、分类页、收藏页和历史页，减少重复模板。
// 点击事件绑定在根节点，整张卡片都是热区，移动端点击更容易命中。
import { defineProps } from 'vue'
import { useRouter } from 'vue-router'

// 声明接收的 news 对象。required: true 表示父组件必须传，否则 Vue 会在控制台警告。
// 这里没有写默认值，是为了尽早暴露“忘记传参”的调用错误。
const props = defineProps({
  news: {
    type: Object,
    required: true
  }
})

// useRouter 返回路由实例，用来做编程式导航（在 JS 里跳页面，而不是点 <router-link>）。
const router = useRouter()

// 点击整张卡片时进入详情页。详情页路由定义为 /news/detail/:id，
// 所以这里把新闻 id 拼进路径，详情页再用 route.params.id 取出来。
const goToDetail = () => {
  router.push(`/news/detail/${props.news.id}`)
}
</script>

<style scoped>
.news-item {
  display: flex;
  padding: 12px 16px;
  border-bottom: 1px solid #f2f2f2;
  background-color: #fff;
}

.news-content {
  flex: 1;
  margin-right: 12px;
  overflow: hidden;
}

.news-title {
  font-size: 16px;
  font-weight: 500;
  margin: 0 0 8px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.news-desc {
  font-size: 14px;
  color: #666;
  margin: 0 0 8px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.news-info {
  font-size: 12px;
  color: #999;
  display: flex;
}

.news-info span {
  margin-right: 10px;
}

.news-image {
  width: 110px;
  height: 80px;
  flex-shrink: 0;
}

.news-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
}
</style>