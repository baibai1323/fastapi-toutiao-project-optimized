/**
 * 英文语言包（locale）。
 * 与 zh-CN.js 必须保持完全相同的 key 结构，只是 value 换成英文；
 * 缺少某个 key 时，vue-i18n 会按 fallbackLocale 回退到中文，界面上就会中英混排。
 * 翻译时保留原有语气（按钮用动词、提示用短句），不要把中文标点带进英文句子。
 * 文案变更后最好在窄屏下过一遍，英文长度通常是中文的 1.5 倍，容易挤压按钮。
 */
export default {
  // common：通用动作与状态词，按钮和提示共用，避免同一动作在不同页面出现不同英文。
  // 英文比中文长，按钮文案尽量用短词（Save / Cancel），防止移动端换行。
  // 新增通用词时先判断是否真的跨页面复用，只在单页使用的应放到对应命名空间。
  // 同一个中文词在不同语境下可能需要不同英文（如“设置”可能是 Settings 或 Set），不要机械复用。
  common: {
    confirm: 'Confirm',
    cancel: 'Cancel',
    back: 'Back',
    loading: 'Loading...',
    save: 'Save',
    delete: 'Delete',
    edit: 'Edit',
    search: 'Search',
    notFound: 'Not Found',
    login: 'Login',
    register: 'Register',
    logout: 'Logout',
    allCategories: 'All Categories'
  },
  // nav：底部导航文案，必须与 zh-CN 的 nav 以及 TabBar.vue 的三个入口一一对应。
  // 英文标签比中文长，修改时要确认底部栏在 375px 宽度下不溢出。
  // 跳转路径不在这里维护，语言包只负责显示文本。
  nav: {
    home: 'Home',
    aiChat: 'AI Chat',
    my: 'My'
  },
  // home：首页标题、列表操作与分类名。
  // 这些值按英文习惯做了意译（如“头条”译为 Headlines），不是逐字直译。
  // 修改分类名时保持与后端分类语义一致，避免用户看到的分类和内容不匹配。
  home: {
    title: 'News',
    more: 'More',
    refresh: 'Refresh',
    loadMore: 'Load More',
    noMore: 'No More',
    // categories 的 key 与中文包完全一致，只翻译 value；id 与顺序仍由后端接口决定。
    // 英文分类名首字母大写，保持列表视觉统一；专有名词（Sports）不做复数变形。
    // 新增分类时必须同时在 zh-CN.js 补同名 key，否则中文界面会显示英文或 key。
    // 这里的 more 对应“更多分类”入口，不是分页的 loadMore，注意区分。
    categories: {
      headline: 'Headlines',
      society: 'Society',
      domestic: 'Domestic',
      international: 'International',
      entertainment: 'Entertainment',
      sports: 'Sports',
      military: 'Military',
      technology: 'Technology',
      finance: 'Finance',
      more: 'More'
    }
  },
  // aiChat：AI 对话页文案。thinking 用现在进行时，表达“正在处理”。
  // placeholder 用 Enter your question，比直接翻译“请输入”更符合英文界面习惯。
  // 模型名不写进文案，换模型时不需要改语言包。
  aiChat: {
    title: 'AI Chat',
    placeholder: 'Enter your question...',
    send: 'Send',
    thinking: 'AI is thinking...'
  },
  // my：“我的”页面入口与登录引导。
  // notLoggedIn 是状态描述，goToLogin / goToRegister 是行动按钮，翻译时保持词性区别。
  // Profile 指个人资料页，Settings 指设置页，二者不要都译成“设置”相关词。
  // 登录状态下的 Logout 与游客状态的 Login 词形接近，测试时注意不要点错入口。
  my: {
    title: 'My',
    notLoggedIn: 'Not Logged In',
    goToLogin: 'Login',
    goToRegister: 'Register',
    myFavorite: 'My Favorites',
    browsingHistory: 'Browsing History',
    notifications: 'Notifications',
    settings: 'Settings',
    logout: 'Logout',
    profile: 'Profile'
  },
  // settings：设置页分组与提示。languageChanged 说明了“部分更改需重启生效”的边界。
  // 主题名不在此翻译，由 theme store 提供；这里只放页面静态文案。
  // 英文提示句较长，展示时允许换行，不要为了塞进一行而删减关键信息。
  settings: {
    title: 'Settings',
    personalization: 'Personalization',
    themeCustomization: 'Theme Customization',
    languageSettings: 'Language Settings',
    account: 'Account',
    privacySettings: 'Privacy Settings',
    notificationSettings: 'Notification Settings',
    aboutUs: 'About Us',
    selectTheme: 'Select Theme',
    themeChanged: 'Theme changed',
    languageChanged: 'Language changed, some changes will take effect after restarting the app',
    selectLanguage: 'Select Language'
  },
  // profile：个人资料字段。Username 通常只读，Bio 可编辑。
  // Save Changes 比 Save 更明确，强调保存的是修改后的资料。
  // Bio 为空时页面应展示占位提示，不要把空字符串直接渲染成空白区域。
  profile: {
    title: 'Profile',
    username: 'Username',
    bio: 'Bio',
    save: 'Save Changes'
  }
};