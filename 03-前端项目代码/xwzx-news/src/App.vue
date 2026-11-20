<template>
  <div class="app">
    <router-view v-slot="{ Component }">
      <template v-if="$route.meta.keepAlive">
        <keep-alive>
          <component :is="Component" />
        </keep-alive>
      </template>
      <template v-else>
        <component :is="Component" />
      </template>
    </router-view>
  </div>
</template>

<script setup>
/**
 * 应用根组件（SFC，Single-File Component，单文件组件：把模板、逻辑、样式放在同一个 .vue 文件）。
 * 这里只负责最外层布局和路由出口，不放具体业务，避免每个页面都跟着重新渲染。
 *
 * 约定：路由 meta.keepAlive 为 true 时，把页面包进 <keep-alive> 缓存组件实例，
 * 例如首页从详情页返回时能保留列表和滚动位置；详情页设为 false，保证每次进入都重新取数。
 * 模板里的 <router-view> 是路由匹配到的页面占位符，Component 就是当前页面组件。
 */
// App.vue 作为根组件
</script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

html, body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen,
    Ubuntu, Cantarell, 'Open Sans', 'Helvetica Neue', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  font-size: 16px;
  background-color: #f7f8fa;
  color: #333;
  height: 100%;
  width: 100%;
}

.app {
  max-width: 750px;
  margin: 0 auto;
  height: 100%;
}

/* 移动端适配 */
@media screen and (max-width: 750px) {
  html {
    font-size: calc(100vw / 750 * 16);
  }
}
</style>
