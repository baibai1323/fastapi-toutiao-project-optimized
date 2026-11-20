<template>
  <van-tabbar v-model="active" route>
    <van-tabbar-item to="/home" icon="home-o">{{ $t('nav.home') }}</van-tabbar-item>
    <van-tabbar-item to="/aichat" icon="chat-o">{{ $t('nav.aiChat') }}</van-tabbar-item>
    <van-tabbar-item to="/my" icon="user-o">{{ $t('nav.my') }}</van-tabbar-item>
  </van-tabbar>
</template>

<script setup>
/**
 * 底部导航栏：首页、AI 问答、我的三个入口。
 * 使用 Vant 的 <van-tabbar>，开启 route 模式后，点击标签会直接按 to 指定的路径跳转。
 * active 只控制高亮下标，真正的页面切换由路由完成，两者要保持同步。
 *
 * 该组件只在主布局里渲染一次，切换页面时不会重建，因此高亮逻辑必须自己监听路由变化。
 */
// 该组件只在主布局出现一次，是三个一级页面的切换入口。
// 图标名来自 Vant 内置图标集，换图标只改 icon 值，不需要引入图片资源。
// 文案走 i18n，切换语言后标签会随 $t 自动更新，无需重新挂载组件。
import { ref } from 'vue'
import { useRoute } from 'vue-router'

// ref 用来创建响应式数据：值变化时，模板里用到它的地方会自动更新。
const route = useRoute()
const active = ref(0)

// 根据当前路由路径设置激活的标签
// 用 includes 而不是全等，是为了兼容带子路径的情况（例如详情页仍归属首页 Tab）。
// 顺序按“首页 → AI → 我的”写，三个分支互斥，命中一个就不会再判断后面的。
const setActiveTab = () => {
  const path = route.path
  if (path.includes('/home')) {
    active.value = 0
  } else if (path.includes('/aichat')) {
    active.value = 1
  } else if (path.includes('/my')) {
    active.value = 2
  }
}

// 初始化时设置激活标签
// 组件首次加载时同步一次，之后的高亮切换主要交给 van-tabbar 的 route 模式处理。
setActiveTab()
</script>

<style scoped>
/* 自定义样式可以在这里添加 */
</style>