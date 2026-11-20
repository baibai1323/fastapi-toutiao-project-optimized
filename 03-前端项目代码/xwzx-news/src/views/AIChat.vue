<template>
  <div class="ai-chat-container">
    <van-nav-bar title="AI问答" fixed />
    
    <div class="chat-content">
      <!-- [优化] 后端无 Key 时会返回 X-AI-Mode: mock；明确告诉用户这是预设回复，避免误解。 -->
      <div v-if="isMockMode" class="demo-banner">
        演示模式：未配置 API Key，以下为预设流式回复，不会调用真实模型
      </div>
      <div class="messages-container" ref="messagesContainer">
        <div 
          v-for="(message, index) in messages" 
          :key="index" 
          :class="['message', message.role === 'user' ? 'user-message' : 'ai-message']"
        >
          <div class="message-content">
            <div v-if="message.role === 'assistant' && message.content === ''" class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
            <div v-else v-html="formatMessage(message.content)"></div>
          </div>
        </div>
      </div>
      
      <div class="input-container">
        <van-field
          v-model="userInput"
          rows="1"
          autosize
          type="textarea"
          placeholder="请输入问题..."
          class="chat-input"
          @keypress.enter.prevent="sendMessage"
        />
        <van-button 
          type="primary" 
          class="send-button" 
          :disabled="isLoading || !userInput.trim()" 
          @click="sendMessage"
        >
          发送
        </van-button>
      </div>
    </div>
    
    <tab-bar />
  </div>
</template>

<script setup>
// 这是“和 AI 对话”页面。页面本身不难，难点在文件后半段：怎么把服务端一段一段推来的
// 流式数据（SSE）拼成完整回复，并在用户离开时及时断开连接。
import { ref, onMounted, onBeforeUnmount, nextTick, watch } from 'vue';
import { useRouter } from 'vue-router';
import TabBar from '../components/TabBar.vue';
import { showToast } from 'vant';
// marked 把 Markdown 文本转成 HTML；DOMPurify 负责清洗，防止 AI 输出里夹带恶意脚本（XSS）。
import * as marked from 'marked';
import DOMPurify from 'dompurify';
// aiChatConfig 决定用哪个模型名，apiConfig 提供后端地址前缀。
import { aiChatConfig, apiConfig } from '../config/api';
import { useUserStore } from '../store/user';

/**
 * [优化] 原代码问题：
 *   1. fetch('/api/ai/chat') 不带 Authorization，后端加鉴权后直接 401；
 *   2. 没有 AbortController，离开页面后流还在读，浪费连接；
 *   3. 只按单行 '\n' 拆 SSE，跨 chunk 的事件可能被截断；
 *   4. 没登录也能进入页面发请求。
 * 修复：带 Bearer、组件卸载时 abort、按 '\n\n' 解析完整事件、进入页面先检查登录。
 */

// 聊天消息
// messages 是对话记录数组，每项形如 { role: 'user'|'assistant', content: '文字' }，模板用 v-for 渲染成气泡。
const messages = ref([
  { role: 'assistant', content: '你好！我是AI助手，有什么可以帮助你的吗？' }
]);
// 输入框的内容，和模板里的 van-field 通过 v-model 双向绑定，发送成功后会被清空。
const userInput = ref('');
// 指向消息列表那个 DOM 节点；只有拿到它才能算出“滚到底部”要滚多少。
const messagesContainer = ref(null);
// 是否正在等回复：为 true 时发送按钮禁用，防止用户连点造成消息顺序错乱。
const isLoading = ref(false);
// 后端没配 API Key 时返回的是预设回复，用这个标记在顶部提示用户，避免误以为真调了模型。
const isMockMode = ref(false);

// 用户仓库：本页主要用它的 token（请求要带）和登录状态（没登录不让用）。
const userStore = useUserStore();
const router = useRouter();
// 保存当前的“取消控制器”，离开页面时用它中断还没读完的流，否则连接会一直挂着。
let currentAbort = null;

// 从配置文件获取API设置
// 模型名写在配置文件里，一般不用改；用 ref 包一层是为了以后能做成可切换。
const model = ref(aiChatConfig.model);   // 保留

