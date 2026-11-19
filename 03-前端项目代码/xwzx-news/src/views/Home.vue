<template>
  <div class="home">
    <van-nav-bar :title="$t('home.title')" fixed />
    
    <!-- 更多选项独立div -->
    <div class="more-options">
      <div class="more-tab" @click="goToCategory">
        {{ $t('home.more') }} <van-icon name="arrow" />
      </div>
    </div>
    
    <div class="category-tabs">
      <van-tabs v-model:active="activeTab" sticky swipeable animated>
        <van-tab 
          v-for="category in displayCategories" 
          :key="category.id" 
          :title="getCategoryTranslation(category.name)"
        >
          <van-pull-refresh v-model="newsStore.refreshing" @refresh="onRefresh">
            <van-list
              v-model:loading="newsStore.loading"
              :finished="newsStore.finished"
              :finished-text="$t('home.noMore')"
              @load="onLoad"
            >
              <news-item 
                v-for="item in newsStore.newsList" 
                :key="item.id" 
                :news="item" 
              />
            </van-list>
          </van-pull-refresh>
        </van-tab>
      </van-tabs>
    </div>
    
    <tab-bar />
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed } from 'vue'
import { useNewsStore } from '../store/modules/news'
import { useRouter, useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import NewsItem from '../components/NewsItem.vue'
import TabBar from '../components/TabBar.vue'

/**
 * 首页。
 *
 * [优化] 原代码问题：
 *   1. 写了两个 onMounted（:78 和 :166），每个都调用 getNewsList，
 *      首次进入会并发请求两次列表；
 *   2. van-tab 上同时有 @click 和 watch(activeTab)，点一次发两次请求；
 *   3. handleTabClick 使用未定义的 showDropdown，是运行时会报错的死代码；
 *   4. watch(activeTab) 直接 categories[newVal].id，分类还没加载时点 Tab 会崩。
 * 修复：只保留一个 onMounted；只靠 activeTab 的 watch 切分类；
 *       删掉 showDropdown/更多下拉死代码；越界保护。
 */

const newsStore = useNewsStore()
const router = useRouter()
const route = useRoute()
const { t } = useI18n()

const activeTab = ref(0)
// 分类加载完成前，watch 不触发请求，避免 categories 为空时越界。
let initialized = false

const displayCategories = computed(() => newsStore.categories)

const getCategoryTranslation = (categoryName) => {
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
    '更多': 'more',
  }

  const key = categoryMap[categoryName]
  return key ? t(`home.categories.${key}`) : categoryName
}

const goToCategory = () => {
  router.push('/category')
}

// 根据 route.query.categoryId 找到对应 Tab；返回是否命中。
const syncTabFromRoute = () => {
  const categoryId = Number.parseInt(route.query.categoryId, 10)
  if (!Number.isInteger(categoryId)) return false

  const index = displayCategories.value.findIndex((cat) => cat.id === categoryId)
  if (index === -1) return false

  activeTab.value = index
  return true
}

onMounted(async () => {
  await newsStore.getCategories()

  if (displayCategories.value.length === 0) return

  // 路由带了 categoryId 就优先用它，否则用当前分类/第一个分类。
  if (!syncTabFromRoute()) {
    let index = displayCategories.value.findIndex(
      (cat) => cat.id === newsStore.currentCategory
    )
    if (index === -1) index = 0
    activeTab.value = index
    newsStore.currentCategory = displayCategories.value[index].id
  }

  initialized = true
  await newsStore.getNewsList(true)
})

// 点击/滑动 Tab 只在这里触发一次分类切换。
watch(activeTab, (index) => {
  if (!initialized) return
  const category = displayCategories.value[index]
  if (!category) return
  newsStore.changeCategory(category.id)
})

// 从分类页返回首页时，按 query 切到对应 Tab。
watch(
  () => route.query.categoryId,
  () => {
    if (initialized) syncTabFromRoute()
  }
)

const onRefresh = () => {
  newsStore.getNewsList(true)
}

const onLoad = () => {
  newsStore.getNewsList()
}
</script>

<style scoped>
.home {
  padding-top: 46px;
  padding-bottom: 50px;
  background-color: #f7f8fa;
  min-height: 100vh;
}

.category-tabs {
  margin-bottom: 10px;
  position: relative;
}

:deep(.van-tabs__wrap) {
  background-color: #fff;
}

:deep(.van-tab) {
  font-size: 14px;
}

:deep(.van-tab--active) {
  font-weight: bold;
  color: #1989fa;
}

.more-options {
  position: fixed;
  right: 0;
  /* [优化] 原来用 JS 计算 tabsTop，首屏 300ms 内是 0，会盖住导航栏；直接用固定值。 */
  top: 46px;
  background-color: #fff;
  padding: 0;
  border-radius: 4px 0 0 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  z-index: 1000;
  height: 44px;
  display: flex;
  align-items: center;
}

.more-tab {
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  color: #1989fa;
  font-weight: bold;
  height: 100%;
  padding: 0 10px;
}
</style>
