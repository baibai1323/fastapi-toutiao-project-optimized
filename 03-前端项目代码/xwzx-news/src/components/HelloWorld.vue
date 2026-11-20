/**
 * Vite + Vue 脚手架自带的示例组件，用来演示 props、ref 和热更新（HMR）。
 * 它不属于新闻业务，项目里没有页面引用它，确认是脚手架残留，可以安全删除。
 * 这里保留文件头注释，仅作为学习“组件如何接收参数、如何维护内部计数”的参考。
 */
<script setup>
import { ref } from 'vue'

// defineProps 是 <script setup> 的编译宏，用来声明父组件可以传入 msg 字符串。
// 不写 required，表示 msg 可选；父组件不传时模板会渲染为空。
defineProps({
  msg: String,
})

// ref(0) 创建响应式计数器，初始值为 0；模板中点击按钮执行 count++ 会自动触发视图更新。
const count = ref(0)
</script>

<template>
  <h1>{{ msg }}</h1>

  <div class="card">
    <button type="button" @click="count++">count is {{ count }}</button>
    <p>
      Edit
      <code>components/HelloWorld.vue</code> to test HMR
    </p>
  </div>

  <p>
    Check out
    <a href="https://vuejs.org/guide/quick-start.html#local" target="_blank"
      >create-vue</a
    >, the official Vue + Vite starter
  </p>
  <p>
    Learn more about IDE Support for Vue in the
    <a
      href="https://vuejs.org/guide/scaling-up/tooling.html#ide-support"
      target="_blank"
      >Vue Docs Scaling up Guide</a
    >.
  </p>
  <p class="read-the-docs">Click on the Vite and Vue logos to learn more</p>
</template>

<style scoped>
.read-the-docs {
  color: #888;
}
</style>