// 格式化消息内容（支持Markdown）
// AI 回复里常有列表、代码块等 Markdown 语法，先由 marked 转成 HTML，再由 DOMPurify 去掉危险标签。
const formatMessage = (content) => {
  // 空内容直接返回空串，否则 marked 可能解析出意料之外的结构。
  if (!content) return '';
  // 使用marked解析Markdown，并用DOMPurify清理HTML
  // sanitize 是最后一道安全关：即使 AI 输出了 <script>，也会被清掉，不会在页面里执行。
  return DOMPurify.sanitize(marked.parse(content));
};

// 发送消息
// 流程：校验登录与内容 → 用户气泡上屏 → 插入空白 AI 气泡 → 请求流式回复 → 滚动到底。
const sendMessage = async () => {
  // 未登录直接拦下并跳登录页：后端接口要求 token，发出去也只会收到 401。
  if (!userStore.getLoginStatus) {
    showToast('请先登录');
    router.push('/login');
    return;
  }
  // 空内容或上一条还没回完就忽略这次发送；trim() 先去掉首尾空格再判断，避免全是空格也算有内容。
  if (!userInput.value.trim() || isLoading.value) return;
  

  
  // 添加用户消息
  // 先把输入内容存成快照再清空输入框：后面发请求用的是快照，否则用户接着打字会改掉要发送的内容。
  const userMessage = userInput.value.trim();
  messages.value.push({ role: 'user', content: userMessage });
  userInput.value = '';
  
  // 添加AI消息占位
  // 先插一条内容为空的 AI 气泡：模板看到空内容就会显示“正在输入”的三个跳动小点。
  messages.value.push({ role: 'assistant', content: '' });
  
  // 滚动到底部
  // nextTick 等 Vue 把新气泡真正渲染到 DOM 之后再滚，否则算出来的高度还是旧的。
  await nextTick();
  scrollToBottom();
  
  // 发送请求
  // 置为 true 后发送按钮自动禁用，防止用户在等待期间重复发送。
  isLoading.value = true;
  try {
    await fetchAIResponse(userMessage);
  } catch (error) {
    console.error('Error fetching AI response:', error);
    // 更新最后一条消息为错误信息
    // 把错误写进最后一条气泡，用户能在对话里直接看到原因，而不是只弹一个一闪而过的提示。
    messages.value[messages.value.length - 1].content = `发生错误: ${error.message || '请检查网络连接和API设置'}`;
  } finally {
    // finally 无论成功还是失败都会执行：恢复按钮可用状态，并再滚一次，确保看到最新内容。
    isLoading.value = false;
    await nextTick();
    scrollToBottom();
  }
};

