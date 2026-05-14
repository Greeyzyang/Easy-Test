<template>
  <div class="app-container" @click="handleCardClick">
    <el-card class="query-card">
      <div slot="header">
        <span>测试用例转换</span>
      </div>
      <el-form ref="queryForm" :model="queryForm" :rules="rules" label-width="120px" inline>
        <el-form-item label="文档 URL" prop="docUrl">
          <el-input
            v-model="queryForm.docUrl"
            placeholder="https://docs.qq.com/sheet/DSVNDeERaUnpSc1VF?u=xxx&tab=f6ilfw"
            style="width: 500px"
            clearable
          />
        </el-form-item>
        <el-form-item label="Jira 单号">
          <el-input
            v-model="queryForm.jiraId"
            placeholder="如 DM-19290（可选）"
            style="width: 200px"
            clearable
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="success"
            :loading="loadingConvert"
            :disabled="!queryForm.docUrl"
            @click="handleConvert"
          >
            转换测试用例
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- 转换结果 -->
    <el-card v-if="resultData" class="result-card">
      <div slot="header">
        <span>转换结果</span>
        <div style="float: right; display: flex; gap: 8px; align-items: center;">
          <el-button
            type="primary"
            size="small"
            icon="el-icon-document-copy"
            :disabled="!resultData.records || !resultData.records.length"
            @click="handleCopyAll"
          >
            复制全部
          </el-button>
          <el-button
            type="text"
            icon="el-icon-download"
            @click="handleExport"
          >
            导出 HTML
          </el-button>
        </div>
      </div>

      <!-- 统计信息 -->
      <el-row :gutter="20" class="stats-row">
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">TASK</div>
            <div class="stat-value">{{ resultData.jira_id }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">MODULE</div>
            <div class="stat-value">{{ resultData.module_name }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">TOTAL</div>
            <div class="stat-value">{{ resultData.total_count }}</div>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <div class="stat-label">PASS RATE</div>
            <div class="stat-value">
              <el-tag :type="passRateType" size="small">{{ passRateDisplay }}</el-tag>
            </div>
          </div>
        </el-col>
      </el-row>

      <!-- 卡片样式 HTML -->
      <div
        v-if="resultData.card_html"
        class="card-container"
        v-html="resultData.card_html"
      />

      <!-- 原始记录表格（可折叠） -->
      <el-collapse v-if="resultData.records && resultData.records.length" style="margin-top: 20px">
        <el-collapse-item title="原始数据表格" name="raw">
          <el-table
            :data="resultData.records"
            border
            stripe
            max-height="500"
            size="small"
          >
            <el-table-column label="#" prop="case_id" width="60" align="center" />
            <el-table-column label="TASK" prop="task" width="100" align="center" />
            <el-table-column label="MODULE" prop="module" width="90" align="center" />
            <el-table-column label="PRIORITY" prop="test_priority" width="90" align="center">
              <template slot-scope="scope">
                <el-tag :type="getPriorityType(scope.row.test_priority)" size="small">
                  {{ scope.row.test_priority }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column label="TITLE" prop="case_title" min-width="180" show-overflow-tooltip />
            <el-table-column label="STEPS" prop="case_steps" min-width="200" show-overflow-tooltip />
            <el-table-column label="EXPECTED" prop="expected_result" min-width="160" show-overflow-tooltip />
            <el-table-column label="ACTUAL" prop="actual_results" width="90" align="center" />
            <el-table-column label="TESTER" prop="tester" width="90" align="center" />
            <el-table-column label="NOTE" prop="note" min-width="120" show-overflow-tooltip />
          </el-table>
        </el-collapse-item>
      </el-collapse>
    </el-card>

    <!-- 提示信息 -->
    <el-alert
      v-if="errorMsg"
      :title="errorMsg"
      type="error"
      show-icon
      style="margin-top: 16px"
      :closable="false"
    />
  </div>
</template>

<script>
import { convertTestcases } from '@/api/tencent-docs'

export default {
  name: 'TencentDocsConvert',
  data() {
    return {
      queryForm: {
        docUrl: '',
        jiraId: ''
      },
      rules: {
        docUrl: [
          { required: true, message: '请输入腾讯文档 URL', trigger: 'blur' }
        ]
      },
      loadingConvert: false,
      resultData: null,
      errorMsg: ''
    }
  },
  computed: {
    passRate() {
      if (!this.resultData || !this.resultData.records.length) return 0
      const passCount = this.resultData.records.filter(r => r.actual_results === 'PASS').length
      return Math.round((passCount / this.resultData.total_count) * 100)
    },
    passRateDisplay() {
      return `${this.passRate}%`
    },
    passRateType() {
      if (this.passRate >= 80) return 'success'
      if (this.passRate >= 50) return 'warning'
      return 'danger'
    }
  },
  methods: {
    async handleConvert() {
      this.$refs.queryForm.validate(async valid => {
        if (!valid) return

        this.loadingConvert = true
        this.errorMsg = ''
        this.resultData = null

        try {
          const response = await convertTestcases({
            doc_url: this.queryForm.docUrl,
            jira_id: this.queryForm.jiraId || null
          })

          if (response.code === '0' && response.data) {
            this.resultData = response.data
            this.$message.success(`转换成功，共 ${response.data.total_count} 条测试用例`)
          } else {
            this.$message.error(response.msg || '转换失败')
          }
        } catch (error) {
          console.error('转换失败:', error)
          this.errorMsg = error.response?.data?.detail || error.message || '转换失败'
        } finally {
          this.loadingConvert = false
        }
      })
    },

    async handleCopyAll() {
      if (!this.resultData || !this.resultData.records || !this.resultData.records.length) return
      try {
        const allText = this.resultData.records
          .map(r => r.copy_text)
          .filter(Boolean)
          .join('\n\n')
        await navigator.clipboard.writeText(allText)
        this.$message.success(`已复制全部 ${this.resultData.records.length} 条到剪贴板`)
      } catch (e) {
        console.error('复制失败:', e)
        this.$message.error('复制失败，请手动复制')
      }
    },

    async handleCardClick(e) {
      const btn = e.target.closest('.card-copy-btn')
      if (!btn) return
      const text = btn.getAttribute('data-copy-text')
      if (!text) return
      // 将 \\n 转为真实换行（后端已将 \n 存储为字面 \\n）
      const textWithNewlines = text.replace(/\\n/g, '\n')
      try {
        await navigator.clipboard.writeText(textWithNewlines)
        this.$message.success('已复制到剪贴板')
      } catch (err) {
        console.error('复制失败:', err)
        this.$message.error('复制失败，请手动复制')
      }
    },

    handleExport() {
      if (!this.resultData || !this.resultData.card_html) return
      const blob = new Blob([this.resultData.card_html], { type: 'text/html;charset=utf-8' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `testcases_${this.resultData.jira_id || 'output'}.html`
      a.click()
      URL.revokeObjectURL(url)
    },

    getPriorityType(priority) {
      const p = (priority || '').toLowerCase()
      if (p === 'important' || p === 'p0' || p === 'p1') return 'danger'
      if (p === 'medium' || p === 'p2') return 'warning'
      return 'info'
    }
  }
}
</script>

<style scoped>
.app-container {
  padding: 20px;
}

.query-card {
  margin-bottom: 20px;
}

.result-card {
  margin-bottom: 20px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-item {
  text-align: center;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 4px;
}

.stat-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.stat-value {
  font-size: 16px;
  font-weight: bold;
  color: #303133;
}

.card-container {
  margin-top: 16px;
}
</style>
