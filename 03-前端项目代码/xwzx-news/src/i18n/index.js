/**
 * 国际化（i18n）初始化。
 * 作用：让界面文案按语言包切换，模板里统一写 $t('nav.home')，而不是直接写“首页”。
 * 约定：key 使用“命名空间.字段”的层级写法，中英文语言包必须保持相同 key，否则某语言会回退到中文。
 */
import { createI18n } from 'vue-i18n';
import zhCN from './locales/zh-CN.js';
import enUS from './locales/en-US.js';

// 创建i18n实例
// 在应用启动时调用一次，返回值交给 main.js 的 app.use(i18n)。
export function setupI18n() {
  // 在创建i18n实例前获取语言设置
  // 用户上次选择的语言存在 localStorage；没有记录时默认中文，保证首次访问有可读文案。
  const savedLanguage = localStorage.getItem('language') || 'zh-CN';
  
  // legacy: false 表示使用组合式 API 模式，此时 locale 是 ref，切换时要改 .value。
  // fallbackLocale 指定找不到当前语言 key 时的兜底语言，防止页面直接显示 key 本身。
  // messages 是语言包字典，键名必须和 locale 的值（zh-CN / en-US）完全一致。
  const i18n = createI18n({
    legacy: false, // 使用组合式API
    locale: savedLanguage,
    fallbackLocale: 'zh-CN',
    messages: {
      'zh-CN': zhCN,
      'en-US': enUS
    }
  });
  
  // 返回实例，由调用方安装到 Vue 应用。
  return i18n;
}

// 动态切换语言
// i18n.mode 为 legacy 时 locale 是普通字符串，组合式模式下是 ref，所以两种写法要分别处理。
// 同步更新 <html lang="...">，既方便 CSS 按语言微调，也提升屏幕阅读器和浏览器的语言识别。
export function setI18nLanguage(i18n, locale) {
  if (i18n.mode === 'legacy') {
    i18n.global.locale = locale;
  } else {
    i18n.global.locale.value = locale;
  }
  document.querySelector('html').setAttribute('lang', locale);
}