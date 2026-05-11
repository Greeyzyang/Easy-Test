<template>
  <div class="global-assistant">
    <div class="floating-btn" @click="toggleVisible">
      <i class="el-icon-cpu"></i>
      <span class="pulse-ring"></span>
    </div>

    <el-dialog
      title="AI 牛马"
      :visible.sync="visible"
      width="50%"
      :append-to-body="true"
      custom-class="assistant-dialog"
      :modal="false"
      v-dialogDrag
    >
      <div class="chat-container">
        <div class="messages" ref="messagesContainer">
          <div
            v-for="(msg, index) in messages"
            :key="index"
            :class="['message', msg.role === 'user' ? 'user' : 'assistant']"
          >
            <div v-if="msg.content" class="content">
              <span v-if="msg.role === 'assistant'" class="avatar ai-avatar">
                <i class="el-icon-cpu"></i>
              </span>
              <div class="text" @click="handleMessageClick">
                <div v-if="msg.role === 'assistant'" v-html="renderMarkdown(msg.content)"></div>
                <div v-else>{{ msg.content }}</div>
              </div>
              <span v-if="msg.role === 'user'" class="avatar user-avatar">我</span>
            </div>
          </div>
          <div v-if="isThinking" class="message assistant">
             <div class="content">
               <span class="avatar ai-avatar thinking">
                 <i class="el-icon-cpu"></i>
               </span>
               <div class="text loading-text">
                 <div class="thinking-process">
                   <div class="thinking-dots">
                     <span></span><span></span><span></span>
                   </div>
                   <span class="thinking-label">AI 正在思考中...</span>
                 </div>
               </div>
             </div>
          </div>
        </div>
        <div class="input-area">
          <el-input
            v-model="input"
            type="textarea"
            :rows="2"
            placeholder="请输入您关于jira统计、报告分析或故障诊断的问题..."
            @keyup.enter.native="sendMessage"
          ></el-input>
          <el-button type="primary" :loading="loading" @click="sendMessage">发送</el-button>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { chatWithAgent } from '@/api/assistant'
import * as markedModule from 'marked'

