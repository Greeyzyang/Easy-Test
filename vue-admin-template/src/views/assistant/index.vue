<template>
  <div class="app-container">
    <el-card class="box-card">
      <div slot="header" class="hero-header">
        <div class="hero-title">
          <i class="el-icon-magic-stick"></i>
          <span>AI 测试用例生成助手</span>
        </div>
        <div class="hero-actions">
          <el-tag type="success" size="small">智能生成</el-tag>
        </div>
      </div>
      
      <el-form ref="form" :model="form" label-width="140px" :rules="rules">
        <el-form-item label="核心需求 Jira Key" prop="jira_key" required>
          <el-input 
            v-model="form.jira_key" 
            placeholder="例如：PROJ-123" 
            clearable
            @keyup.enter.native="handleGenerate"
          >
            <template slot="prepend">
              <i class="el-icon-document"></i>
            </template>
          </el-input>
        </el-form-item>
        
        <el-form-item label="历史需求 Jira Keys">
          <el-input 
            v-model="form.history_keys_str" 
            placeholder="多个Key用英文逗号隔开, 例如: PROJ-100,PROJ-101" 
            clearable
            type="textarea"
            :rows="2"
          >
            <template slot="prepend">
              <i class="el-icon-files"></i>
            </template>
          </el-input>
          <div class="form-tip">
            <i class="el-icon-info"></i> 历史需求将提供额外上下文，帮助生成更全面的测试用例
          </div>
        </el-form-item>
        
        <el-form-item>
          <el-button 
            type="primary" 
            :loading="loading" 
            @click="handleGenerate"
            icon="el-icon-video-play"
            size="medium"
          >
            {{ loading ? '生成中...' : '开始生成测试用例' }}
          </el-button>
          <el-button 
            @click="resetForm" 
            icon="el-icon-refresh"
            size="medium"
          >
            重置
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 任务状态卡片 -->
    <el-card v-if="taskStatus || generatedTestcases.length > 0" class="box-card" style="margin-top: 20px;">
      <div slot="header" class="clearfix">
        <span><i class="el-icon-document-copy"></i> 生成结果</span>
        <div style="float: right;">
        <el-button
          v-if="generatedTestcases.length > 0"
          type="success"
          size="mini"
            icon="el-icon-download"
          @click="handleExport"
          >
            导出Excel
          </el-button>
          <el-button
            v-if="generatedTestcases.length > 0"
            type="info"
            size="mini"
            icon="el-icon-view"
            @click="showStatistics = !showStatistics"
          >
            {{ showStatistics ? '隐藏统计' : '显示统计' }}
          </el-button>
        </div>
      </div>
      
      <!-- 统计信息 -->
      <div v-if="showStatistics && generatedTestcases.length > 0" class="statistics-section">
        <el-row :gutter="20">
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-number">{{ generatedTestcases.length }}</div>
              <div class="stat-label">总测试用例</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-number">{{ priorityStats.P0 || 0 }}</div>
              <div class="stat-label">P0 优先级</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-number">{{ priorityStats.P1 || 0 }}</div>
              <div class="stat-label">P1 优先级</div>
            </el-card>
          </el-col>
          <el-col :span="6">
            <el-card shadow="hover" class="stat-card">
              <div class="stat-number">{{ priorityStats.P2 || 0 }}</div>
              <div class="stat-label">P2 优先级</div>
            </el-card>
          </el-col>
        </el-row>
        
        <el-row :gutter="20" style="margin-top: 20px;">
          <el-col :span="12">
            <el-card shadow="hover">
              <div slot="header">测试类型分布</div>
              <div class="type-distribution">
                <div v-for="(count, type) in typeStats" :key="type" class="type-item">
                  <el-tag :type="getTypeTagType(type)" size="small">{{ type }}</el-tag>
                  <span class="type-count">{{ count }}</span>
                </div>
              </div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="hover">
              <div slot="header">模块分布</div>
              <div class="module-distribution">
                <div v-for="(count, module) in moduleStats" :key="module" class="module-item">
                  <span class="module-name">{{ module || '未指定' }}</span>
                  <el-tag size="small" type="info">{{ count }}</el-tag>
                </div>
              </div>
            </el-card>
          </el-col>
        </el-row>
        
        <!-- 新增：质量问题提示与覆盖度建议 -->
        <el-row :gutter="20" style="margin-top: 20px;">
          <el-col :span="12">
            <el-card shadow="hover" class="quality-card">
              <div slot="header">质量问题提示</div>
              <div v-if="qualityIssues.length === 0" class="quality-empty">暂无明显质量问题</div>
              <div v-else class="quality-list">
                <el-alert
                  v-for="(issue, idx) in qualityIssues"
                  :key="idx"
                  type="warning"
                  :closable="false"
                  show-icon
                  class="quality-alert"
                  :title="issue"
                />
              </div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="hover" class="coverage-card">
              <div slot="header">覆盖度建议</div>
              <div v-if="coverageSuggestions.length === 0" class="coverage-empty">覆盖度良好</div>
              <ul v-else class="coverage-list">
                <li v-for="(tip, i) in coverageSuggestions" :key="i" class="coverage-item">
                  <i class="el-icon-guide"></i>
                  <span>{{ tip }}</span>
                </li>
              </ul>
            </el-card>
          </el-col>
        </el-row>
      </div>
      
      <!-- 加载状态 -->
      <div v-if="loading" class="loading-status">
        <el-steps :active="activeStep" align-center finish-status="success" class="progress-steps">
          <el-step title="获取Jira"/>
          <el-step title="分析历史"/>
          <el-step title="调用模型"/>
          <el-step title="生成用例"/>
          <el-step title="完成"/>
        </el-steps>
        <el-progress 
          :percentage="loadingProgress" 
          :stroke-width="8"
          :show-text="false"
          color="#409EFF"
        ></el-progress>
      <div class="loading-text">
        <i class="el-icon-loading"></i>
        <span>{{ taskStatus }}</span>
      </div>
      </div>
      
      <!-- 测试用例列表 -->
      <div v-if="!loading && generatedTestcases.length > 0" class="testcases-container">
        <div class="list-toolbar">
          <el-input v-model="filterText" clearable placeholder="搜索标题/模块/类型" size="small" class="list-search"/>
          <div class="list-actions">
            <el-button size="mini" @click="expandAll" icon="el-icon-caret-bottom">展开全部</el-button>
            <el-button size="mini" @click="collapseAll" icon="el-icon-caret-top">收起全部</el-button>
          </div>
        </div>
        <el-collapse v-model="activeNames" accordion>
          <el-collapse-item 
            v-for="(testcase, index) in filteredTestcases" 
            :key="index"
            :name="index"
            class="testcase-collapse-item"
          >
            <template slot="title">
              <div class="testcase-header">
                <span class="testcase-id">{{ testcase.id }}</span>
                <el-tag 
                  :type="getPriorityTagType(testcase.priority)" 
                  size="mini"
                  class="priority-tag"
                >
                  {{ testcase.priority }}
                </el-tag>
                <el-tag 
                  :type="getTypeTagType(testcase.type)" 
                  size="mini"
                  class="type-tag"
                >
                  {{ testcase.type }}
                </el-tag>
                <span class="testcase-title">{{ testcase.title }}</span>
                <el-button type="text" icon="el-icon-document-copy" @click.stop="copyTestcase(testcase)"></el-button>
              </div>
            </template>
            
            <div class="testcase-content">
              <el-row :gutter="20">
                <el-col :span="8">
                  <div class="info-section">
                    <h4><i class="el-icon-folder"></i> 模块</h4>
                    <p>{{ testcase.module || '未指定' }}</p>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="info-section">
                    <h4><i class="el-icon-warning"></i> 优先级</h4>
                    <p>{{ testcase.priority }}</p>
                  </div>
                </el-col>
                <el-col :span="8">
                  <div class="info-section">
                    <h4><i class="el-icon-collection-tag"></i> 类型</h4>
                    <p>{{ testcase.type }}</p>
                  </div>
                </el-col>
              </el-row>
              
              <div v-if="testcase.precondition" class="precondition-section">
                <h4><i class="el-icon-setting"></i> 前置条件</h4>
                <div class="precondition-content">{{ testcase.precondition }}</div>
              </div>
              
              <div class="steps-section">
                <h4><i class="el-icon-guide"></i> 测试步骤</h4>
                <div class="steps-list">
                  <div 
                    v-for="(step, stepIndex) in testcase.steps" 
                    :key="stepIndex" 
                    class="step-item"
                  >
                    <div class="step-number">{{ stepIndex + 1 }}</div>
                    <div class="step-content">{{ step }}</div>
                  </div>
                </div>
              </div>
              
              <div class="expected-section">
                <h4><i class="el-icon-check"></i> 预期结果</h4>
                <div class="expected-content">{{ testcase.expected_result }}</div>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>
      
      <!-- 错误信息 -->
      <div v-if="error" class="error-message">
        <el-alert
          :title="error"
          type="error"
          :closable="false"
          show-icon
        >
          <template slot="title">
            <i class="el-icon-error"></i>
            生成失败: {{ error }}
          </template>
        </el-alert>
      </div>
    </el-card>
  </div>
