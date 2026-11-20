/**
 * 简体中文语言包（locale）。
 * 结构是嵌套对象，访问路径就是 key：例如 t('home.categories.headline') 取到“头条”。
 * 约定：新增文案时必须在 en-US.js 增加同名 key，否则英文界面会回退到中文。
 * 这里只放“展示文案”，不放业务判断值；需要枚举 id 的配置应放在 store 或 config 里。
 * 修改文案前先确认该 key 是否被多个页面引用，避免只改一处导致同类按钮措辞不一致。
 */
export default {
  // common：全站通用动作和状态词，多个页面复用，避免每个页面各写一套“确认/取消”。
  // 组件里只引用语义 key（如 common.save），改文案时不用动任何 .vue 文件。
  // 如果某个 key 只在单个页面使用，应放到对应页面命名空间，不要往 common 里堆。
  // common 的 key 越少，改动影响面越小；新增前先确认是否真的跨页面复用。
  common: {
    confirm: '确认',
    cancel: '取消',
    back: '返回',
    loading: '加载中...',
    save: '保存',
    delete: '删除',
    edit: '编辑',
    search: '搜索',
    notFound: '未找到内容',
    login: '登录',
    register: '注册',
    logout: '退出登录',
    allCategories: '全部分类'
  },
  // nav：底部导航栏文案，key 与 TabBar.vue 里的 $t('nav.xxx') 一一对应。
  // 增删导航入口时，这里和 TabBar.vue 必须同时改，否则会出现空白标签或多余 key。
  // 跳转路径写在组件模板的 to 属性里，语言包只负责“显示成什么字”。
  nav: {
    home: '首页',
    aiChat: 'AI问答',
    my: '我的'
  },
  // home：首页的标题、操作按钮和分类名。
  // title 用于页面主标题；more / refresh / loadMore / noMore 对应列表的交互提示。
  // 这些 key 会被 Home.vue 和分类页共用，改动前先搜索引用，避免影响两个页面。
  home: {
    title: '新闻资讯',
    more: '更多',
    refresh: '刷新',
    loadMore: '加载更多',
    noMore: '没有更多了',
    // categories 是分类展示名；真正的分类 id 来自后端接口，这里只负责翻译，顺序不代表接口顺序。
    // 前端按 id 匹配分类后，用对应 key 取中文名，因此 key 名要与业务分类语义一致。
    // 后端新增分类时，两个语言包都要补 key，否则界面会直接暴露未翻译的 key。
    // 时政类（headline/society/domestic/international）在前，生活与专业类在后，便于人工校对。
    categories: {
      headline: '头条',
      society: '社会',
      domestic: '国内',
      international: '国际',
      entertainment: '娱乐',
      sports: '体育',
      military: '军事',
      technology: '科技',
      finance: '财经',
      more: '更多'
    }
  },
  // aiChat：AI 对话页的输入框占位符、发送按钮和等待提示。
  // thinking 在请求发出到首字返回之间展示，给用户“系统正在工作”的反馈。
  // placeholder 只描述输入内容，不写具体模型名，换模型时无需改文案。
  aiChat: {
    title: 'AI问答',
    placeholder: '请输入您的问题...',
    send: '发送',
    thinking: 'AI思考中...'
  },
  // my：“我的”页面入口文案；未登录时用 notLoggedIn + goToLogin 引导登录。
  // myFavorite / browsingHistory / notifications / settings / profile 是功能入口标题。
  // 退出登录按钮复用 logout，但和 common.logout 分开，方便以后单独调整“我的”页措辞。
  // notLoggedIn 只描述状态，真正可点的是 goToLogin / goToRegister 两个按钮，不要混用。
  my: {
    title: '我的',
    notLoggedIn: '未登录',
    goToLogin: '去登录',
    goToRegister: '去注册',
    myFavorite: '我的收藏',
    browsingHistory: '浏览历史',
    notifications: '消息通知',
    settings: '设置',
    logout: '退出登录',
    profile: '个人信息'
  },
  // settings：设置页的分组标题、主题/语言选择及相关提示。
  // languageChanged 是“切换成功”的提示文案，实际语言切换由 i18n 的 setI18nLanguage 完成。
  // 主题名（如“浅色模式”）来自 theme store，不放在这里，避免同一概念两处维护。
  settings: {
    title: '设置',
    personalization: '个性化',
    themeCustomization: '主题定制',
    languageSettings: '语言设置',
    account: '账户',
    privacySettings: '隐私设置',
    notificationSettings: '通知设置',
    aboutUs: '关于我们',
    selectTheme: '选择主题',
    themeChanged: '主题已更改',
    languageChanged: '语言设置已更改，部分更改将在重启应用后生效',
    selectLanguage: '选择语言'
  },
  // profile：个人信息编辑页的字段标签和保存按钮。
  // username 通常只读展示，bio 可编辑；保存按钮文案与 common.save 分开，便于单独强调“修改”。
  // bio 为空时页面应展示占位提示，不要把空字符串直接渲染成空白区域。
  profile: {
    title: '个人信息',
    username: '用户名',
    bio: '个人简介',
    save: '保存修改'
  }
};