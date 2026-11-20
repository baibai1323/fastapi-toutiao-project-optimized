<template>
  <div class="history-container">
    <van-nav-bar
      title="浏览历史"
      left-text="返回"
      left-arrow
      @click-left="onClickLeft"
      right-text="清空"
      @click-right="onClickClear"
      fixed
    />
    
    <div class="history-list" v-if="historyStore.getHistory.length">
      <div class="history-item" v-for="item in historyStore.getHistory" :key="item.id">
        <van-cell @click="goToNewsDetail(item.id)" :border="false">
          <template #title>
            <div class="news-item">
              <div class="news-image" v-if="item.image">
                <img :src="item.image" :alt="item.title">
              </div>
              <div class="news-info">
                <div class="news-title">{{ item.title }}</div>
                <div class="news-meta">
                  <span>{{ item.author }}</span>
                  <span>{{ item.publishTime }}</span>
                  <span>浏览时间: {{ item.viewTime }}</span>
                </div>
              </div>
            </div>
          </template>
        </van-cell>
        <van-button 
          class="delete-btn" 
          type="danger" 
          size="mini" 
          icon="cross"
          @click="confirmDelete(item.id)"
        ></van-button>
      </div>
    </div>
    
    <van-empty v-else description="暂无浏览历史" />
  </div>
</template>

<script setup>
// 浏览历史页：列出用户看过的新闻，支持删一条和一键清空。
// 历史同时存在服务端（登录用户）和本地缓存（未登录），仓库会自动在两者之间回退。
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
// 历史仓库：封装了“读服务端列表 / 读本地列表 / 删除 / 清空”，页面不用关心细节。
import { useHistoryStore } from '../store/modules/history';
// showDialog 用来做删除前的二次确认，避免误触把记录删掉。
import { showDialog } from 'vant';

const router = useRouter();
const historyStore = useHistoryStore();

// 返回上一页
// back() 等价于浏览器的后退按钮，用户从哪里进来就回到哪里。
const onClickLeft = () => {
  router.back();
};

// 跳转到新闻详情
// 列表每一项都带着新闻 id，拼进路由就能打开对应文章。
const goToNewsDetail = (id) => {
  router.push(`/news/detail/${id}`);
};

// 删除单条历史记录
// 删除要区分“服务端删除”和“本地删除”：仓库返回的 isLocal=true 表示这次只动了本地缓存。
const removeHistory = async (id) => {
  try {
    const result = await historyStore.removeHistoryApi(id);
    // 打印结果方便在控制台确认接口到底成功没有，排查问题时很有用。
    console.log('删除单条历史记录结果:', result);
    
    // 如果API请求失败且不是本地操作，则显示错误提示
    // 本地操作失败通常不必打扰用户，只有真正的服务端失败才弹窗。
    if (!result.success && !result.isLocal) {
      showDialog({
        title: '提示',
        message: result.message || '删除失败，请稍后重试',
      });
    }
  } catch (error) {
    // 抛异常说明请求本身失败（断网等），这里只提示不重试，避免界面和服务端状态不一致。
    console.error('删除历史记录失败:', error);
    // 出错时仍然尝试本地删除
    // historyStore.removeHistory(id);
  }
};

// 确认删除
// showDialog 返回 Promise：确认时 action 为 'confirm'，取消时走 reject。
const confirmDelete = (id) => {
  showDialog({
    title: '提示',
    message: '确定要删除这条浏览记录吗？',
    showCancelButton: true,
  }).then((action) => {
    // 只有明确点了“确认”才删除，防止误触。
    if (action === 'confirm') {
      removeHistory(id);
    }
  });
};

// 清空历史记录
// 清空比删一条更危险，所以同样要先确认；成功后仓库会清空列表，页面自动显示空状态。
const onClickClear = async () => {
  showDialog({
    title: '提示',
    message: '确定要清空所有浏览历史吗？',
    showCancelButton: true,
  }).then(async (action) => {
    // 用户点“取消”时 Promise 走 reject，这里不会执行任何删除。
    if (action === 'confirm') {
      try {
        // 一次请求清空服务端记录，比循环逐条删除省很多次网络往返。
        const result = await historyStore.clearHistoryApi();
        // 打印结果便于确认接口是否真的清空成功。
        console.log('清空历史记录结果:', result);
        
        // 如果API请求失败且不是本地操作，则显示错误提示
        // isLocal=true 表示只清了本地缓存、没有真的请求后端，不必当成错误弹窗。
        if (!result.success && !result.isLocal) {
          showDialog({
            title: '提示',
            message: result.message || '清空失败，请稍后重试',
          });
        }
      } catch (error) {
        // 请求异常时只记录日志，界面上的列表保持不变，避免出现“假清空”。
        console.error('清空历史记录失败:', error);
        // 出错时仍然尝试本地清空
        // historyStore.clearHistory();
      }
    }
  });
};

// 组件挂载时加载历史记录
// onMounted：页面显示到屏幕上之后执行一次，适合做首屏加载。
onMounted(async () => {
  // 先尝试从API获取浏览历史
  // 已登录时以服务端为准，这样换设备登录也能看到完整历史。
  try {
    const result = await historyStore.getHistoryListApi();
    console.log('浏览历史页面：API获取结果', result);
    
    // 如果API请求失败或用户未登录，则从本地加载
    // 未登录时后端会直接返回失败，这不是异常，静默回退到本地即可。
    if (!result || !result.success) {
      historyStore.loadHistory();
    }
  } catch (error) {
    console.error('浏览历史页面：API请求异常', error);
    // 出错时从本地加载
    // 本地缓存存在 localStorage 里，断网时也能让用户看到最近看过什么。
    historyStore.loadHistory();
  }
});
</script>

<style scoped>
.history-container {
  padding-top: 46px;
  padding-bottom: 20px;
  background-color: #f7f8fa;
  min-height: 100vh;
}

.history-list {
  padding: 10px;
}

.news-item {
  display: flex;
  padding: 10px 0;
}

.news-image {
  width: 120px;
  height: 80px;
  margin-right: 12px;
  flex-shrink: 0;
}

.news-image img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  border-radius: 4px;
}

.news-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.news-title {
  font-size: 16px;
  font-weight: bold;
  line-height: 1.4;
  margin-bottom: 8px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.news-meta {
  font-size: 12px;
  color: #999;
  display: flex;
  flex-wrap: wrap;
}

.news-meta span {
  margin-right: 10px;
}

.delete-button {
  width: 20px;
  height: 20px;
  background-color: #ee0a24;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 10px;
}

.delete-btn {
  height: 100%;
  width: 65px;
}

.van-swipe-cell {
  margin-bottom: 8px;
}

.history-item {
  position: relative;
  margin-bottom: 10px;
  background-color: #fff;
  border-radius: 8px;
  overflow: hidden;
}

.delete-btn {
  position: absolute;
  top: 50%;
  right: 10px;
  transform: translateY(-50%);
  z-index: 10;
  width: 24px;
  height: 24px;
  padding: 0;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.delete-icon {
  position: absolute;
  top: 50%;
  right: 15px;
  transform: translateY(-50%);
  width: 36px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f2f3f5;
  border-radius: 50%;
  z-index: 2;
}
</style>