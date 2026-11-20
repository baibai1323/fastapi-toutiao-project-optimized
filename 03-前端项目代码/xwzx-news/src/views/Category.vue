<template>
  <div class="category">
    <van-nav-bar 
      :title="$t('common.allCategories')" 
      :left-text="$t('common.back')"
      left-arrow
      @click-left="onClickLeft"
      fixed 
    />
    
    <div class="category-container">
      <van-grid :column-num="3" :border="false">
        <van-grid-item 
          v-for="category in displayCategories" 
          :key="category.id"
          :text="getCategoryTranslation(category.name)"
          icon="newspaper-o"
          @click="goToCategoryNews(category.id)"
        />
      </van-grid>
    </div>
    
    <tab-bar />
  </div>
</template>

<script setup>
// 分类总览页：用三列宫格列出所有分类，点任意一项就回首页并切到该分类。
// 数据仍复用首页那份 Pinia 仓库，两处不会出现“分类列表不一致”的问题。
import { useNewsStore } from '../store/modules/news'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import TabBar from '../components/TabBar.vue'
import { computed } from 'vue'

// router 负责跳转，t 是 i18n 的翻译函数，切换语言后文案会自动变。
const newsStore = useNewsStore()
const router = useRouter()
const { t } = useI18n()

// 计算属性（computed）：由别的数据推导出来的值，依赖变化时它会自动重算。
// 计算属性：显示的分类（只显示非"更多"分类）
const displayCategories = computed(() => {
  // “更多”只是首页的跳转按钮，本身不是一个分类，总览页要把它过滤掉。
  return newsStore.categories.filter(category => category.name !== '更多');
})

// 返回上一页
// 用 back() 而不是写死跳首页，用户从哪里进来就回到哪里，符合直觉。
const onClickLeft = () => {
  router.back()
}

// 跳转到对应分类的新闻列表
// 这里做两件事：先让仓库记住新分类，再带着分类 id 跳回首页。
// 只跳转不记状态的话，首页 watch 读到的可能还是旧分类，列表会闪一下。
const goToCategoryNews = (categoryId) => {
  // 先切换分类
  newsStore.changeCategory(categoryId)
  
  // 使用路由参数传递分类ID
  // query 是地址栏 ? 后面的部分；写进 query 后刷新页面还能从地址里读回分类。
  router.push({
    path: '/home',
    query: { categoryId: categoryId }
  })
}

// 获取分类名称的翻译
// 分类名是后端返回的中文，转成 i18n 的 key 后，切英文时分类名才会跟着变。
const getCategoryTranslation = (categoryName) => {
  // 这张表是“中文分类名 → i18n key”的对照；后端新增分类时要在这里补一行，否则显示原文。
  const categoryMap = {
    '头条': 'headline',
    '社会': 'society',
    '国内': 'domestic',
    '国际': 'international',
    '娱乐': 'entertainment',
    '体育': 'sports',
    '军事': 'military',
    '科技': 'technology',
    '财经': 'finance',
    '更多': 'more'
  };
  
  // 映射表里没有的新分类会拿到 undefined，下面会原样显示中文，不会变成空白。
  const key = categoryMap[categoryName];
  // 有 key 就走翻译，没有 key 就退回后端给的原始名字，保证永远有字可显示。
  return key ? t(`home.categories.${key}`) : categoryName;
}
</script>

<style scoped>
.category {
  padding-top: 46px;
  padding-bottom: 50px;
  background-color: #f7f8fa;
  min-height: 100vh;
}

.category-container {
  padding: 16px;
  background-color: #fff;
  margin-top: 12px;
  border-radius: 8px;
}

:deep(.van-grid-item__content) {
  background-color: #f5f7fa;
  border-radius: 8px;
  padding: 20px 0;
}

:deep(.van-grid-item__icon) {
  font-size: 28px;
  color: #1989fa;
}

:deep(.van-grid-item__text) {
  margin-top: 8px;
  color: #333;
  font-size: 14px;
}
</style>