// 获取AI响应（SSE）
// SSE（Server-Sent Events）是服务端“边生成边推送”的协议：每个事件以空行结尾，正文写在 data: 后面。
// 这里要做的是把一截截网络数据拼回一个个完整事件，再把事件里的 JSON 取出来。
const fetchAIResponse = async (userMessage) => {
  // 只把已有的对话发给后端；slice(0, -1) 去掉刚插入的那个内容为空的 AI 占位气泡。
  const allMessages = messages.value
    .slice(0, -1) // 排除最后一个空的 assistant 占位
    .map((msg) => ({ role: msg.role, content: msg.content }));

  // AbortController 是浏览器提供的“取消开关”，把它传给 fetch，就能在页面卸载时中断请求。
  const controller = new AbortController();
  currentAbort = controller;

  // 整个流程分三步：发请求 → 逐块读流 → 按空行切出完整事件并解析。
  try {
    // POST 到后端聊天接口，headers 说明请求格式与身份，body 是对话内容，signal 用于取消。
    const response = await fetch(`${apiConfig.baseURL}/api/v1/ai/chat`, {
      method: 'POST',
      headers: {
        // 告诉后端请求体是 JSON，否则服务端可能解析不出参数。
        'Content-Type': 'application/json',
        // [优化] 后端已要求登录，必须带 Bearer。
        // Bearer 是一种鉴权格式：后端只认 "Bearer + 空格 + token" 这样的写法。
        Authorization: `Bearer ${userStore.token}`,
      },
      body: JSON.stringify({
        // model 用 .value 取当前值：ref 相当于“装着值的盒子”，必须拆开才能读到里面。
        model: model.value,
        messages: allMessages,
      }),
      signal: controller.signal,
    });

    // 401 表示没登录或 token 已过期：先清掉本地登录态再回登录页，避免在坏状态下继续重试。
    if (response.status === 401) {
      userStore.logout();
      router.push('/login');
      throw new Error('登录已过期，请重新登录');
    }

    // fetch 只在网络层失败时 reject，4xx/5xx 仍要自己检查 response.ok。
    if (!response.ok) {
      // 先试着读后端返回的 JSON 错误信息，读不到（返回的不是 JSON）就退回状态码，保证总有文案。
      const error = await response.json().catch(() => ({}));
      throw new Error(error.message || error.detail || `HTTP error! status: ${response.status}`);
    }

    // [优化] 让用户知道当前是演示回复，而不是真实模型输出。
    // 后端用自定义响应头 X-AI-Mode 标记“这次是 mock”，前端据此显示顶部横幅。
    isMockMode.value = response.headers.get('X-AI-Mode') === 'mock';

    // response.body 是可读流，getReader() 得到“分段读取器”：可以边下载边处理，不必等全文。
    const reader = response.body.getReader();
    // TextDecoder 把二进制字节解码成文字；网络分块可能正好切断一个汉字，所以要配合 stream:true。
    const decoder = new TextDecoder();
    // buffer 暂存“还没凑成完整事件”的半截数据，这是流式解析的关键变量。
    let buffer = '';
    // aiResponse 累积已经收到的正文，每来一小段就整体替换气泡内容。
    let aiResponse = '';

    // [优化] 按 SSE 的空行分隔完整事件，避免 JSON 被网络 chunk 截断。
    // 一个事件里可能有多行 data:，按规范要用换行拼起来；返回 true 表示收到了结束标记。
    const consumeEvent = (eventText) => {
      // 事件由若干行组成，这里只挑 data: 开头的行，event:/id: 等字段本页用不到。
      const dataLines = eventText
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        // slice(5) 去掉 "data:" 这 5 个字符，trimStart 再去掉后面可能多的空格。
        .map((line) => line.slice(5).trimStart());

      // 没有数据行说明是心跳或注释，直接跳过；返回 false 表示对话还没结束。
      if (dataLines.length === 0) return false;

      const data = dataLines.join('\n');
      // [DONE] 是各家约定的结束标记，返回 true 让外层停止继续解析。
      if (data === '[DONE]') return true;

      // 不同后端的返回结构不一样，下面按几种常见格式依次兜底取值。
      try {
        const json = JSON.parse(data);
        // choices[0].delta.content 是 OpenAI 风格；output.text 是另一种简化格式。
        const content =
          json.choices?.[0]?.delta?.content ||
          json.output?.text ||
          json.choices?.[0]?.message?.content ||
          '';
        // 有内容才追加：有些事件只带角色信息或结束标记，正文是空的。
        if (content) {
          aiResponse += content;
          messages.value[messages.value.length - 1].content = aiResponse;
          // 每收到一小段就滚到底部，视觉上就像 AI 在一个字一个字“打字”。
          nextTick(scrollToBottom);
        }
      } catch (e) {
        // 单条事件解析失败不能中断整个对话，打日志后跳过即可。
        console.error('解析SSE数据失败:', e, data);
      }
      return false;
    };

    // 一直读，直到服务端关闭连接（done 变成 true）。
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      // stream:true 告诉解码器“后面还有数据”，遇到半个汉字时先留在内部缓冲，不会出现乱码。
      buffer += decoder.decode(value, { stream: true });
      // 统一换行符：有的服务端用 \r\n，不统一就会找不到空行分隔符。
      buffer = buffer.replace(/\r\n/g, '\n');

      // indexOf('\n\n') 找事件边界；返回 -1 说明还没收到完整事件，继续读下一块。
      let boundary = buffer.indexOf('\n\n');
      // 一个网络 chunk 里可能含多个完整事件，所以要循环切直到没有边界。
      while (boundary !== -1) {
        // 切出这个事件的文本，剩下的继续留在 buffer 里等下一块数据。
        const eventText = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        // consumeEvent 返回 true 表示收到了 [DONE]，清空缓冲并跳出内层循环。
        if (consumeEvent(eventText)) {
          buffer = '';
          break;
        }
        boundary = buffer.indexOf('\n\n');
      }
    }

    // 流结束时缓冲里可能还剩最后一个事件（没有结尾空行），这里补做一次解析。
    if (buffer.trim()) {
      consumeEvent(buffer);
    }

    // 一个字都没收到说明后端异常或返回空，给用户明确文案，而不是留一个空白气泡。
    if (!aiResponse) {
      messages.value[messages.value.length - 1].content = '抱歉，无法生成回复。';
    }
  } catch (error) {
    // AbortError 是我们主动 abort（比如离开页面）造成的，属于预期情况，提示“已停止”即可。
    if (error.name === 'AbortError') {
      messages.value[messages.value.length - 1].content = '已停止生成。';
      return;
    }
    console.error('请求代理接口失败:', error);
    messages.value[messages.value.length - 1].content = `请求失败：${error.message}`;
    // 其它错误继续往外抛，交给 sendMessage 的 catch 统一展示。
    throw error;
  } finally {
    // 请求结束（成功或失败）都要清空取消开关，避免下次误 abort 到已经结束的请求。
    currentAbort = null;
  }
};

