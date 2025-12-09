<template>
  <div class="app-container">
    <el-card class="kb-card" shadow="never">
      <div slot="header" class="hero-header">
        <div class="hero-title">
          <i class="el-icon-reading"></i>
          <span>知识库问答</span>
        </div>
        <div class="hero-actions">
          <el-tag type="success" size="small">RAG</el-tag>
        </div>
      </div>
      <el-form :model="form" label-width="100px">
        <el-form-item label="问题">
          <el-input v-model="form.question" type="textarea" :rows="3" placeholder="请输入要查询的问题" />
        </el-form-item>
        <el-form-item label="TopK">
          <div class="topk-row">
            <el-input-number v-model="form.top_k" :min="1" :max="10" />
            <el-slider v-model="form.top_k" :min="1" :max="10" :step="1" show-stops class="topk-slider" />
          </div>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" @click="onQuery">查询</el-button>
          <el-button @click="onReset">重置</el-button>
        </el-form-item>
        
        <el-steps v-if="loading" :active="activeStep" align-center finish-status="success" class="progress-steps">
          <el-step title="加载文档"/>
          <el-step title="切分片段"/>
          <el-step title="向量检索"/>
          <el-step title="生成答案"/>
          <el-step title="完成"/>
        </el-steps>
        <div v-if="loading" class="progress-block">
          <el-progress :percentage="progressPercent" :text-inside="true" :stroke-width="18" status="success" />
          <div class="progress-text">{{ progressText }}</div>
        </div>
      </el-form>
    </el-card>

    <el-card v-if="answer || sources.length" class="result-card" shadow="never">
      <div slot="header" class="result-header">
        <span>查询结果</span>
        <div class="result-actions">
          <el-button v-if="answer" type="text" icon="el-icon-document-copy" @click="copyAnswer"></el-button>
          <el-input v-model="filterText" clearable placeholder="筛选来源片段" size="small" class="list-search" />
        </div>
      </div>
      <div v-if="answer" class="answer-block">
        <div class="answer-title">答案</div>
        <div class="answer-text">{{ answer }}</div>
      </div>
      <div v-if="sources.length" class="sources-block">
        <div class="sources-title">来源片段</div>
        <el-table :data="filteredSources" border style="width: 100%">
          <el-table-column label="页码" width="100" align="center">
            <template slot-scope="scope">{{ normalizePage(scope.row.page) }}</template>
          </el-table-column>
          <el-table-column label="内容">
            <template slot-scope="scope">
              <pre class="snippet">{{ scope.row.content }}</pre>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" align="center">
            <template slot-scope="scope">
              <el-button type="text" icon="el-icon-document-copy" @click="copySource(scope.row)"></el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-card>
  </div>
</template>

<script>
import { kbQuery } from '@/api/assistant'