export default {
  name: 'GlobalAssistant',
  directives: {
      // Simple directive for dragging dialog (if element-ui doesn't support it natively in this version, it might be ignored or need implementation)
      // For now we assume standard dialog behavior.
      dialogDrag: {
          bind(el, binding, vnode, oldVnode) {
              // Drag logic omitted for brevity, standard Element UI usually requires external directive or is static
          }
      }
  },
  data() {
    return {
      visible: false,
      input: '',
      messages: [
        { 
          role: 'assistant', 
          content: '您好！我是您的 **测试开发 AI 助手**。🚀\n\n我可以为您提供以下专业支持：\n- � **需求深度评审**：基于 Jira 需求进行多维度专业评审，识别潜在漏洞与风险。\n- 📝 **测试用例生成**：基于评审后的需求，一键生成高质量、多维度的测试用例。\n- 📈 **质量洞察与发布决策**：分析 Jira 缺陷分布、版本回归状态，辅助发布决策。\n- �️ **故障诊断与 SQL 校验**：深度分析测试报告定位根因，或执行安全 SQL 校验底层数据。\n- 📚 **知识库解答**：快速检索测试规范、最佳实践及项目技术文档。\n\n**建议流程**：先输入 `评审需求 XXX-123`，确认无误后再执行 `生成用例`。今天需要我协助处理哪个 Jira 需求？' 
        }
      ],
      loading: false,
      isThinking: false
    }
  },
  created() {
    // 配置 marked
    const markedObj = markedModule.marked || markedModule
    if (markedObj && markedObj.setOptions) {
      markedObj.setOptions({
        gfm: true,
        breaks: true,
        headerIds: false,
        mangle: false,
        smartLists: true,
        smartypants: true
      })
    }
  },
  methods: {
    toggleVisible() {
        this.visible = !this.visible
    },
    renderMarkdown(text) {
      if (!text) return ''
      try {
        // 0. 预处理：识别并保护 echarts 代码块，避免被 marked 破坏
        let processedText = text
        const chartBlocks = []
        processedText = processedText.replace(/```echarts\n([\s\S]*?)\n```/g, (match, content) => {
          const id = `chart-${Math.random().toString(36).substr(2, 9)}`
          chartBlocks.push({ id, content: content.trim() })
          return `<div id="${id}" class="echarts-container" style="width: 100%; height: 300px; margin: 15px 0;"></div>`
        })

        // 1. 预处理：确保表格前后有空行，但不要在表格行之间插入空行
        processedText = processedText.replace(/^([^|].*)\n(\s*\|)/gm, '$1\n\n$2')
        
        // 2. 增强链接：为下载链接添加标识，并处理相对路径
        processedText = processedText.replace(/\[点击下载 Excel 测试用例\]\((.*?)\)/g, (match, url) => {
          let finalUrl = url
          // 如果是相对路径且以 /rest 开头，则补全 Base API
          if (url.startsWith('/rest/')) {
            const baseUrl = process.env.VUE_APP_BASE_API || ''
            // 避免双斜杠
            finalUrl = baseUrl.replace(/\/$/, '') + '/' + url.replace(/^\//, '')
          }
          return `<a href="${finalUrl}" class="download-link" target="_blank"><i class="el-icon-download"></i> 点击下载 Excel 测试用例</a>`
        })
        
        // 3. 确保 marked 正确调用 (兼容不同版本和导入方式)
        const markedObj = markedModule.marked || markedModule
        const parseFn = (typeof markedObj.parse === 'function') ? markedObj.parse.bind(markedObj) : (typeof markedObj === 'function' ? markedObj : null)
        
        let html = processedText
        if (parseFn) {
          html = parseFn(processedText)
        }

        // 在渲染完成后异步初始化图表
        if (chartBlocks.length > 0) {
          this.$nextTick(() => {
            this.initCharts(chartBlocks)
          })
        }

        return html
      } catch (e) {
        console.error('Markdown parse error:', e)
        return text
      }
    },
    initCharts(blocks) {
      const echarts = require('echarts')
      blocks.forEach(block => {
        const el = document.getElementById(block.id)
        if (el) {
          try {
            const chart = echarts.init(el)
            const option = JSON.parse(block.content)
            chart.setOption(option)
            
            // 响应式处理
            window.addEventListener('resize', () => chart.resize())
          } catch (err) {
            console.error('ECharts init error:', err)
            el.innerHTML = `<div style="color: red; padding: 10px; border: 1px solid #ddd;">图表渲染失败: ${err.message}</div>`
          }
        }
      })
    },
    handleMessageClick(event) {
      // 拦截链接点击
      const target = event.target.closest('a')
      if (target && target.classList.contains('download-link')) {
        // 如果是下载链接，我们可以做一些额外的处理，比如记录日志
        console.log('Downloading test cases from:', target.href)
        // 默认行为（在新窗口打开链接）会被执行，因为我们设置了 target="_blank"
      }
    },
    async sendMessage() {
      if (!this.input.trim() || this.loading) return
      
      const userMsg = this.input
      this.messages.push({ role: 'user', content: userMsg })
      this.input = ''
      this.loading = true
      this.isThinking = true
      
      // 创建一个空的助手回复消息对象
      const assistantMsg = { role: 'assistant', content: '' }
      this.messages.push(assistantMsg)
      
      this.scrollToBottom()

      try {
        const token = this.$store.getters.token
        const response = await fetch(process.env.VUE_APP_BASE_API + '/rest/v1/ai/chat/', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer ' + token
          },
          body: JSON.stringify({
            message: userMsg,
            history: this.messages.slice(-11, -2).map(m => ({ role: m.role, content: m.content })),
            stream: true
          })
        })

        if (!response.ok) {
          throw new Error('网络响应错误: ' + response.status)
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          
          const chunk = decoder.decode(value, { stream: true })
          if (!chunk) continue

          // 当收到非空的有效数据时，停止显示“思考中”占位符
          if (this.isThinking) {
            this.isThinking = false
          }
          
          assistantMsg.content += chunk
          this.scrollToBottom()
        }
      } catch (e) {
        console.error('Streaming error:', e)
        assistantMsg.content = '网络错误或请求超时：' + e.message
      } finally {
        this.loading = false
        this.isThinking = false
        this.scrollToBottom()
      }
    },
    scrollToBottom() {
      this.$nextTick(() => {
        const container = this.$refs.messagesContainer
        if (container) {
          container.scrollTop = container.scrollHeight
        }
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.global-assistant {
  position: fixed;
  bottom: 30px;
  right: 30px;
  z-index: 2000;
}

.floating-btn {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  cursor: pointer;
  box-shadow: 0 4px 20px rgba(118, 75, 162, 0.4);
  transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
  position: relative;
  z-index: 1;

  &:hover {
    transform: scale(1.1) rotate(5deg);
    box-shadow: 0 6px 24px rgba(118, 75, 162, 0.6);
  }

  .pulse-ring {
    content: "";
    width: 100%;
    height: 100%;
    background: inherit;
    border-radius: 50%;
    position: absolute;
    top: 0;
    left: 0;
    z-index: -1;
    animation: pulse 2s infinite;
    opacity: 0.6;
  }
}

@keyframes pulse {
  0% {
    transform: scale(1);
    opacity: 0.6;
  }
  70% {
    transform: scale(1.5);
    opacity: 0;
  }
  100% {
    transform: scale(1);
    opacity: 0;
  }
}

.chat-container {
  display: flex;
  flex-direction: column;
  height: 50vh;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 10px;
  border: 1px solid #e6ebf5;
  border-radius: 4px;
  margin-bottom: 10px;
  background: #f9f9f9;
}

.message {
  margin-bottom: 15px;
  .content {
    display: flex;
    align-items: flex-start;
  }
  
  &.user {
    .content {
      justify-content: flex-end;
      .text {
        background: #e6f7ff;
        color: #333;
        margin-right: 10px;
        border-top-right-radius: 0;
      }
      .avatar {
          background: #67C23A;
      }
    }
  }
  
  &.assistant {
    .content {
      justify-content: flex-start;
      .avatar {
        background: #409EFF;
      }
      .text {
        background: #f4f4f5;
        color: #333;
        margin-left: 10px;
        border-top-left-radius: 0;
        max-width: 90%; // 增加宽度以容纳表格

        // Markdown 表格样式
        ::v-deep table {
          border-collapse: collapse;
          width: 100%;
          margin: 15px 0;
          background-color: #fff;
          border: 1px solid #dfe2e5;
          display: table; // 恢复为 table 布局
          overflow-x: auto;
          
          th, td {
            border: 1px solid #dfe2e5;
            padding: 8px 12px;
            text-align: left;
            font-size: 13px;
          }
          
          th {
            background-color: #f6f8fa;
            font-weight: 600;
          }
          
          tr:nth-child(2n) {
            background-color: #f6f8fa;
          }
        }

        // 下载链接样式
        ::v-deep .download-link {
          display: inline-block;
          margin: 10px 0;
          padding: 8px 16px;
          background-color: #67c23a;
          color: white !important;
          border-radius: 4px;
          text-decoration: none !important;
          font-weight: bold;
          transition: all 0.3s;
          box-shadow: 0 2px 4px rgba(0,0,0,0.1);

          &:hover {
            background-color: #85ce61;
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
            transform: translateY(-1px);
          }

          i {
            margin-right: 5px;
          }
        }

        // Markdown 引用样式 (用于思考过程)
        ::v-deep blockquote {
          margin: 10px 0;
          padding: 8px 15px;
          color: #666;
          border-left: 4px solid #dfe2e5;
          background-color: #f8f9fa;
          font-style: normal;
          border-radius: 0 4px 4px 0;
          
          p {
            margin: 5px 0;
            font-size: 13px;
            line-height: 1.5;
            color: #606266;
          }
        }

        // 代码块样式
        ::v-deep pre {
          background-color: #282c34;
          color: #abb2bf;
          padding: 10px;
          border-radius: 4px;
          overflow-x: auto;
          margin: 10px 0;
          
          code {
            font-family: 'Consolas', 'Monaco', monospace;
          }
        }

        // 行内代码
        ::v-deep code {
          background-color: rgba(27,31,35,0.05);
          padding: 0.2em 0.4em;
          border-radius: 3px;
          font-family: 'Consolas', 'Monaco', monospace;
        }

        // 标题样式
        ::v-deep h1, ::v-deep h2, ::v-deep h3, ::v-deep h4 {
          margin-top: 15px;
          margin-bottom: 10px;
          font-weight: 600;
          line-height: 1.25;
        }
        
        ::v-deep h3 { font-size: 1.25em; }
      }
    }
  }
  
  .avatar {
    width: 36px;
    height: 36px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 14px;
    flex-shrink: 0;
    font-weight: bold;
    box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    
    &.ai-avatar {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      color: #fff;
      font-size: 20px;
      
      &.thinking {
        animation: ai-pulse 2s infinite ease-in-out;
      }
    }
    
    &.user-avatar {
      background: #e2e8f0;
      color: #4a5568;
    }
  }
  
  .text {
    padding: 10px 14px;
    border-radius: 12px;
    max-width: 80%;
    word-break: break-word;
    line-height: 1.6;
    font-size: 14px;
    box-shadow: 0 2px 12px 0 rgba(0,0,0,0.05);
    
    &.loading-text {
      background: #fff;
      border: 1px solid #ebeef5;
      padding: 12px 20px;
    }
  }
}

// 思考中的新动画效果
.thinking-process {
  display: flex;
  align-items: center;
  gap: 12px;
}

.thinking-dots {
  display: flex;
  gap: 4px;
  
  span {
    width: 8px;
    height: 8px;
    background-color: #409EFF;
    border-radius: 50%;
    display: inline-block;
    animation: thinking-bounce 1.4s infinite ease-in-out both;
    
    &:nth-child(1) { animation-delay: -0.32s; }
    &:nth-child(2) { animation-delay: -0.16s; }
    &:nth-child(3) { animation-delay: 0s; }
  }
}

.thinking-label {
  font-size: 13px;
  color: #606266;
  font-weight: 500;
  letter-spacing: 0.5px;
}

@keyframes thinking-bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1.0); }
}

@keyframes ai-pulse {
  0% { box-shadow: 0 0 0 0 rgba(118, 75, 162, 0.4); }
  70% { box-shadow: 0 0 0 10px rgba(118, 75, 162, 0); }
  100% { box-shadow: 0 0 0 0 rgba(118, 75, 162, 0); }
}

// 优化 Markdown 引用样式 (用于思考过程)
.assistant .text ::v-deep blockquote {
  margin: 12px 0;
  padding: 12px 16px;
  color: #555;
  border-left: 4px solid #409EFF;
  background-color: #f0f7ff;
  border-radius: 4px;
  font-style: normal;
  box-shadow: inset 0 0 10px rgba(64, 158, 255, 0.05);
  
  p {
    margin: 4px 0;
    font-family: "PingFang SC", "Helvetica Neue", Helvetica, Arial, sans-serif;
    font-size: 13px;
    line-height: 1.5;
    
    // 针对“思考”、“行动”、“观察”关键词加重显示
    strong {
      color: #409EFF;
    }
  }
}

.input-area {
  display: flex;
  gap: 10px;
  align-items: flex-end;
}

// Markdown 表格样式
::v-deep table {
  width: 100%;
  border-collapse: collapse;
  margin: 10px 0;
  font-size: 13px;
  background-color: #fff;
  border: 1px solid #ebeef5;

  th, td {
    border: 1px solid #ebeef5;
    padding: 8px 12px;
    text-align: left;
  }

  th {
    background-color: #f5f7fa;
    color: #909399;
    font-weight: 600;
  }

  tr:nth-child(even) {
    background-color: #fafafa;
  }

  tr:hover {
    background-color: #f5f7fa;
  }
}

// 下载链接按钮样式
::v-deep .download-link {
  display: inline-block;
  margin: 10px 0;
  padding: 8px 16px;
  background-color: #67c23a;
  color: white !important;
  border-radius: 4px;
  text-decoration: none !important;
  font-weight: bold;
  transition: all 0.3s;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);

  &:hover {
    background-color: #85ce61;
    box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    transform: translateY(-1px);
  }

  i {
    margin-right: 5px;
  }
}
</style>