</template>

<script>
import { startGenerationTask, getTaskStatus, downloadTestcasesXlsx } from '@/api/assistant'

export default {
  name: 'AIAssistant',
  data() {
    return {
      loading: false,
      loadingProgress: 0,
      form: {
        jira_key: '',
        history_keys_str: ''
      },
      rules: {
        jira_key: [
          { required: true, message: '请输入核心需求 Jira Key', trigger: 'blur' }
        ]
      },
      taskId: null,
      taskStatus: '',
      pollInterval: null, // 轮询定时器
      ws: null, // WebSocket 连接实例
      generatedTestcases: [],
      error: '',
      showStatistics: false,
      activeNames: [0], // 默认展开第一个测试用例
      // 新增：用于覆盖度计算的目标类型集合（与后端约定的10大维度一致）
      targetTypes: ['functional','boundary','negative','security','integration','performance','concurrency','data-validation','network','compatibility'],
      // 新增：并行早期轮询的控制
      wsFirstMsgReceived: false,
      earlyPollInterval: null,
      filterText: ''
    }
  },
  computed: {
    priorityStats() {
      const stats = {}
      this.generatedTestcases.forEach(testcase => {
        const priority = testcase.priority || 'P2'
        stats[priority] = (stats[priority] || 0) + 1
      })
      return stats
    },
    typeStats() {
      const stats = {}
      this.generatedTestcases.forEach(testcase => {
        const type = testcase.type || 'other'
        stats[type] = (stats[type] || 0) + 1
      })
      return stats
    },
    moduleStats() {
      const stats = {}
      this.generatedTestcases.forEach(testcase => {
        const module = testcase.module || '未指定'
        stats[module] = (stats[module] || 0) + 1
      })
      return stats
    },
    // 新增：质量问题提示
    qualityIssues() {
      const issues = []
      if (!this.generatedTestcases || this.generatedTestcases.length === 0) return issues
      const priorityAllowed = ['P0','P1','P2']
      const idPrefix = this.form.jira_key ? new RegExp(`^${this.form.jira_key}-\\d{3}$`) : /^[A-Z]+-\d+-\d{3}$/

      let missingExpected = 0
      let shortSteps = 0
      let invalidPriority = 0
      let invalidType = 0
      let invalidId = 0
      let missingModule = 0

      this.generatedTestcases.forEach(tc => {
        // 预期结果
        if (!tc.expected_result || String(tc.expected_result).trim().length < 5) missingExpected++
        // 步骤数量
        if (!Array.isArray(tc.steps) || tc.steps.length < 3) shortSteps++
        // 优先级合法性
        if (!priorityAllowed.includes(tc.priority)) invalidPriority++
        // 类型合法性（仅用于质量提示，不强制全部在目标集合内）
        if (!tc.type || (this.targetTypes.includes(tc.type) === false && tc.type !== 'other')) invalidType++
        // ID格式
        if (!tc.id || !idPrefix.test(tc.id)) invalidId++
        // 模块缺失
        if (!tc.module || String(tc.module).trim().length === 0) missingModule++
      })

      if (missingExpected > 0) issues.push(`${missingExpected} 个用例缺少或过短的整体预期结果`)
      if (shortSteps > 0) issues.push(`${shortSteps} 个用例步骤不足（建议每个用例 3-6 步）`)
      if (invalidPriority > 0) issues.push(`${invalidPriority} 个用例优先级不在 P0/P1/P2 范围内`)
      if (invalidType > 0) issues.push(`${invalidType} 个用例测试类型未对齐目标维度或缺失`)
      if (invalidId > 0) issues.push(`${invalidId} 个用例编号不符合约定格式（如 ${this.form.jira_key}-001）`)
      if (missingModule > 0) issues.push(`${missingModule} 个用例缺少模块信息`)

      // 分布过于集中提示（单一模块或单一种类占比过高）
      const typeTotal = Object.values(this.typeStats).reduce((a,b)=>a+b,0)
      const moduleTotal = Object.values(this.moduleStats).reduce((a,b)=>a+b,0)
      const maxType = Math.max(...Object.values(this.typeStats)) || 0
      const maxModule = Math.max(...Object.values(this.moduleStats)) || 0
      if (typeTotal > 0 && maxType / typeTotal > 0.7) issues.push('测试类型分布过于集中，建议增加多维度场景（负面、安全、性能、边界等）')
      if (moduleTotal > 0 && maxModule / moduleTotal > 0.7) issues.push('用例过于集中在单一模块，建议覆盖跨模块/集成场景')

      return issues
    },
    // 新增：覆盖度建议
    coverageSuggestions() {
      const tips = []
      const currentTypes = this.typeStats
      // 缺失的目标类型建议补充
      this.targetTypes.forEach(t => {
        if (!currentTypes[t]) tips.push(`缺少 ${t} 场景，建议补充 1-2 条用例以覆盖该维度`)
      })
      // 高优先级覆盖建议
      const total = this.generatedTestcases.length
      const p0Count = this.priorityStats.P0 || 0
      if (total > 0 && p0Count / total < 0.1) tips.push('高优先级（P0）场景覆盖偏低，建议提升关键路径用例优先级')
      // 步骤平均长度建议
      const avgSteps = (() => {
        const counts = this.generatedTestcases.map(tc => Array.isArray(tc.steps) ? tc.steps.length : 0)
        const sum = counts.reduce((a,b)=>a+b,0)
        return counts.length ? (sum / counts.length) : 0
      })()
      if (avgSteps > 0 && avgSteps < 3) tips.push('用例步骤平均不足 3 步，建议细化操作与验证点')

      return tips
    },
    filteredTestcases() {
      const q = (this.filterText || '').toLowerCase()
      if (!q) return this.generatedTestcases
      return this.generatedTestcases.filter(tc => {
        const title = String(tc.title || '').toLowerCase()
        const module = String(tc.module || '').toLowerCase()
        const type = String(tc.type || '').toLowerCase()
        return title.includes(q) || module.includes(q) || type.includes(q)
      })
    },
    activeStep() {
      const p = Number(this.loadingProgress || 0)
      if (p >= 100) return 4
      if (p >= 75) return 3
      if (p >= 50) return 2
      if (p >= 25) return 1
      return 0
    }
  },
  beforeDestroy() {
    // 组件销毁前清除轮询定时器
    this.clearPolling()
    // 关闭 WebSocket 连接
    if (this.ws) {
      try { this.ws.close() } catch (e) {}
      this.ws = null
    }
  },
  methods: {
    async handleGenerate() {
      try {
        await this.$refs.form.validate()
      } catch (error) {
        return
      }
      
      this.loading = true
      this.loadingProgress = 0
      this.taskStatus = '正在启动任务...'
      this.generatedTestcases = []
      this.error = ''
      this.taskId = null
      this.showStatistics = false

      try {
        // 解析历史需求Keys
        const history_keys = this.form.history_keys_str.split(',').map(key => key.trim()).filter(key => key)
        
        // 先启动任务
        const response = await startGenerationTask({
          jira_key: this.form.jira_key,
          history_keys: history_keys
        })
        
        if (response && response.code === '0') {
          this.taskId = response.data.task_id
          this.taskStatus = response.data.message || '任务已启动'
          
          // 启动轮询获取任务状态
          this.setupWebSocket()
        } else {
          throw new Error(response.message || '启动任务失败')
        }
      } catch (err) {
        this.loading = false
        this.error = err.message || '启动任务失败，请检查网络或联系管理员'
        this.$message.error(this.error)
      }
    },
    
    resetForm() {
      this.$refs.form.resetFields()
      this.generatedTestcases = []
      this.error = ''
      this.taskStatus = ''
      this.showStatistics = false
      this.activeNames = [0]
      // 清除轮询
      this.clearPolling()
      // 清空进度详情
      // 结束早期轮询
      if (this.earlyPollInterval) {
        clearInterval(this.earlyPollInterval)
        this.earlyPollInterval = null
      }
      this.wsFirstMsgReceived = false
    },
    
    async handleExport() {
      if (!this.taskId) {
        this.$message.error('请先生成测试用例');
        return;
      }
      try {
        this.$message.info('正在生成Excel文件...')
        const res = await downloadTestcasesXlsx(this.taskId)
        const blob = new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' })
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = `testcases_${this.taskId}.xlsx`
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
        this.$message.success('Excel文件下载成功！')
      } catch (err) {
        this.$message.error('下载失败，请稍后重试');
      }
    },
    
    // 启动轮询获取任务状态
    startPolling() {
      // 清除之前的轮询
      this.clearPolling()
      
      // 启动新的轮询
      this.pollInterval = setInterval(async () => {
        try {
          const res = await getTaskStatus(this.taskId)
          const task = res.data
          
          // 根据任务状态更新UI
          if (task.status === 'SUCCESS') {
            this.handleTaskSuccess(task)
          } else if (task.status === 'FAILURE') {
            this.handleTaskFailure(task)
          } else {
            this.handleTaskProgress(task)
          }
        } catch (err) {
          console.error('轮询任务状态失败:', err)
          this.error = '获取任务状态失败'
          this.clearPolling()
          this.loading = false
        }
      }, 2000) // 每2秒轮询一次
    },
    
    // 清除轮询
    clearPolling() {
      if (this.pollInterval) {
        clearInterval(this.pollInterval)
        this.pollInterval = null
      }
    },
    
    // 处理任务成功
    handleTaskSuccess(task) {
      this.clearPolling()
      this.loading = false
      this.loadingProgress = 100
      this.taskStatus = '任务执行完成'
      
      if (task.result && task.result.result && task.result.result.testcases) {
        this.generatedTestcases = task.result.result.testcases
        this.showStatistics = true
        this.$message.success(`成功生成 ${this.generatedTestcases.length} 个测试用例！`)
      } else {
        this.error = '任务执行完成，但未返回有效的测试用例数据'
        this.$message.error(this.error)
      }
    },
    
    // 处理任务失败
    handleTaskFailure(task) {
      this.clearPolling()
      this.loading = false
      this.error = task.result.message || task.result.error || '任务执行失败'
      this.$message.error(this.error)
    },
    
    // 处理任务进度
    handleTaskProgress(task) {
      // 更新进度
      if (task.result && task.result.status === 'PROGRESS') {
        this.taskStatus = task.result.message || '处理中...'
        this.loadingProgress = task.result.progress || this.loadingProgress
        
        // 根据消息内容更新进度条
        if (this.taskStatus.includes('获取Jira信息')) {
          this.loadingProgress = Math.max(this.loadingProgress, 20)
        } else if (this.taskStatus.includes('生成测试用例')) {
          this.loadingProgress = Math.max(this.loadingProgress, 60)
        } else if (this.taskStatus.includes('调用大模型')) {
          this.loadingProgress = Math.max(this.loadingProgress, 70)
        } else {
          this.loadingProgress = Math.min(this.loadingProgress + 5, 90)
        }
      }
    },
    // 还原：标签类型映射（用于优先级与类型Tag渲染）
    getPriorityTagType(priority) {
      const types = {
        'P0': 'danger',
        'P1': 'warning',
        'P2': 'info'
      }
      return types[priority] || 'info'
    },
    getTypeTagType(type) {
      const types = {
        'functional': 'primary',
        'boundary': 'success',
        'negative': 'warning',
        'security': 'danger',
        'performance': 'info',
        'compatibility': 'success',
        'usability': 'primary',
        'i18n': 'warning',
        'integration': 'success',
        'regression': 'info',
        'data-validation': 'warning',
        'workflow': 'primary'
      }
      return types[type] || 'info'
    },
    // 使用 WebSocket 获取任务进度（优先）
    setupWebSocket() {
      // 若已有连接，先关闭
      if (this.ws) {
        try { this.ws.close() } catch (e) {}
        this.ws = null
      }
      if (!this.taskId) {
        // 无 taskId 时退回轮询
        this.startPolling()
        return
      }
      // 根据环境变量构建 WebSocket URL
      const baseApi = process.env.VUE_APP_BASE_API || ''
      const wsHost = baseApi.startsWith('https') ? baseApi.replace('https', 'wss') : baseApi.replace('http', 'ws')
      const wsUrl = `${wsHost}/rest/v1/ai/ws/progress/${this.taskId}`
      try {
        this.ws = new WebSocket(wsUrl)
      } catch (e) {
        console.error('创建 WebSocket 失败，回退轮询:', e)
        this.startPolling()
        return
      }
      this.taskStatus = '已连接进度通道，等待任务事件...'
      // 标记：尚未接收WS首条消息
      this.wsFirstMsgReceived = false
      // 监听消息
      this.ws.onmessage = (evt) => {
        try {
          const msg = JSON.parse(evt.data || '{}')
          const status = msg.status || 'PROGRESS'
          // 标记已收到WS消息，停止早期轮询
          if (!this.wsFirstMsgReceived) {
            this.wsFirstMsgReceived = true
            if (this.earlyPollInterval) {
              clearInterval(this.earlyPollInterval)
              this.earlyPollInterval = null
            }
          }
        if (status === 'PROGRESS') {
          this.loadingProgress = Number(msg.progress || 0)
          this.taskStatus = msg.text || '处理中...'
        } else if (status === 'SUCCESS') {
          this.loadingProgress = Number(msg.progress || 100)
          this.taskStatus = msg.text || '任务完成'
          if (msg.result && Array.isArray(msg.result.testcases)) {
            this.generatedTestcases = msg.result.testcases
            this.showStatistics = true
          }
          this.loading = false
            // 关闭 WS
            try { this.ws && this.ws.close() } catch (e) {}
            this.ws = null
        } else if (status === 'FAILURE') {
          this.loadingProgress = Number(msg.progress || 100)
          this.taskStatus = '任务失败'
          this.error = msg.text || '生成失败'
          this.loading = false
          try { this.ws && this.ws.close() } catch (e) {}
          this.ws = null
        }
        } catch (parseErr) {
          console.error('解析 WS 消息失败:', parseErr)
        }
      }
      // 连接建立与错误处理
      this.ws.onopen = () => {
        // 已建立连接
      }
      this.ws.onerror = (e) => {
        console.error('WebSocket 连接错误，回退到轮询:', e)
        // 关闭并回退轮询
        try { this.ws && this.ws.close() } catch (err) {}
        this.ws = null
        this.startPolling()
      }
      this.ws.onclose = () => {
        this.ws = null
      }
    }
    ,
    expandAll() {
      const n = this.filteredTestcases.length
      this.activeNames = Array.from({ length: n }, (_, i) => i)
    },
    collapseAll() {
      this.activeNames = []
    },
    copyTestcase(testcase) {
      const content = `ID: ${testcase.id}\nTitle: ${testcase.title}\nModule: ${testcase.module}\nPriority: ${testcase.priority}\nType: ${testcase.type}\nPrecondition: ${testcase.precondition || ''}\nSteps:\n${Array.isArray(testcase.steps) ? testcase.steps.map((s, i) => `${i+1}. ${s}`).join('\n') : ''}\nExpected: ${testcase.expected_result}`
      try {
        const ta = document.createElement('textarea')
        ta.value = content
        document.body.appendChild(ta)
        ta.select()
        document.execCommand('copy')
        document.body.removeChild(ta)
        this.$message.success('用例已复制到剪贴板')
      } catch (e) {
        this.$message.error('复制失败')
      }
    }
  }
}
</script>