// 滚动到底部
// scrollHeight 是内容总高度，scrollTop 是当前滚动位置；把后者设成前者，滚动条就落到最底部。
const scrollToBottom = () => {
  // 先判断 ref 是否已经有值：组件刚创建时它还是 null，直接读会报错。
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

// 监听消息变化，自动滚动
// deep:true 表示“深层监听”：数组里某个对象的 content 变了也要触发，否则流式追加不会滚。
watch(messages, () => {
  // 用 nextTick 等 DOM 更新完再滚动，否则滚动位置按旧高度算，会差一截。
  nextTick(scrollToBottom);
}, { deep: true });

// 组件挂载时检查登录并滚动到底部
// 未登录用户进来也没法发消息，所以直接提示并送去登录页。
onMounted(() => {
  if (!userStore.getLoginStatus) {
    showToast('请先登录');
    router.push('/login');
    return;
  }
  scrollToBottom();
});

// [优化] 离开页面时中断未完成的 SSE 请求，避免内存/连接泄漏。
// onBeforeUnmount 是组件销毁前最后一个钩子，适合做“收尾”工作。
onBeforeUnmount(() => {
  if (currentAbort) {
    // abort() 会让正在 await 的 reader.read() 抛 AbortError，请求随即结束。
    currentAbort.abort();
    currentAbort = null;
  }
});
</script>

<style scoped>
.ai-chat-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding-top: 46px;
  padding-bottom: 50px;
  box-sizing: border-box;
}

.chat-content {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.demo-banner {
  flex: 0 0 auto;
  padding: 6px 10px;
  background: #fff7e6;
  color: #ad6800;
  border-bottom: 1px solid #ffe7ba;
  font-size: 12px;
  line-height: 1.4;
  text-align: center;
}

.messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
}

.message {
  margin-bottom: 10px;
  max-width: 80%;
}

.user-message {
  margin-left: auto;
}

.ai-message {
  margin-right: auto;
}

.message-content {
  padding: 10px;
  border-radius: 10px;
  word-break: break-word;
}

.user-message .message-content {
  background-color: #007aff;
  color: white;
}

.ai-message .message-content {
  background-color: #f2f2f2;
  color: #333;
}

.input-container {
  display: flex;
  padding: 10px;
  border-top: 1px solid #eee;
  background-color: #fff;
}

.chat-input {
  flex: 1;
  margin-right: 10px;
}

.send-button {
  align-self: flex-end;
}

/* Markdown 样式 */
.message-content pre {
  background-color: #f8f8f8;
  padding: 10px;
  border-radius: 5px;
  overflow-x: auto;
}

.message-content code {
  background-color: rgba(0, 0, 0, 0.05);
  padding: 2px 4px;
  border-radius: 3px;
}

.message-content img {
  max-width: 100%;
}

/* 打字指示器 */
.typing-indicator {
  display: flex;
  padding: 5px;
}

.typing-indicator span {
  height: 8px;
  width: 8px;
  background-color: #999;
  border-radius: 50%;
  margin: 0 2px;
  display: inline-block;
  animation: bounce 1.5s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes bounce {
  0%, 60%, 100% {
    transform: translateY(0);
  }
  30% {
    transform: translateY(-5px);
  }
}

/* Markdown样式 */
:deep(pre) {
  background-color: #f0f0f0;
  padding: 10px;
  border-radius: 4px;
  overflow-x: auto;
}

:deep(code) {
  font-family: monospace;
  background-color: #f0f0f0;
  padding: 2px 4px;
  border-radius: 4px;
}

:deep(p) {
  margin: 8px 0;
}

:deep(ul), :deep(ol) {
  padding-left: 20px;
}

:deep(a) {
  color: #1989fa;
  text-decoration: none;
}
</style>