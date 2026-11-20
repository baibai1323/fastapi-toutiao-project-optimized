<template>
  <div class="favorite-container">
    <van-nav-bar
      title="我的收藏"
      left-text="返回"
      left-arrow
      @click-left="onClickLeft"
      right-text="清空"
      @click-right="onClickClear"
      fixed
    />
    
    <div class="favorite-list" v-if="favoriteStore.getFavorites.length">
      <div class="favorite-item" v-for="item in favoriteStore.getFavorites" :key="item.id">
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
                  <span>收藏时间: {{ item.favoriteTime }}</span>
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
    
    <van-empty v-else description="暂无收藏内容" />
  </div>
</template>

<script setup>
// 收藏页：列出所有已收藏的新闻，支持单条删除和一键清空。
// 数据放在 Pinia 仓库（favoriteStore）里，本页只负责展示和触发增删，不直接读写 localStorage。
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
// 收藏仓库：同时维护内存列表与本地缓存，并封装了收藏相关的接口请求。
import { useFavoriteStore } from '../store/modules/favorite';
// showDialog 是带“取消/确认”的弹窗，删除属于不可撤销操作，必须先让用户确认。
import { showDialog } from 'vant';

const router = useRouter();
const favoriteStore = useFavoriteStore();

// 返回上一页
// 用 back() 回到进入本页的那一页（通常是“我的”），比写死路径更符合用户预期。
const onClickLeft = () => {
  router.back();
};

// 跳转到新闻详情
// 收藏列表里每一项都带着自己的 id，拼进路由就能打开对应文章。
const goToNewsDetail = (id) => {
  router.push(`/news/detail/${id}`);
};

// 删除单条收藏
// 先请求服务端删除、成功后再改本地列表；反过来的话服务端失败但界面已删，用户会误以为删掉了。
const removeFavorite = async (id) => {
  const result = await favoriteStore.removeFavoriteApi(id);
  if (result.success) {
    // API请求成功后，更新本地收藏列表
    // 这里删的是仓库里的那一项，列表是响应式的，页面会立刻少一行。
    favoriteStore.removeFavorite(id);
  }
};

// 确认删除
// showDialog 返回 Promise：点“确认”时 action 为 'confirm'，点“取消”时走 reject。
const confirmDelete = (id) => {
  showDialog({
    title: '提示',
    message: '确定要删除这条收藏吗？',
    showCancelButton: true,
  }).then((action) => {
    // 只有点“确认”才真正删除；点“取消”什么都不做，删除动作绝不能默认执行。
    if (action === 'confirm') {
      removeFavorite(id);
    }
  });
};

// 清空收藏
// 清空比删一条更危险，所以同样先弹窗确认；成功后仓库把列表置空，模板会自动显示空状态。
const onClickClear = async () => {
  showDialog({
    title: '提示',
    message: '确定要清空所有收藏吗？',
    showCancelButton: true,
  }).then(async (action) => {
    // 用户点“取消”时 Promise 走 reject，不会进入这里，列表保持原样。
    if (action === 'confirm') {
      // 一次请求清空服务端记录，比循环逐条删除省掉很多次网络往返。
      const result = await favoriteStore.clearFavoritesApi();
      // 先判断 result 是否存在再取 .success，避免接口没返回时读 undefined 报错。
      if (!result || !result.success) {
        // 如果API请求失败，回退到本地清空
        // favoriteStore.clearFavorites();
        console.log('清空收藏列表');
      }
    }
  });
};

// 组件挂载时加载收藏数据
// onMounted 是页面显示到屏幕上之后执行一次的钩子，首屏数据在这里拉。
onMounted(async () => {
  // 使用API请求获取收藏列表
  try {

    // 已登录时以服务端列表为准，这样换设备登录也能看到同样的收藏。
    const result = await favoriteStore.getFavoriteListApi();
    // 未登录或令牌过期时后端会返回失败，这里静默回退，不弹错误打扰用户。
    if (!result || !result.success) {
      // 如果API请求失败，回退到本地存储
      // favoriteStore.loadFavorites();
      console.log('从本地存储加载收藏列表');  
    }
  } catch (error) {
    // 网络异常说明请求根本没发出去，直接读本地缓存，至少让页面有内容可看。
    favoriteStore.loadFavorites();
  }
});
</script>

<style scoped>
.favorite-container {
  padding-top: 46px;
  padding-bottom: 20px;
  background-color: #f7f8fa;
  min-height: 100vh;
}

.favorite-list {
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

.favorite-item {
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
</style>