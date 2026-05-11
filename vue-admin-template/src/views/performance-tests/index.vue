<template>
  <div class="app-container">
    <div class="filter-container">
      <el-input
        v-model="listQuery.name"
        placeholder="压测名称"
        style="width: 200px;"
        class="filter-item"
        clearable
        @keyup.enter.native="handleFilter"
      />
      <el-select
        v-model="listQuery.project_id"
        placeholder="所属项目"
        style="width: 180px;"
        class="filter-item"
        clearable
        filterable
        @change="handleFilter"
      >
        <el-option
          v-for="p in projectOptions"
          :key="p.id"
          :label="p.name"
          :value="p.id"
        />
      </el-select>
      <el-button v-waves class="filter-item" type="primary" icon="el-icon-search" @click="handleFilter">
        搜索
      </el-button>
      <el-button class="filter-item" style="margin-left: 10px;" type="primary" icon="el-icon-plus" @click="handleCreate">
        新建压测
      </el-button>
    </div>

    <el-table
      v-loading="listLoading"
      :data="list"
      element-loading-text="加载中..."
      border
      fit
      highlight-current-row
      style="width: 100%;"
    >
      <el-table-column label="压测名称" min-width="180">
        <template slot-scope="scope">
          <span class="link-type" @click="handleUpdate(scope.row)">{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="160">
        <template slot-scope="scope">
          <span>{{ scope.row.description || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="并发用户" align="center" width="100">
        <template slot-scope="scope">
          <el-tag type="info">{{ scope.row.concurrent_users }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="模式" align="center" width="100">
        <template slot-scope="scope">
          <el-tag :type="scope.row.run_mode === 'fixed_requests' ? 'warning' : 'primary'" size="small">
            {{ scope.row.run_mode === 'fixed_requests' ? '固定请求' : '固定时长' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="目标" align="center" width="100">
        <template slot-scope="scope">
          <span v-if="scope.row.run_mode === 'fixed_requests'">
            {{ scope.row.total_requests_limit ? scope.row.total_requests_limit + ' reqs' : '-' }}
          </span>
          <span v-else>{{ scope.row.duration_seconds }}s</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" align="center" width="100">
        <template slot-scope="scope">
          <el-tag :type="statusType(scope.row.status)">{{ statusText(scope.row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" align="center" width="160">
        <template slot-scope="scope">
          <span>{{ formatDate(scope.row.created_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" min-width="280">
        <template slot-scope="scope">
          <div v-if="scope.row.running" style="width: 100%; display: flex; flex-direction: column; align-items: center;">
            <el-progress
              :percentage="scope.row.progressPercent || 0"
              :text-inside="true"
              :stroke-width="20"
              style="width: 90%; margin-bottom: 8px;"
            />
            <div style="width: 100%; display: flex; justify-content: center; gap: 5px;">
              <div style="color: #409EFF; font-size: 12px; line-height: 28px;">{{ scope.row.progressText || '执行中...' }}</div>
              <el-button type="danger" size="mini" @click="handleStop(scope.row)">
                停止
              </el-button>
            </div>
          </div>
          <div v-else style="display: flex; flex-wrap: wrap; justify-content: center; gap: 5px;">
            <el-button type="success" size="mini" @click="handleRun(scope.row)">
              运行
            </el-button>
            <el-button type="info" size="mini" @click="handleViewReports(scope.row)">
              报告
            </el-button>
            <el-button type="primary" size="mini" @click="handleUpdate(scope.row)">
              编辑
            </el-button>
            <el-button type="danger" size="mini" @click="handleDelete(scope.row)">
              删除
            </el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total > 0"
      :total="total"
      :page.sync="listQuery.page"
      :limit.sync="listQuery.limit"
      @pagination="getList"
    />

    <!-- Run Progress Dialog -->
    <el-dialog
      :visible.sync="progressDialogVisible"
      title="压测执行中"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-progress
        :percentage="progressPercent"
        :text-inside="true"
        :stroke-width="24"
        :status="progressStatus"
        style="margin-bottom: 16px;"
      />
      <div v-if="currentMetrics" style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 13px;">
        <div>总请求: <b>{{ currentMetrics.total_requests }}</b></div>
        <div>成功: <b style="color: #67C23A;">{{ currentMetrics.successful_requests }}</b></div>
        <div>失败: <b style="color: #F56C6C;">{{ currentMetrics.failed_requests }}</b></div>
        <div>错误率: <b>{{ ((currentMetrics.error_rate || 0) * 100).toFixed(2) }}%</b></div>
        <div>平均RT: <b>{{ currentMetrics.avg_response_time }}ms</b></div>
        <div>RPS: <b>{{ currentMetrics.requests_per_second }}</b></div>
        <div>P90: <b>{{ currentMetrics.p90_response_time }}ms</b></div>
        <div>P99: <b>{{ currentMetrics.p99_response_time }}ms</b></div>
      </div>
      <div style="text-align: center; margin-top: 12px; color: #909399;">{{ progressText }}</div>
      <div slot="footer">
        <el-button type="danger" @click="handleStop(scope.row)">停止压测</el-button>
        <el-button type="primary" @click="viewReport">查看报告</el-button>
        <el-button @click="progressDialogVisible = false">关闭</el-button>
      </div>
    </el-dialog>

    <!-- Reports Dialog -->
    <el-dialog :visible.sync="reportsDialogVisible" title="压测报告" width="90%" top="5vh">
      <el-table
        v-loading="reportsLoading"
        :data="reportList"
        border
        style="width: 100%;"
      >
        <el-table-column label="状态" align="center" width="80">
          <template slot-scope="{ row }">
            <el-tag :type="statusType(row.status)">{{ statusText(row.status) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" align="center" width="160">
          <template slot-scope="{ row }">
            <span>{{ formatDate(row.start_time) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="持续" align="center" width="80">
          <template slot-scope="{ row }">
            <span>{{ row.duration_seconds }}s</span>
          </template>
        </el-table-column>
        <el-table-column label="总请求" align="center" width="80">
          <template slot-scope="{ row }">
            <span>{{ row.total_requests }}</span>
          </template>
        </el-table-column>
        <el-table-column label="成功/失败" align="center" width="100">
          <template slot-scope="{ row }">
            <span style="color: #67C23A;">{{ row.successful_requests }}</span>
            /
            <span style="color: #F56C6C;">{{ row.failed_requests }}</span>
          </template>
        </el-table-column>
        <el-table-column label="平均RT" align="center" width="90">
          <template slot-scope="{ row }">
            <span>{{ row.avg_response_time ? row.avg_response_time + 'ms' : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="P90" align="center" width="80">
          <template slot-scope="{ row }">
            <span>{{ row.p90_response_time ? row.p90_response_time + 'ms' : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="P99" align="center" width="80">
          <template slot-scope="{ row }">
            <span>{{ row.p99_response_time ? row.p99_response_time + 'ms' : '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="RPS" align="center" width="80">
          <template slot-scope="{ row }">
            <span>{{ row.requests_per_second || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" align="center" width="80">
          <template slot-scope="{ row }">
            <el-button type="text" size="mini" @click="openReport(row)">详情</el-button>
          </template>
        </el-table-column>
      </el-table>
      <pagination
        v-show="reportTotal > 0"
        :total="reportTotal"
        :page.sync="reportQuery.page"
        :limit.sync="reportQuery.limit"
        @pagination="getReports"
      />
    </el-dialog>
  </div>
</template>

<script>
import { getPerformanceTestList, deletePerformanceTest, executePerformanceTest, stopPerformanceTest, getPerformanceTestReports } from '@/api/performance-test'
import { getProjectList as getProjects } from '@/api/project'
import waves from '@/directive/waves'
import Pagination from '@/components/Layout/Pagination'
import { formatDateTime } from '@/utils/format'

export default {
  name: 'PerformanceTestList',
  components: { Pagination },
  directives: { waves },
  data() {
    return {
      list: [],
      total: 0,
      listLoading: false,
      listQuery: {
        page: 1,
        limit: 10,
        name: undefined,
        project_id: undefined
      },
      projectOptions: [],
      progressDialogVisible: false,
      progressPercent: 0,
      progressStatus: 'warning',
      progressText: '',
      currentMetrics: null,
      currentTaskId: null,
      currentRow: null,
      pollingTimer: null,
      reportsDialogVisible: false,
      reportList: [],
      reportTotal: 0,
      reportsLoading: false,
      reportQuery: {
        page: 1,
        limit: 10
      },
      currentPerformanceTestId: null
    }
  },
  created() {
    this.getList()
    this.getProjectOptions()
  },
  beforeDestroy() {
    this.stopPolling()
  },
  methods: {
    formatDate(v) {
      return v ? formatDateTime(v) : '-'
    },
    statusType(status) {
      const map = {
        PENDING: 'info',
        IN_PROGRESS: 'warning',
        COMPLETED: 'success',
        PASSED: 'success',
        FAILED: 'danger',
        SKIPPED: 'info'
      }
      return map[status] || 'info'
    },
    statusText(status) {
      const map = {
        PENDING: '待执行',
        IN_PROGRESS: '执行中',
        COMPLETED: '已完成',
        PASSED: '通过',
        FAILED: '失败',
        SKIPPED: '跳过'
      }
      return map[status] || status
    },
    async getProjectOptions() {
      try {
        const res = await getProjects({ limit: 1000 })
        if (res && res.code === '0' && res.data) {
          this.projectOptions = res.data.items || []
        }
      } catch (e) {
        console.error('获取项目列表失败', e)
      }
    },
    async getList() {
      this.listLoading = true
      try {
        const response = await getPerformanceTestList(this.listQuery)
        if (response && response.code === '0' && response.data) {
          this.list = (response.data.items || []).map(item => ({
            ...item,
            running: false,
            progressPercent: 0,
            progressText: ''
          }))
          this.total = response.data.total || 0
        } else {
          this.list = []
          this.total = 0
        }
      } catch (error) {
        console.error('获取压测列表失败', error)
        this.$message.error('获取压测列表失败')
        this.list = []
        this.total = 0
      } finally {
        this.listLoading = false
      }
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleCreate() {
      this.$router.push('/performance/create')
    },
    handleUpdate(row) {
      this.$router.push(`/performance/edit/${row.id}`)
    },
    async handleRun(row) {
      this.currentRow = row
      this.progressDialogVisible = true
      this.progressPercent = 0
      this.progressText = '提交压测任务...'
      this.currentMetrics = null
      this.currentTaskId = null

      this.$set(row, 'running', true)
      this.$set(row, 'progressPercent', 0)

      try {
        const res = await executePerformanceTest(row.id)
        if (res && res.code === '0') {
          this.currentTaskId = res.data.task_id
          this.progressText = '压测已启动，等待结果...'
          this.startPolling()
        } else {
          this.progressText = '提交失败: ' + (res.msg || '未知错误')
          this.$set(row, 'running', false)
        }
      } catch (error) {
        console.error('启动压测失败', error)
        this.progressText = '启动失败: ' + (error.message || '未知错误')
        this.$set(row, 'running', false)
      }
    },
    async handleStop(row) {
      try {
        await stopPerformanceTest(row.id)
        this.stopPolling()
        this.progressText = '已停止'
        this.progressStatus = 'warning'
        this.$set(row, 'running', false)
        this.$message.success('压测已停止')
      } catch (error) {
        console.error('停止压测失败', error)
        this.$message.error('停止失败: ' + (error.message || '未知错误'))
      }
    },
    startPolling() {
      this.stopPolling()
      this.pollingTimer = setInterval(() => {
        this.pollProgress()
      }, 3000)
    },
    stopPolling() {
      if (this.pollingTimer) {
        clearInterval(this.pollingTimer)
        this.pollingTimer = null
      }
    },
    async pollProgress() {
      if (!this.currentTaskId) return
      try {
        const baseURL = process.env.VUE_APP_BASE_API
        const url = baseURL + `/rest/v1/tasks/async/${this.currentTaskId}`
        const token = localStorage.getItem('token') || localStorage.getItem('Admin-Token')
        const headers = token ? { Authorization: `Bearer ${token}` } : {}
        const resp = await fetch(url, { headers })
        if (!resp.ok) return
        const data = await resp.json()

        if (data.state === 'SUCCESS' || data.state === 'FAILURE') {
          this.stopPolling()
          this.progressPercent = 100
          this.progressText = data.state === 'SUCCESS' ? '压测完成' : '压测失败'
          this.progressStatus = data.state === 'SUCCESS' ? 'success' : 'exception'
          if (data.result) {
            try {
              const result = typeof data.result === 'string' ? JSON.parse(data.result) : data.result
              if (result.report_id) {
                this.currentPerformanceTestId = result.report_id
              }
            } catch (e) {}
          }
          if (this.currentRow) {
            this.$set(this.currentRow, 'running', false)
          }
          if (data.state === 'FAILURE') {
            this.$message.error('压测执行失败')
          }
        } else if (data.state === 'PROGRESS' && data.meta) {
          const m = data.meta
          this.progressPercent = m.progress || 0
          this.progressText = m.message || m.text || '执行中...'
          this.currentMetrics = {
            total_requests: m.total_requests || 0,
            successful_requests: m.successful_requests || 0,
            failed_requests: m.failed_requests || 0,
            error_rate: m.error_rate || 0,
            avg_response_time: m.avg_response_time || 0,
            p90_response_time: m.p90_response_time || 0,
            p99_response_time: m.p99_response_time || 0,
            requests_per_second: m.requests_per_second || 0
          }
          if (this.currentRow) {
            this.$set(this.currentRow, 'progressPercent', this.progressPercent)
            this.$set(this.currentRow, 'progressText', this.progressText)
          }
        }
      } catch (error) {
        console.error('轮询进度失败', error)
      }
    },
    handleStop() {
      this.stopPolling()
      this.progressText = '压测已停止'
      if (this.currentRow) {
        this.$set(this.currentRow, 'running', false)
      }
    },
    viewReport() {
      if (this.currentPerformanceTestId) {
        this.progressDialogVisible = false
        this.$router.push(`/performance/report/${this.currentPerformanceTestId}`)
      } else {
        this.$message.warning('暂无可用报告')
      }
    },
    openReport(row) {
      this.reportsDialogVisible = false
      this.$router.push(`/performance/report/${row.id}`)
    },
    async handleViewReports(row) {
      this.currentPerformanceTestId = row.id
      this.reportsDialogVisible = true
      await this.getReports()
    },
    async getReports() {
      if (!this.currentPerformanceTestId) return
      this.reportsLoading = true
      try {
        const res = await getPerformanceTestReports(this.currentPerformanceTestId, this.reportQuery)
        if (res && res.code === '0' && res.data) {
          this.reportList = res.data.items || []
          this.reportTotal = res.data.total || 0
        } else {
          this.reportList = []
          this.reportTotal = 0
        }
      } catch (error) {
        console.error('获取报告列表失败', error)
        this.reportList = []
        this.reportTotal = 0
      } finally {
        this.reportsLoading = false
      }
    },
    async handleDelete(row) {
      try {
        await this.$confirm('确认删除该压测配置？删除后不可恢复', '删除确认', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await deletePerformanceTest(row.id)
        this.$message.success('删除成功')
        this.getList()
      } catch (e) {
        if (e !== 'cancel') {
          this.$message.error('删除失败')
        }
      }
    }
  }
}
</script>