export default {
  name: 'KnowledgeBase',
  data: function() {
    return {
      form: {
        question: '',
        top_k: 4
      },
      loading: false,
      taskId: null,
      taskStatus: '',
      ws: null,
      progressPercent: 0,
      progressText: '',
      answer: '',
      sources: [],
      filterText: ''
    }
  },
  computed: {
    filteredSources: function() {
      const q = (this.filterText || '').toLowerCase()
      if (!q) return this.sources
      return this.sources.filter(function(s) {
        const c = String(s.content || '').toLowerCase()
        const p = String(s.page || '').toLowerCase()
        return c.includes(q) || p.includes(q)
      })
    },
    activeStep: function() {
      const p = Number(this.progressPercent || 0)
      if (p >= 100) return 4
      if (p >= 75) return 3
      if (p >= 50) return 2
      if (p >= 25) return 1
      return 0
    }
  },
  methods: {
    onQuery: function() {
      if (!this.form.question || !this.form.question.trim()) {
        this.$message.warning('请输入问题')
        return
      }
      this.loading = true
      const self = this
      kbQuery({ question: this.form.question, top_k: this.form.top_k })
        .then(function(res) {
          const payload = (res && res.data && (res.data.data || res.data)) || {}
          if (payload.task_id) {
            self.taskId = payload.task_id
            self.taskStatus = '任务已提交，等待执行...'
            self.startWebSocket()
          } else {
            const data = payload || {}
            self.answer = data.answer || ''
            self.sources = Array.isArray(data.sources) ? data.sources : []
            if (!self.answer && self.sources.length === 0) {
              self.$message.info('未检索到相关内容')
            }
          }
        })
        .catch(function(e) {
          const msg = (e && e.message) || '查询失败'
          self.$message.error(msg)
        })
        .finally(function() {
          if (!self.taskId) {
            self.loading = false
          }
        })
    },
    startWebSocket: function() {
      const baseApi = process.env.VUE_APP_BASE_API
      let wsHost
      if (baseApi && baseApi.startsWith('http')) {
        wsHost = baseApi.replace(/^http/, 'ws')
      } else {
        wsHost = window.location.origin.replace(/^http/, 'ws') + (baseApi || '')
      }
      const wsUrl = wsHost + '/rest/v1/ai/ws/progress/' + this.taskId
      try {
        if (this.ws) {
          try { this.ws.close() } catch (e) {}
        }
        this.ws = new WebSocket(wsUrl)
      } catch (e) {
        this.$message.error('WebSocket 连接失败')
        this.loading = false
        return
      }
      const self = this
      this.ws.onopen = function() {
        self.taskStatus = 'WebSocket已连接，等待结果...'
      }
      this.ws.onmessage = function(event) {
        let msg
        try {
          msg = JSON.parse(event.data)
        } catch (e) {
          msg = {}
        }
        const status = msg.status
        if (status === 'PROGRESS') {
          const progress = msg.progress || 0
          const text = msg.text || '处理中...'
          self.progressPercent = progress
          self.progressText = text
        } else if (status === 'SUCCESS') {
          const content = msg.result || {}
          self.answer = content.answer || ''
          self.sources = Array.isArray(content.sources) ? content.sources : []
          self.loading = false
          self.progressPercent = 100
          self.progressText = '完成'
          try { self.ws.close() } catch (e) {}
          self.ws = null
          if (!self.answer && self.sources.length === 0) {
            self.$message.info('未检索到相关内容')
          }
        } else if (status === 'FAILURE') {
          const err = (msg && (msg.text || msg.message)) || '任务失败'
          self.$message.error(err)
          self.loading = false
          self.progressText = '失败'
          try { self.ws.close() } catch (e) {}
          self.ws = null
        }
      }
      this.ws.onerror = function() {
        self.$message.error('WebSocket 连接错误')
        self.loading = false
        try { self.ws.close() } catch (e) {}
        self.ws = null
      }
      this.ws.onclose = function() {
        // no-op
      }
    },
    onReset: function() {
      this.form.question = ''
      this.form.top_k = 4
      this.answer = ''
      this.sources = []
      this.taskId = null
      this.taskStatus = ''
      this.progressPercent = 0
      this.progressText = ''
      if (this.ws) { try { this.ws.close() } catch (e) {}; this.ws = null }
    },
    normalizePage: function(p) {
      const n = Number(p)
      if (Number.isFinite(n) && n > 0) return n
      return ''
    },
    copyAnswer: function() {
      const ta = document.createElement('textarea')
      ta.value = String(this.answer || '')
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      this.$message.success('答案已复制到剪贴板')
    },
    copySource: function(row) {
      const ta = document.createElement('textarea')
      ta.value = `Page: ${this.normalizePage(row.page)}\n\n${String(row.content || '')}`
      document.body.appendChild(ta)
      ta.select()
      document.execCommand('copy')
      document.body.removeChild(ta)
      this.$message.success('片段已复制到剪贴板')
    }
  }
}
</script>

<style lang="scss" scoped>
.app-container {
  padding: 20px;
}
.kb-card {
  margin-bottom: 16px;
}
.hero-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.hero-title { display: flex; align-items: center; gap: 8px; font-weight: 600; }
.hero-title i { color: #409EFF; }
.hero-actions { display: flex; align-items: center; gap: 8px; }
.result-card {
  margin-top: 8px;
}
.result-header { display: flex; align-items: center; justify-content: space-between; }
.answer-block {
  margin-bottom: 16px;
}
.answer-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.answer-text {
  padding: 12px;
  background: #f8f8f8;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  white-space: pre-wrap;
}
.sources-title {
  font-weight: 600;
  margin-bottom: 8px;
}
.snippet {
  white-space: pre-wrap;
  margin: 0;
}
.task-status {
  color: #606266;
  margin-top: 8px;
}
.progress-steps { margin-top: 8px; margin-bottom: 8px; }
.topk-row { display: flex; align-items: center; gap: 12px; }
.topk-slider { width: 50%; }
.list-search { width: 260px; }
</style>
