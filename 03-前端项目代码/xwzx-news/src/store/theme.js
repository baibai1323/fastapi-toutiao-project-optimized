/**
 * 主题 Store：维护可选配色、当前主题，并把配色写到页面根元素的 CSS 变量上。
 * 持久化思路：localStorage 只保存主题名字符串，刷新时按名字从 themes 表里取回完整配色，
 * 这样以后改某个主题的具体色值，所有用户都会自动用上新配色，不需要迁移本地数据。
 * 术语：CSS 变量（自定义属性）形如 --primary-color，设置一次后，样式里用 var(--primary-color) 复用。
 */
import { defineStore } from 'pinia';

// defineStore 的第一个参数是 store 的唯一 id，第二个参数用对象写法组织 state/getters/actions。
export const useThemeStore = defineStore('theme', {
  // state 必须写成函数，保证每次创建 store 都返回一份新对象，避免多个实例共享同一份引用。
  // 这也是 Pinia 与 Vuex 的硬性约定：直接写对象会在热更新时残留上一次的状态。
  state: () => ({
    // 初始化时同步读取 localStorage，保证首屏渲染前就知道该用哪套颜色，避免先闪一下浅色。
    // 如果用户手动改过缓存导致主题名不存在，getThemeConfig 会得到 undefined；正常入口都会走 setTheme 校验。
    currentTheme: localStorage.getItem('theme') || 'light', // 默认浅色主题
    // themes 是“主题名 → 一套颜色”的字典；新增主题时在这里加一项即可，界面会通过 getAllThemes 自动出现。
    themes: {
      light: {
        name: '浅色模式',
        backgroundColor: '#ffffff',
        textColor: '#333333',
        primaryColor: '#1989fa',
        secondaryColor: '#f5f5f5',
      },
      dark: {
        name: '深色模式',
        backgroundColor: '#121212',
        textColor: '#ffffff',
        primaryColor: '#4c8bf5',
        secondaryColor: '#2d2d2d',
      },
      blue: {
        name: '蓝色主题',
        backgroundColor: '#e6f7ff',
        textColor: '#333333',
        primaryColor: '#1890ff',
        secondaryColor: '#bae7ff',
      },
      green: {
        name: '绿色主题',
        backgroundColor: '#f6ffed',
        textColor: '#333333',
        primaryColor: '#52c41a',
        secondaryColor: '#d9f7be',
      }
    }
  }),
  
  // getters 对外暴露只读派生数据，组件不需要知道 themes 的内部结构。
  getters: {
    // 当前主题名，例如 'light'。
    getCurrentTheme: (state) => state.currentTheme,
    // 当前主题的完整配色对象，供需要读取具体色值的组件使用。
    // 返回的是 themes 里的原对象，组件只读即可；不要直接改它，否则会污染主题表。
    getThemeConfig: (state) => state.themes[state.currentTheme],
    // 转成下拉框/列表更好消费的数组，只暴露 id、显示名和主色，避免把整张配色表传出去。
    getAllThemes: (state) => Object.keys(state.themes).map(key => ({
      id: key,
      name: state.themes[key].name,
      primaryColor: state.themes[key].primaryColor
    }))
  },
  
  // actions 封装主题切换的完整流程：校验 → 改状态 → 持久化 → 应用 CSS 变量。
  // 四步顺序不能乱：先持久化再应用，页面刷新后仍能恢复；先校验再改状态，避免写入非法主题名。
  actions: {
    setTheme(themeName) {
      // 先确认名字存在，防止调用方传错值后 currentTheme 指向 undefined，后续取色直接报错。
      // 不存在时静默忽略而不是抛异常：主题切换失败不应阻断页面其它交互。
      if (this.themes[themeName]) {
        // 先改内存再持久化：界面能立即响应，随后同步写入 localStorage。
        // 隐私模式下 localStorage 可能不可写，此时至少保证当前会话内主题生效。
        this.currentTheme = themeName;
        localStorage.setItem('theme', themeName);
        // 最后刷 CSS 变量，保证“状态、缓存、画面”三者一致。
        this.applyTheme();
      }
    },
    
    // 把当前主题的四个色值写到 <html> 上，全局样式即可通过 var(--xxx) 跟随切换。
    // 写在 documentElement（即 <html>）而不是某个组件上，CSS 变量才能被所有后代元素继承。
    // 变量名是样式与 JS 之间的契约，改动时要同步搜索 styles 里的 var(--background-color) 等引用。
    applyTheme() {
      const theme = this.themes[this.currentTheme];
      document.documentElement.style.setProperty('--background-color', theme.backgroundColor);
      document.documentElement.style.setProperty('--text-color', theme.textColor);
      document.documentElement.style.setProperty('--primary-color', theme.primaryColor);
      document.documentElement.style.setProperty('--secondary-color', theme.secondaryColor);
    },
    
    // 应用启动时调用：localStorage 里已有主题名，这里只负责把对应色值真正刷到页面上。
    // 放在 main.js 挂载应用之前调用，首屏就能拿到正确颜色，避免用户看到默认色再跳变。
    initTheme() {
      this.applyTheme();
    }
  }
});