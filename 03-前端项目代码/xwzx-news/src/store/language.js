/**
 * 语言偏好 Store。
 * 职责只有一件事：记住用户选的语言并写入 localStorage，供 i18n 初始化时读取。
 * 注意：这里不直接修改 vue-i18n 实例，真正的文案切换由调用方再调用 i18n 的 setI18nLanguage 完成。
 */
import { defineStore } from 'pinia';

// defineStore(唯一 id, 配置)：id 不能和别的 store 重名，调试工具里也靠它识别。
export const useLanguageStore = defineStore('language', {
  // state 是 store 的数据源；localStorage 只能存字符串，取不到时回退到中文。
  state: () => ({
    currentLanguage: localStorage.getItem('language') || 'zh-CN', // 默认中文
  }),
  
  // getters 类似组件里的计算属性，只读，避免组件直接改 state。
  getters: {
    getCurrentLanguage: (state) => state.currentLanguage,
  },
  
  // actions 用来封装“修改 state + 持久化”这一组动作，组件只调用 action，不关心存储细节。
  actions: {
    setLanguage(language) {
      this.currentLanguage = language;
      localStorage.setItem('language', language);
    },
  }
});