<template>
  <div class="profile-page">
    <van-nav-bar
      title="个人信息"
      left-arrow
      @click-left="$router.back()"
      fixed
    />
    
    <div class="profile-container">
      <van-cell-group inset class="avatar-group">
        <van-cell title="头像" center>
          <template #right-icon>
            <van-image
              round
              width="60"
              height="60"
              src="https://fastly.jsdelivr.net/npm/@vant/assets/cat.jpeg"
            />
          </template>
        </van-cell>
      </van-cell-group>
      
      <van-cell-group inset class="info-group">
        <van-cell title="用户名" :value="userInfo.username || 'admin'" />
        <van-cell title="账号ID" :value="`ID: heima-${userId || 'N/A'}`" />
        <van-cell title="个人简介" :value="userBio || '暂无简介'" is-link @click="showBioDialog" />
      </van-cell-group>
      
      <van-cell-group inset class="security-group">
        <van-cell title="修改密码" is-link @click="showPasswordConfirm" />
      </van-cell-group>
    </div>
  </div>
</template>

<script setup>
// 个人中心页：展示当前登录用户的信息，并提供“修改密码”“修改个人简介”两个弹窗操作。
// <script setup> 是 Vue 3 的组合式写法，这里定义的变量和函数可以直接在模板里使用。
// ref 用来存“会变化的值”，computed 是“由别的值算出来的值”，h 用来在 JS 里拼出 DOM 结构。
import { ref, computed, h, onMounted } from 'vue';
// 全局用户状态仓库（Pinia）：token、用户资料、登录状态都放这里，多个页面共享同一份数据。
import { useUserStore } from '../store/user';
// vant 的弹窗与提示组件：showDialog 弹确认框，showToast 是几秒后自动消失的轻提示。
import { showDialog, showToast, showLoadingToast, showSuccessToast, showFailToast } from 'vant';
// useRouter 拿到路由对象，用来做“跳转到登录页”这类页面切换。
import { useRouter } from 'vue-router';

// 路由实例：router.push('/login') 表示跳转到登录页。
const router = useRouter();
// 用户仓库实例：下面所有用户数据的读取和修改都通过它，保证各页面状态一致。
const userStore = useUserStore();

// 初始化用户状态
// onMounted 是“组件挂载完成”的生命周期钩子，页面一打开就会执行这里的逻辑。
onMounted(async () => {
  // 如果用户未登录，跳转到登录页面
  // 先判断仓库里的登录状态，没登录直接回登录页，后面的请求也就不用发了。
  if (!userStore.getLoginStatus) {
    router.push('/login');
    return;
  }
  
  // 获取用户信息
  try {
    // 显示加载提示
    // duration:0 表示“不自动关闭”，需要我们自己调 close()，适合耗时不确定的请求；
    // forbidClick:true 会加一层遮罩，防止用户在加载过程中重复点击。
    const loadingInstance = showLoadingToast({
      message: '加载中...',
      forbidClick: true,
      duration: 0
    });
    
    // console.log('获取用户信息，当前token:', userStore.token);
    
    // 使用新的 getUserInfoDetail 方法
    // await 会等接口返回再继续往下执行；result.success 表示这次请求在业务上是否成功。
    const result = await userStore.getUserInfoDetail();
    
    // 手动关闭加载提示
    // 放在成功/失败判断之前，保证两条路径都会关掉，否则加载圈会一直转。
    loadingInstance.close();
    
    // 成功时仓库里的 userInfo 已被更新，模板会自动刷新显示。
    if (result.success) {
      console.log('获取用户信息成功:', userStore.userInfo);
      // 显示成功提示
      // showSuccessToast('获取用户信息成功');
    } else {
      // 接口通了但业务失败（比如 token 失效），把后端给的原因弹给用户看。
      console.error('获取用户信息失败:', result.message);
      showFailToast(result.message || '获取用户信息失败');
    }
  } catch (error) {
    // catch 兜住网络异常这类“请求根本没成功”的情况。
    console.error('获取用户信息请求失败:', error);
    // 确保关闭加载提示
    // 出错路径里拿不到 loadingInstance，用 showToast.clear() 统一清掉页面上所有提示。
    showToast.clear();
    showToast.fail('获取用户信息失败');
  }
});

// 三个计算属性：依赖的仓库数据一变，它们会自动重新计算，模板里可以像变量一样直接用。
const userInfo = computed(() => userStore.userInfo);
// 用 token 的前 5 位当“用户编号”展示：既能区分用户，又不会把完整 token 暴露在界面上。
const userId = computed(() => userStore.token ? userStore.token.substring(0, 5) : '');
// ?. 是可选链：userInfo 可能还是 null，直接取 .bio 会报错；没有简介时给一句默认文案。
const userBio = computed(() => userStore.userInfo?.bio || '暂无简介');

