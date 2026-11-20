<template>
  <div class="settings-container">
    <van-nav-bar
      :title="$t('settings.title')"
      left-arrow
      @click-left="onClickLeft"
    />
    
    <div class="settings-list">
      <van-cell-group inset :title="$t('settings.personalization')">
        <van-cell :title="$t('settings.themeCustomization')" is-link @click="showThemePopup = true" />
        <van-cell :title="$t('settings.languageSettings')" is-link @click="showLanguagePopup = true" />
      </van-cell-group>
      
      <van-cell-group inset :title="$t('settings.account')">
        <van-cell :title="$t('settings.privacySettings')" is-link />
        <van-cell :title="$t('settings.notificationSettings')" is-link />
        <van-cell :title="$t('settings.aboutUs')" is-link />
      </van-cell-group>
    </div>
    
    <!-- 主题选择弹出层 -->
    <van-popup
      v-model:show="showThemePopup"
      position="bottom"
      round
      :style="{ height: '40%' }"
    >
      <div class="popup-title">{{ $t('settings.selectTheme') }}</div>
      <div class="theme-list">
        <div 
          v-for="theme in themeList" 
          :key="theme.id" 
          class="theme-item"
          :class="{ active: currentTheme === theme.id }"
          @click="changeTheme(theme.id)"
        >
          <div class="theme-color" :style="{ backgroundColor: theme.primaryColor }"></div>
          <div class="theme-name">{{ theme.name }}</div>
        </div>
      </div>
    </van-popup>
    
    <!-- 语言选择弹出层 -->
    <van-popup
      v-model:show="showLanguagePopup"
      position="bottom"
      round
      :style="{ height: '40%' }"
    >
      <div class="popup-title">{{ $t('settings.selectLanguage') }}</div>
      <van-radio-group v-model="currentLanguage">
        <van-cell-group inset>
          <van-cell 
            v-for="lang in languageOptions" 
            :key="lang.value" 
            :title="lang.label" 
            clickable 
            @click="currentLanguage = lang.value"
            :class="{ 'language-active': currentLanguage === lang.value }"
          >
            <template #right-icon>
              <van-radio :name="lang.value" />
            </template>
          </van-cell>
        </van-cell-group>
      </van-radio-group>
      <div class="popup-footer">
        <van-button type="primary" block @click="changeLanguage">{{ $t('common.confirm') }}</van-button>
      </div>
    </van-popup>
  </div>
</template>

<script setup>
// 设置页：主题配色和界面语言两个弹层，改动会写进各自的仓库并在刷新后继续生效。
import { ref, computed } from 'vue';
import { useRouter } from 'vue-router';
import { showToast } from 'vant';
// 三个仓库分工：主题配色、语言偏好、以及 i18n 的翻译函数所在上下文。
import { useThemeStore } from '../store/theme';
import { useI18n } from 'vue-i18n';
import { useLanguageStore } from '../store/language';

const router = useRouter();
const themeStore = useThemeStore();
const languageStore = useLanguageStore();
// t 用于翻译文案；locale 是当前语言代码（如 'zh-CN'），改它就会切换界面语言。
const { t, locale } = useI18n();

// 返回上一页
// 设置页是从“我的”点进来的，back() 正好回到那里。
const onClickLeft = () => {
  router.back();
};

// 主题相关
// 主题就是“主色 + 背景色”这套配色，由 themeStore 统一管理，换页也不会丢。
// showThemePopup 用 ref 存布尔值，配合 van-popup 的 v-model:show 控制弹层显隐。
const showThemePopup = ref(false);
// getAllThemes 是仓库里的 getter；包一层 computed，主题列表变化时页面会自动更新。
const themeList = computed(() => themeStore.getAllThemes);
// getCurrentTheme 返回当前主题的 id，列表里靠它高亮“选中”的那一项。
const currentTheme = computed(() => themeStore.getCurrentTheme);

// 切换主题
// 先改仓库再提示，用户马上能看到颜色变化，不用等刷新。
const changeTheme = (themeId) => {
  themeStore.setTheme(themeId);
  showToast(t('settings.themeChanged'));
  // 关闭弹层，否则它会一直挡在设置项上面。
  showThemePopup.value = false;
};

// 语言相关
// 语言由 i18n 决定，取值同样来自仓库，这样刷新后还能记住用户的选择。
const showLanguagePopup = ref(false);
// 弹层里“选中但还没确认”的语言先存这里，点“确定”才真正生效，避免误点即切换。
const currentLanguage = ref(languageStore.getCurrentLanguage);
// 目前只支持中英两种；value 是标准语言代码，和 i18n 的 locale 一一对应。
const languageOptions = [
  { label: '简体中文', value: 'zh-CN' },
  { label: 'English', value: 'en-US' }
];

// 切换语言
// 先写进语言仓库、再更新 i18n 的 locale，最后刷新页面让所有已渲染的文案重新翻译。
const changeLanguage = () => {
  languageStore.setLanguage(currentLanguage.value);
  locale.value = currentLanguage.value;
  showLanguagePopup.value = false;
  showToast(t('settings.languageChanged'));
  // 强制刷新页面以应用语言更改
  // 不刷新的话，已经渲染好的标题、Tab 文案不会重新取一次翻译。
  window.location.reload();
};
</script>

<style scoped>
.settings-container {
  min-height: 100vh;
  background-color: var(--background-color);
  color: var(--text-color);
  padding-top: 46px;
  padding-bottom: 20px;
}

.settings-list {
  margin-top: 20px;
}

.popup-title {
  text-align: center;
  padding: 16px;
  font-size: 16px;
  font-weight: bold;
  border-bottom: 1px solid #eee;
}

.theme-list {
  display: flex;
  flex-wrap: wrap;
  padding: 16px;
}

.theme-item {
  width: 25%;
  display: flex;
  flex-direction: column;
  align-items: center;
  margin-bottom: 16px;
  cursor: pointer;
}

.theme-color {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  margin-bottom: 8px;
  border: 2px solid transparent;
}

.theme-item.active .theme-color {
  border-color: #1989fa;
}

.theme-name {
  font-size: 12px;
}

.popup-footer {
  padding: 16px;
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
}

.language-active {
  background-color: #f5f5f5;
}
</style>