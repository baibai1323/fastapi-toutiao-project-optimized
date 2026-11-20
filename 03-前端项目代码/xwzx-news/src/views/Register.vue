<template>
  <div class="register-page">
    <van-nav-bar
      title="用户注册"
      left-arrow
      @click-left="onClickLeft"
      fixed
    />
    
    <div class="register-container">
      <div class="register-logo">
        <van-image
          width="80"
          height="80"
          src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg"
          round
        />
        <h2>新闻资讯</h2>
      </div>
      
      <van-form @submit="onSubmit" class="register-form">
        <van-cell-group inset>
          <van-field
            v-model="username"
            name="username"
            label="用户名"
            placeholder="请输入用户名"
            :rules="[{ required: true, message: '请填写用户名' }]"
          />
          <van-field
            v-model="password"
            type="password"
            name="password"
            label="密码"
            placeholder="请输入密码"
            :rules="[{ required: true, message: '请填写密码' }]"
          />
          <van-field
            v-model="confirmPassword"
            type="password"
            name="confirmPassword"
            label="确认密码"
            placeholder="请再次输入密码"
            :rules="[
              { required: true, message: '请确认密码' },
              { validator: validatePassword, message: '两次密码不一致' }
            ]"
          />
        </van-cell-group>
        
        <div class="submit-btn">
          <van-button round block type="primary" native-type="submit" size="large">
            注册
          </van-button>
        </div>
        
        <div class="login-link">
          已有账号？<span @click="goToLogin">去登录</span>
        </div>
      </van-form>
    </div>
  </div>
</template>

<script setup>
// 注册页只做三件事：收集账号密码、校验两次输入一致、调用接口建号。
// ref 定义“会变化的数据”，值改了就触发界面刷新；这是 Vue 3 组合式 API 的基础。
import { ref } from 'vue';
import { useRouter } from 'vue-router';
// showToast 是 Vant 的轻提示，用来显示“注册中/成功/失败”，无需自己写弹窗。
import { showToast } from 'vant';
// useUserStore 是全局登录状态仓库（Pinia）：注册成功后 token 也由它保存。
import { useUserStore } from '../store/user';

// useRouter 负责页面跳转，它只关心“去哪一页”。
const router = useRouter();
// 仓库实例：调用 userStore.register() 就是“请求注册接口 + 顺带保存登录态”。
const userStore = useUserStore();

// 三个输入框各自对应一个 ref，van-field 通过 v-model 和它们双向绑定。
const username = ref('');
// 密码只在内存中保存，真正代表身份的是注册成功后返回的 token。
const password = ref('');
// 确认密码只用于前端比对，不会发给后端，作用是不让用户把密码打错。
const confirmPassword = ref('');

// 验证两次密码是否一致
// Vant 的校验规则允许传一个函数，返回 true 表示通过，这里比较两个 ref 的当前值。
const validatePassword = () => {
  return password.value === confirmPassword.value;
};

// 注册提交：先弹“注册中”，再调仓库注册，最后按结果提示并跳转。
const onSubmit = async () => {
  // 显示加载提示
  // duration:0 让提示一直显示，直到下面用成功/失败提示替换它。
  showToast({
    type: 'loading',
    message: '注册中...',
    forbidClick: true,
    duration: 0
  });
  
  // 网络异常必须捕获，否则请求失败时用户只看到按钮点不动，不知道发生了什么。
  try {
    // 调用API注册
    // 只提交用户名和密码，确认密码是前端的概念，后端不需要。
    const result = await userStore.register({
      username: username.value,
      password: password.value
    });
    
    // success=true 表示后端已建号；仓库会同时把 token 存好，等于“注册即登录”。
    if (result.success) {
      // 成功提示用 Vant 的 success 样式：绿色图标加后端返回的文案，比纯文字更醒目。
      showToast({
        type: 'success',
        message: result.message
      });
      
      // 已经是登录状态，直接回首页，不必再让用户去登录页输一遍。
      router.push('/');
    } else {
      // 用户名重复等业务失败：把后端 message 原样提示，比自己编文案更准确。
      showToast({
        type: 'fail',
        message: result.message
      });
    }
  } catch (error) {
    // 请求本身失败（断网/服务异常）才会走到这里，提示用户稍后重试即可。
    showToast({
      type: 'fail',
      message: '注册失败，请稍后再试'
    });
  }
};

// 左上角返回：回到上一页，用户很可能是从登录页点“注册”过来的。
const onClickLeft = () => {
  router.back();
};

// “已有账号？去登录”的入口：切到登录页，省得用户自己找。
const goToLogin = () => {
  router.push('/login');
};
</script>

<style scoped>
.register-page {
  min-height: 100vh;
  background-color: #f7f8fa;
}

.register-container {
  padding-top: 56px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.register-logo {
  margin: 40px 0;
  text-align: center;
}

.register-logo h2 {
  margin-top: 16px;
  color: #323233;
  font-size: 22px;
}

.register-form {
  width: 100%;
  padding: 0 16px;
}

.submit-btn {
  margin: 24px 16px;
}

.login-link {
  text-align: center;
  margin-top: 16px;
  color: #969799;
  font-size: 14px;
}

.login-link span {
  color: #1989fa;
}
</style>