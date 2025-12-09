<template>
  <div class="app-container" v-loading="loading">
    <el-card class="box-card stats-card" shadow="hover">
      <div slot="header" class="card-header">
        <span class="header-title">测试结果统计</span>
      </div>
      <el-row :gutter="20" v-if="report">
        <el-col :span="16">
          <div class="chart-container">
            <pie-chart :chart-data="chartData" />
          </div>
        </el-col>
        <el-col :span="8">
          <div class="stat-cards">
            <div class="stat-card total">
              <i class="el-icon-data-analysis stat-icon"></i>
              <div class="stat-content">
                <div class="stat-title">总用例数</div>
                <div class="stat-value">{{ report.total_cases }}</div>
              </div>
            </div>
            <div class="stat-card success">
              <i class="el-icon-circle-check stat-icon"></i>
              <div class="stat-content">
                <div class="stat-title">成功</div>
                <div class="stat-value">{{ report.passed_cases }}</div>
              </div>
            </div>
            <div class="stat-card failed">
              <i class="el-icon-circle-close stat-icon"></i>
              <div class="stat-content">
                <div class="stat-title">失败</div>
                <div class="stat-value">{{ report.failed_cases }}</div>
              </div>
            </div>
            <div class="stat-card skipped">
              <i class="el-icon-warning-outline stat-icon"></i>
              <div class="stat-content">
                <div class="stat-title">跳过</div>
                <div class="stat-value">{{ report.skipped_cases }}</div>
              </div>
            </div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <el-card class="box-card cases-card" shadow="hover">
      <div slot="header" class="card-header">
        <span class="header-title">测试用例详情</span>
        <el-input
          v-model="searchQuery"
          placeholder="搜索用例"
          prefix-icon="el-icon-search"
          clearable
          @clear="handleSearch"
          @input="handleSearch"
          class="search-input"
        ></el-input>
      </div>
      <el-table
        v-if="report && report.case_results"
        :data="filteredCaseResults"
        border
        stripe
        highlight-current-row
        style="width: 100%">
        <el-table-column
          prop="name"
          label="用例名称"
          min-width="200">
        </el-table-column>
        <el-table-column
          prop="status"
          label="状态"
          width="100"
          align="center">
          <template slot-scope="scope">
            <el-tag :type="statusTagType(scope.row.status)" effect="dark">{{ scope.row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="duration"
          label="耗时(秒)"
          width="100"
          align="center">
        </el-table-column>
        <el-table-column
          label="详情"
          width="80"
          align="center">
          <template slot-scope="scope">
            <el-button type="primary" size="mini" icon="el-icon-view" circle @click="showCaseDetail(scope.row)"></el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog 
      title="测试用例执行详情" 
      :visible.sync="dialogVisible" 
      width="70%"
      custom-class="case-detail-dialog">
      <div v-if="currentCase" class="case-detail-content">
        <div class="detail-item">
          <div class="detail-label">用例名称:</div>
          <div class="detail-value">{{ currentCase.name }}</div>
        </div>
        <div class="detail-item">
          <div class="detail-label">状态:</div>
          <div class="detail-value">
            <el-tag :type="statusTagType(currentCase.status)" effect="dark">{{ currentCase.status }}</el-tag>
          </div>
        </div>
        <div class="detail-item">
          <div class="detail-label">耗时:</div>
          <div class="detail-value">{{ currentCase.duration }}秒</div>
        </div>
        <div class="detail-item">
          <div class="detail-label">步骤详情:</div>
          <div class="detail-value" style="width:100%">
            <el-table
              v-if="currentCase.steps && currentCase.steps.length"
              :data="currentCase.steps"
              border
              size="mini"
              style="width: 100%">
              <el-table-column prop="step_name" label="步骤名称" min-width="120"/>
              <el-table-column prop="status" label="状态" width="100" align="center">
                <template slot-scope="scope">
                  <el-tag :type="statusTagType(scope.row.status)" effect="dark">{{ scope.row.status }}</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="duration" label="耗时(秒)" width="100" align="center"/>
              <el-table-column prop="error_message" label="错误信息" min-width="150">
                <template slot-scope="scope">
                  <span v-if="scope.row.status && String(scope.row.status).toLowerCase() !== 'passed' && scope.row.error_message">
                    {{ scope.row.error_message }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
            <div v-else>无步骤信息</div>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getTestReportDetail, exportTestReport } from '@/api/testreport'
import PieChart from '@/components/Charts/PieChart'

export default {
  name: 'TestReportDetail',
  components: {
    PieChart
  },
  data() {
    return {
      loading: false,
      dialogVisible: false,
      currentCase: null,
      report: null,
      chartData: {
        labels: ['成功', '失败', '跳过'],
        datasets: [{
          data: [0, 0, 0],
          backgroundColor: ['#67C23A', '#F56C6C', '#909399']
        }]
      },
      searchQuery: ''
    }
  },
  computed: {
    filteredCaseResults() {
      if (!this.report || !this.report.case_results) return []
      if (!this.searchQuery) return this.report.case_results
      
      const query = this.searchQuery.toLowerCase()
      return this.report.case_results.filter(case_result => 
        case_result.name.toLowerCase().includes(query)
      )
    }
  },
  created() {
    this.getReportDetail()
  },
  methods: {
    statusTagType(status) {
      const statusMap = {
        passed: 'success',
        failed: 'danger',
        skipped: 'info',
        running: 'warning'
      }
      return statusMap[String(status).toLowerCase()] || 'info'
    },
    async getReportDetail() {
      try {
        this.loading = true
        const { data } = await getTestReportDetail(this.$route.params.id)
        this.report = data
        console.log('接口返回：', this.report)
        this.updateChartData()
      } catch (error) {
        this.$message.error('获取测试报告详情失败：' + error.message)
      } finally {
        this.loading = false
      }
    },
    updateChartData() {
      if (this.report) {
        this.chartData.datasets[0].data = [
          this.report.passed_cases,
          this.report.failed_cases,
          this.report.skipped_cases
        ]
      }
    },
    async handleExport() {
      try {
        const response = await exportTestReport(this.$route.params.id, {
          responseType: 'blob'  // 明确指定响应类型为blob
        })

        // 兼容 headers 结构和大小写
        const headers = response.headers || {}
        const contentDisposition = headers['content-disposition'] || headers['Content-Disposition']
        let filename = `${this.report.name}.pdf`
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
          if (filenameMatch && filenameMatch[1]) {
            filename = decodeURIComponent(filenameMatch[1].replace(/['"]/g, ''))
          }
        }

        // 创建blob对象
        const blob = new Blob([response.data], { 
          type: headers['content-type'] || headers['Content-Type'] || 'application/pdf'
        })

        // 使用URL.createObjectURL创建下载链接
        const url = window.URL.createObjectURL(blob)
        const link = document.createElement('a')
        link.href = url
        link.download = filename
        document.body.appendChild(link)
        link.click()
        
        // 清理
        document.body.removeChild(link)
        window.URL.revokeObjectURL(url)
        
        this.$message.success('报告导出成功')
      } catch (error) {
        console.error('导出失败:', error)
        this.$message.error('导出报告失败：' + (error.message || '未知错误'))
      }
    },
    showCaseDetail(row) {
      this.currentCase = row
      this.dialogVisible = true
    },
    formatJson(json) {
      if (!json) return ''
      return JSON.stringify(json, null, 2)
    },
    handleSearch() {
      // 搜索功能已通过计算属性实现
    }
  }
}
</script>

<style scoped>
.app-container {
  padding: 20px;
  background-color: #f0f2f5;
  min-height: calc(100vh - 84px);
}

.main-card,
.stats-card,
.cases-card {
  margin-bottom: 20px;
  border-radius: 8px;
  transition: all 0.3s ease;
}

.main-card:hover,
.stats-card:hover,
.cases-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 15px 20px;
  border-bottom: 1px solid #ebeef5;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}

.report-info {
  padding: 20px;
}

.detail-item {
  margin-bottom: 20px;
  display: flex;
  align-items: flex-start;
  padding: 10px;
  border-radius: 4px;
  background-color: #fafafa;
  transition: all 0.3s ease;
}

.detail-item:hover {
  background-color: #f5f7fa;
}

.detail-label {
  width: 120px;
  font-weight: 600;
  color: #606266;
}

.detail-value {
  flex: 1;
  color: #303133;
}

.stat-cards {
  display: flex;
  flex-direction: column;
  gap: 15px;
  padding: 10px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 20px;
  border-radius: 8px;
  background-color: #fff;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
  transition: all 0.3s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.stat-icon {
  font-size: 24px;
  margin-right: 15px;
}

.stat-content {
  flex: 1;
}

.stat-card.total {
  background: linear-gradient(135deg, #409EFF 0%, #36D1DC 100%);
  color: white;
}

.stat-card.success {
  background: linear-gradient(135deg, #67C23A 0%, #95D475 100%);
  color: white;
}

.stat-card.failed {
  background: linear-gradient(135deg, #F56C6C 0%, #F78989 100%);
  color: white;
}

.stat-card.skipped {
  background: linear-gradient(135deg, #909399 0%, #C0C4CC 100%);
  color: white;
}

.stat-title {
  font-size: 14px;
  margin-bottom: 8px;
  opacity: 0.9;
}

.stat-value {
  font-size: 24px;
  font-weight: bold;
}

.chart-container {
  height: 300px;
  position: relative;
  padding: 20px;
  background-color: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px 0 rgba(0, 0, 0, 0.05);
}

.search-input {
  width: 250px;
}

.code-block {
  background-color: #f8f9fa;
  padding: 15px;
  border-radius: 6px;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', 'Consolas', 'source-code-pro', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #333;
  border: 1px solid #e8e8e8;
}

.error-message {
  color: #f56c6c;
  background-color: #fef0f0;
  padding: 10px;
  border-radius: 4px;
  border: 1px solid #fde2e2;
}

.case-detail-dialog {
  border-radius: 8px;
}

.case-detail-content {
  padding: 20px;
}

.el-table {
  border-radius: 8px;
  overflow: hidden;
}

.el-table th {
  background-color: #f5f7fa !important;
  color: #606266;
  font-weight: 600;
}

.el-table td {
  padding: 12px 0;
}

.el-tag {
  border-radius: 4px;
  padding: 0 10px;
  height: 24px;
  line-height: 24px;
}
</style> 