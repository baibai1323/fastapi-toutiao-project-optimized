<template>
  <div class="my-container">
    <van-nav-bar :title="$t('my.title')" />
    <div class="user-info" @click="goToProfile" v-if="isLogin">
      <div class="avatar">
        <van-image
          round
          width="80"
          height="80"
          src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg"
        />
      </div>
      <div class="info">
        <div class="username">{{ isLogin ? userInfo.username : $t('my.notLoggedIn') }}</div>
        <div class="desc" v-if="isLogin">{{ userBio || $t('profile.bio') }}</div>
      </div>
      <van-icon name="arrow" class="arrow-icon" />
    </div>
    <div class="user-info" v-else>
      <div class="avatar">
        <van-image
          round
          width="80"
          height="80"
          src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg"
        />
      </div>
      <div class="info">
        <div class="username">{{ $t('my.notLoggedIn') }}</div>
        <div class="desc">
          <van-button type="primary" size="small" @click="goToLogin" style="margin-right: 10px">{{ $t('my.goToLogin') }}</van-button>
          <van-button type="default" size="small" @click="goToRegister">{{ $t('my.goToRegister') }}</van-button>
        </div>
      </div>
    </div>

    <div class="menu-list">
      <van-cell-group inset>
        <van-cell :title="$t('my.myFavorite')" is-link @click="goToFavorite" />
        <van-cell :title="$t('my.browsingHistory')" is-link @click="goToHistory" />
        <van-cell :title="$t('my.notifications')" is-link />
        <van-cell :title="$t('my.settings')" is-link @click="goToSettings" />
        <van-cell v-if="isLogin" :title="$t('my.logout')" @click="handleLogout" />
      </van-cell-group>
    </div>
    <tab-bar />
  </div>
</template>

<script setup>
// 个人中心页：未登录时头部显示“去登录/去注册”，已登录时显示昵称和个人简介。
import { onMounted } from 'vue';
import { useUserStore } from '../store/user';
import { useRouter } from 'vue-router';
import { computed, ref } from 'vue';
// showDialog 是带“取消/确认”的弹窗（退出登录时用），showToast 是短提示（提示先登录时用）。
import { showDialog, showToast } from 'vant';
// TabBar 是底部导航条；useI18n 提供 t 翻译函数，本页文案都走多语言。
import TabBar from '../components/TabBar.vue';
import { useI18n } from 'vue-i18n';

// Pinia 仓库里存着登录态和用户资料，页面只负责读它，不直接发请求。
const userStore = useUserStore();
// router 只负责页面跳转，不负责取数据，和上面的 userStore 分工不同。
const router = useRouter();
// t('my.title') 会按当前语言返回标题文案，切换语言后整页文案都会变。
const { t } = useI18n();

// 从store获取用户信息和登录状态
// 用 computed 而不是普通变量：仓库里的资料一更新，页面就会自动重新渲染。
const userInfo = computed(() => userStore.userInfo);
// 登录状态由“有没有 token”推导而来，用户一退出登录这里立刻变成 false。
const isLogin = computed(() => userStore.getLoginStatus);
// 简介可能为空，用 || 兜底成占位文案，避免页面上出现 undefined。
const userBio = computed(() => userStore.getUserBio || t('profile.bio'));

// 跳转到登录页
// 未登录时头部显示的“去登录”按钮走这里。
const goToLogin = () => {
  router.push('/login');
};

// 跳转到注册页
// 未登录时头部才显示的第二个按钮：没有账号的人从这里去注册。
const goToRegister = () => {
  router.push('/register');
};

// 跳转到个人信息页
// 点头像区域进资料页；只有已登录才允许，避免用户点进去看到一片空白。
const goToProfile = () => {
  if (isLogin.value) {
    router.push('/profile');
  }
};

// 跳转到浏览历史页面
// 历史属于个人数据：未登录先提示，再送去登录页，登录后就能正常查看。
const goToHistory = () => {
  if (isLogin.value) {
    router.push('/history');
  } else {
    // 提示只显示一两秒，紧接着就跳转，用户能明白自己为什么被带走。
    showToast(t('common.login'));
    router.push('/login');
  }
};

// 跳转到我的收藏页面
// 收藏同理必须登录，否则后端会拒绝请求，页面只能是空的。
const goToFavorite = () => {
  if (isLogin.value) {
    router.push('/favorite');
  } else {
    // 文案来自 i18n 的 common.login，切成英文时这里也会跟着变。
    showToast(t('common.login'));
    router.push('/login');
  }
};

// 跳转到设置页面
// 设置页不需要登录：主题和语言是“设备级偏好”，未登录也应该能改。
const goToSettings = () => {
  router.push('/settings');
};

// 退出登录
// 退出是破坏性操作，先弹窗二次确认，防止误触把登录态清掉。
const handleLogout = () => {
  showDialog({
    title: t('common.confirm'),
    message: t('my.logout') + '?',
    showCancelButton: true,
  }).then((action) => {
    // 只有点“确认”才真正退出；点“取消”不进入这个分支，用户仍保持登录。
    if (action === 'confirm') {
      // logout() 会清掉 token 和内存里的用户信息，其他页面的 isLogin 立刻变 false。
      userStore.logout();
      router.push('/login');
    }
  });
};

// 获取用户信息
// onMounted 是页面显示后执行一次的钩子，用来把最新的昵称/简介拉回来。
onMounted(async () => {
  try {
    // 未登录或接口异常时这里会抛错，只打日志、不打扰用户，页面照常显示。
    await userStore.getUserInfoDetail();
  } catch (error) {
    console.error('获取用户信息失败:', error);
  }
});
</script>

<style scoped>
.my-container {
  padding-top: 46px;
  padding-bottom: 50px;
  background-color: var(--background-color);
  color: var(--text-color);
  min-height: 100vh;
  box-sizing: border-box;
}

.van-nav-bar {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  z-index: 999;
}

.user-info {
  display: flex;
  align-items: center;
  padding: 20px 16px;
  background-color: var(--primary-color);
  color: #fff;
  border-radius: 8px;
  margin: 16px;
  position: relative;
}

.arrow-icon {
  position: absolute;
  right: 16px;
  color: #969799;
}

.avatar {
  margin-right: 16px;
}

.info {
  flex: 1;
}

.username {
  font-size: 18px;
  font-weight: bold;
  margin-bottom: 4px;
}

.desc {
  font-size: 14px;
  color: #999;
}

.menu-list {
  margin: 0 16px;
}
</style>