// 打开“修改密码”弹窗并处理提交
// h() 是 Vue 的渲染函数：用 JS 描述界面，这里用它把三个输入框拼成弹窗内容。
const showPasswordConfirm = () => {
  // 使用ref创建响应式变量
  // 三个输入框的值分别存在这三个 ref 里；ref 创建的值要读写 .value。
  const oldPassword = ref('');
  const newPassword = ref('');
  const confirmPassword = ref('');
  
  // showDialog 返回 Promise：点“确认”走 .then，点“取消”走后面的 .catch。
  showDialog({
    title: '修改密码',
    showCancelButton: true,
    className: 'password-dialog',
    // 弹窗主体由三段“标题 + 密码输入框”组成，按顺序竖着排列。
    message: h('div', { style: 'text-align: left; padding: 10px 0;' }, [
      // 第一段：当前密码。要求先输旧密码，是为了确认操作的人确实是账号本人。
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '当前密码：'),
        h('input', {
          // type: 'password' 会把输入内容显示成圆点，避免被旁人看到。
          type: 'password',
          value: oldPassword.value,
          // onInput 在每次键入时触发，把输入框当前文字同步回 ref，这样提交时才能读到。
          onInput: (e) => { oldPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ]),
      // 第二段：新密码。
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '新密码：'),
        h('input', {
          type: 'password',
          value: newPassword.value,
          onInput: (e) => { newPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ]),
      // 第三段：再输一遍新密码，用来防止手误打错。
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '确认密码：'),
        h('input', {
          type: 'password',
          value: confirmPassword.value,
          onInput: (e) => { confirmPassword.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box;'
        })
      ])
    ]),
  }).then(async () => {
    // 点击确认按钮
    // 先做前端校验：三个框都有值、两次新密码一致，才真正发请求，省掉明显无效的调用。
    if (!oldPassword.value) {
      showToast('请输入当前密码');
      return;
    }
    
    if (!newPassword.value) {
      showToast('请输入新密码');
      return;
    }
    
    // 两次输入不一致说明用户打错了，直接提示重填，不必发给后端。
    if (newPassword.value !== confirmPassword.value) {
      showToast('两次密码输入不一致');
      return;
    }
    
    try {
      // 显示加载提示
      // 请求期间显示“修改中...”，并用遮罩挡住重复点击，避免提交两次。
      const loadingInstance = showLoadingToast({
        message: '修改中...',
        forbidClick: true,
        duration: 0
      });
      
      // 调用API更新密码
      // 把旧密码一起发过去：后端要先验证旧密码对不对，才允许改成新的。
      const result = await userStore.updatePassword(oldPassword.value, newPassword.value);
      
      // 关闭加载提示
      loadingInstance.close();
      
      // 后端返回 success 才算改成功，否则把失败原因展示出来。
      if (result && result.success) {
        showSuccessToast('密码修改成功');
      } else {
        showFailToast((result && result.message) || '密码修改失败');
      }
    } catch (error) {
      // 网络异常或接口报错：清掉残留提示，再给一句统一失败文案。
      console.error('修改密码失败:', error);
      showToast.clear();
      showToast.fail('密码修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
    // 取消是正常操作，什么都不用做；写这个空 catch 是为了不让 Promise 报“未处理异常”。
  });
};

// 打开“修改个人简介”弹窗并处理保存
const showBioDialog = () => {
  // 使用ref创建响应式变量
  // 输入框初值取当前简介，用户可以在原文基础上修改。
  const newBioValue = ref(userBio.value);
  
  // 弹窗内容用 h 拼出来：一行标题 + 一个多行文本框。
  showDialog({
    title: '修改个人简介',
    showCancelButton: true,
    confirmButtonText: '确认',
    className: 'bio-dialog',
    message: h('div', { style: 'text-align: left; padding: 10px 0;' }, [
      h('div', { style: 'margin-bottom: 15px;' }, [
        h('div', { style: 'margin-bottom: 5px; text-align: left;' }, '个人简介：'),
        // textarea 是多行输入框；min-height 保证它至少有 100px 高，便于写长一点。
        h('textarea', {
          value: newBioValue.value,
          onInput: (e) => { newBioValue.value = e.target.value },
          style: 'width: 100%; border: 1px solid #dcdee0; border-radius: 4px; padding: 8px; box-sizing: border-box; min-height: 100px; resize: vertical;'
        })
      ])
    ])
  }).then(async () => {
    // 点击确认按钮
    try {
      // 显示加载提示
      // “保存中...”配合遮罩，告诉用户正在提交并防止重复保存。
      const loadingInstance = showLoadingToast({
        message: '保存中...',
        forbidClick: true,
        duration: 0
      });
      
      console.log('更新个人简介:', newBioValue.value);
      
      // 调用API更新个人简介
      // 传的是输入框里的最新文字；成功后仓库里的 userInfo 会被同步更新。
      const result = await userStore.updateUserBio(newBioValue.value);
      
      // 关闭加载提示
      loadingInstance.close();
      
      // 成功弹成功提示，失败优先展示后端给的具体原因。
      if (result && result.success) {
        showSuccessToast('个人简介修改成功');
      } else {
        showFailToast((result && result.message) || '个人简介修改失败');
      }
    } catch (error) {
      // 请求异常时统一清理提示，避免“保存中”一直挂着。
      console.error('更新个人简介失败:', error);
      showToast.clear();
      showToast.fail('个人简介修改失败');
    }
  }).catch(() => {
    // 点击取消按钮
    // 用户放弃修改时不做任何操作，这里只是吞掉 Promise 的取消回调。
  });
};
</script>

<style scoped>
.profile-page {
  min-height: 100vh;
  background-color: #f7f8fa;
}

.profile-container {
  padding-top: 56px;
  padding-bottom: 20px;
}

.avatar-group,
.info-group,
.security-group {
  margin-top: 12px;
}

.password-dialog .van-dialog__content {
  padding: 20px;
}

.password-form .form-item {
  margin-bottom: 15px;
  text-align: left;
}

.password-form .form-item span {
  display: block;
  margin-bottom: 5px;
  text-align: left;
}

.password-form .password-input {
  width: 100%;
  border: 1px solid #dcdee0;
  border-radius: 4px;
  padding: 8px;
  outline: none;
  box-sizing: border-box;
}
</style>