<style scoped>
.box-card {
  margin-bottom: 20px;
}

.hero-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 0;
}
.hero-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: 600;
}
.hero-title i { color: #409EFF; }
.hero-actions { display: flex; align-items: center; gap: 8px; }

.progress-steps { margin-bottom: 10px; }

.list-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}
.list-search { width: 260px; }
.list-actions { display: flex; gap: 6px; }

.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 5px;
}

.loading-status {
  text-align: center;
  padding: 20px;
}

.loading-text {
  margin-top: 10px;
  font-size: 14px;
  color: #606266;
}

.loading-text .el-icon-loading {
  margin-right: 8px;
}

.statistics-section {
  margin-bottom: 20px;
}

.stat-card {
  text-align: center;
  padding: 20px;
}

.stat-number {
  font-size: 24px;
  font-weight: bold;
  color: #409EFF;
  margin-bottom: 5px;
}

.stat-label {
  font-size: 12px;
  color: #909399;
}

.type-distribution, .module-distribution {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.type-item, .module-item {
  display: flex;
  align-items: center;
  gap: 5px;
}

.type-count {
  font-size: 12px;
  color: #606266;
}

.module-name {
  font-size: 12px;
  color: #606266;
}

.testcases-container {
  margin-top: 20px;
}

.testcase-collapse-item {
  margin-bottom: 10px;
}

.testcase-header {
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}

.testcase-id {
  font-weight: bold;
  color: #409EFF;
  min-width: 80px;
}

.priority-tag, .type-tag {
  min-width: 40px;
  text-align: center;
}

.testcase-title {
  flex: 1;
  font-weight: 500;
}

.testcase-content {
  padding: 20px;
  background-color: #fafafa;
  border-radius: 4px;
}

.info-section {
  margin-bottom: 15px;
}

.info-section h4 {
  font-size: 14px;
  color: #606266;
  margin-bottom: 5px;
}

.info-section p {
  font-size: 13px;
  color: #303133;
  margin: 0;
}

.precondition-section, .steps-section, .expected-section {
  margin-top: 20px;
}

.precondition-section h4, .steps-section h4, .expected-section h4 {
  font-size: 14px;
  color: #606266;
  margin-bottom: 10px;
}

.precondition-content, .expected-content {
  background-color: white;
  padding: 10px;
  border-radius: 4px;
  border-left: 3px solid #409EFF;
  font-size: 13px;
  line-height: 1.5;
}

.steps-list {
  background-color: white;
  border-radius: 4px;
  overflow: hidden;
}

.step-item {
  display: flex;
  padding: 10px;
  border-bottom: 1px solid #ebeef5;
}

.step-item:last-child {
  border-bottom: none;
}

.step-number {
  background-color: #409EFF;
  color: white;
  width: 24px;
  height: 24px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: bold;
  margin-right: 10px;
  flex-shrink: 0;
}

.step-content {
  flex: 1;
  font-size: 13px;
  line-height: 1.5;
  color: #303133;
}

.error-message {
  margin-top: 20px;
}
.quality-card, .coverage-card { min-height: 160px; }
.quality-alert { margin-bottom: 8px; }
.quality-empty, .coverage-empty { color: #909399; padding: 8px 0; }
.coverage-list { list-style: none; padding: 0; margin: 0; }
.coverage-item { display: flex; align-items: center; margin: 6px 0; }
 .coverage-item i { margin-right: 6px; color: #409EFF; }
</style>
