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

// 新闻仓库（Pinia store）：分类列表、新闻列表、分页状态都存在这里，多个页面共享同一份数据。
// router 负责“跳转”，route 负责“读当前地址”，名字很像但职责完全不同。
const newsStore = useNewsStore()
const router = useRouter()
const route = useRoute()
// t 是 i18n 的翻译函数：t('home.title') 会按当前语言返回对应文案。
const { t } = useI18n()

// activeTab 是 van-tabs 的 v-model 值，存的是“第几个分类”，从 0 开始数。
const activeTab = ref(0)
// 分类加载完成前，watch 不触发请求，避免 categories 为空时越界。
let initialized = false

// 直接复用仓库里的分类数组；包成计算属性后，仓库数据一变模板就自动跟着变。
const displayCategories = computed(() => newsStore.categories)

// 后端分类名是中文（如“头条”），界面又要跟随中英文切换，所以先映射成 i18n 的 key 再翻译。
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

// 右上角“更多”按钮进入分类总览页；用 push 而不是 replace，用户点返回还能回到首页。
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

// onMounted 是组件第一次显示到屏幕上之后的钩子，首屏的分类和新闻都在这里拉。
// 注意这里是 async 函数：await 会等接口返回再继续，模板上的 loading 会自己处理。
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
    // currentCategory 是仓库记的“当前分类 id”，这里一起改掉，刷新后才不会跳回别的分类。
    newsStore.currentCategory = displayCategories.value[index].id
  }

  // initialized 置 true 之后，watch 才允许按 Tab 切换发请求。
  initialized = true
  await newsStore.getNewsList(true)
})

// 点击/滑动 Tab 只在这里触发一次分类切换。
// 与“点一次发两次请求”的老写法相比，唯一的触发点在这里，逻辑更好排查。
watch(activeTab, (index) => {
  if (!initialized) return
  const category = displayCategories.value[index]
  // 越界保护：分类没加载完时 index 可能指向不存在的项，直接返回避免报错。
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

// 下拉刷新：参数 true 表示“重置回第一页”，否则新数据会接在旧列表后面。
// van-pull-refresh 自己管刷新动画，我们只要重新拉一次数据即可。
const onRefresh = () => {
  newsStore.getNewsList(true)
}

// 触底加载更多：van-list 滚到底部时回调它，不传参数表示“接着加载下一页”。
// 分页的好处是一次不拉太多数据，手机流量和首屏速度都更好。
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
