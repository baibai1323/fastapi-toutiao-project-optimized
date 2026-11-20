<template>
  <div class="login-page">
    <van-nav-bar
      title="用户登录"
      left-arrow
      @click-left="onClickLeft"
      fixed
    />
    
    <div class="login-container">
      <div class="login-logo">
        <van-image
          width="80"
          height="80"
          src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg"
          round
        />
        <h2>新闻资讯</h2>
      </div>
      
      <van-form @submit="onSubmit" class="login-form">
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
        </van-cell-group>
        
        <div class="submit-btn">
          <van-button round block type="primary" native-type="submit" size="large">
            登录
          </van-button>
        </div>
        
        <div class="login-tips">
          <p>测试账号：admin</p>
          <p>测试密码：123456</p>
        </div>
      </van-form>
    </div>
  </div>
</template>

<script setup>
// 登录页只做一件事：把账号密码交给仓库，成功后跳回首页。
// ref 用来定义“会变化的数据”：值一变，页面上用到它的地方就会自动刷新。
// 这是 Vue 3 组合式 API 最基础的写法，新手可以先把它理解成“会触发界面更新的变量”。
import { ref } from 'vue';
import { useRouter } from 'vue-router';
// showToast 是 Vant 的轻提示组件，用来显示“登录中/成功/失败”，不用自己写弹窗 DOM。
import { showToast } from 'vant';
// useUserStore 是全局的登录状态仓库（Pinia），token 和用户信息都存在里面，多个页面共享。
import { useUserStore } from '../store/user';

// useRouter 提供路由跳转能力（push/back），它只负责“去哪个页面”。
const router = useRouter();
// 取到仓库实例后，userStore.login() 就等于“请求登录接口 + 保存登录态”。
const userStore = useUserStore();

// 用户名初始为空字符串；van-field 通过 v-model 和这个 ref 双向绑定，用户输入会自动写回来。
const username = ref('');
// 密码只放在内存里的 ref 中，真正代表身份的是登录成功后拿到的 token。
const password = ref('');

// 表单提交处理：van-form 的必填校验通过后才会调用它。
// 参数 values 是表单各字段的值，这里用不到，因为下面直接读 username/password 两个 ref。
const onSubmit = async (values) => {
  // 显示加载提示
  // duration:0 表示“不自动关闭”，等请求结束再用新提示替换；forbidClick 防止用户连点。
  showToast({
    type: 'loading',
    message: '登录中...',
    forbidClick: true,
    duration: 0
  });
  
  // try/catch 包住网络请求：断网、服务没启动等情况会进入 catch，页面不会一直卡着。
  try {
    // 调用API登录
    // 仓库内部负责发请求并保存 token，成功后全站都会变成“已登录”状态。
    const result = await userStore.login({
      username: username.value,
      password: password.value
    });
    
    // success 由后端返回：true 才真正登录成功，false 表示密码错误之类业务失败。
    if (result.success) {
      // 成功后用 success 样式提示，绿色图标比纯文字更容易被用户注意到。
      showToast({
        type: 'success',
        message: result.message
      });
      
      // 登录成功回首页；此时 token 已写进本地存储，刷新浏览器也不会掉登录。
      router.push('/');
    } else {
      // 业务失败时把后端给的 message 原样显示，比自己编一句文案更准确。
      showToast({
        type: 'fail',
        message: result.message
      });
    }
  } catch (error) {
    // 能走到这里说明请求本身失败了（网络断开、服务异常），统一提示用户稍后再试。
    showToast({
      type: 'fail',
      message: '登录失败，请稍后再试'
    });
  }
};

// 左上角返回：回到上一个页面而不是固定跳首页，用户不会因为“迷路”而困惑。
const onClickLeft = () => {
  router.back();
};
</script>

<style scoped>
.login-page {
  min-height: 100vh;
  background-color: #f7f8fa;
}

.login-container {
  padding-top: 56px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.login-logo {
  margin: 40px 0;
  text-align: center;
}

.login-logo h2 {
  margin-top: 16px;
  color: #323233;
  font-size: 22px;
}

.login-form {
  width: 100%;
  padding: 0 16px;
}

.submit-btn {
  margin: 24px 16px;
}

.login-tips {
  text-align: center;
  color: #969799;
  font-size: 14px;
  margin-top: 16px;
}

.login-tips p {
  margin: 8px 0;
}
</style>