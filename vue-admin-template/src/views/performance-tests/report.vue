<template>
  <div class="app-container">
    <!-- Header -->
    <div class="page-header">
      <el-button icon="el-icon-arrow-left" @click="goBack">返回</el-button>
      <h2 style="margin: 0 0 0 16px; display: inline-block;">压测报告详情</h2>
    </div>

    <div v-loading="loading">
      <!-- Report Summary -->
      <el-row :gutter="16" style="margin-bottom: 20px;">
        <el-col :span="6">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-label">总请求数</div>
            <div class="metric-value">{{ report.total_requests || 0 }}</div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-label">成功 / 失败</div>
            <div class="metric-value">
              <span style="color: #67C23A;">{{ report.successful_requests || 0 }}</span>
              /
              <span style="color: #F56C6C;">{{ report.failed_requests || 0 }}</span>
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-label">错误率</div>
            <div class="metric-value" :style="{ color: errorRate > 5 ? '#F56C6C' : '#67C23A' }">
              {{ ((report.error_rate || 0) * 100).toFixed(2) }}%
            </div>
          </el-card>
        </el-col>
        <el-col :span="6">
          <el-card shadow="hover" class="metric-card">
            <div class="metric-label">吞吐量 (RPS)</div>
            <div class="metric-value" style="color: #409EFF;">{{ report.requests_per_second || 0 }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Response Time Stats -->
      <el-row :gutter="16" style="margin-bottom: 20px;">
        <el-col :span="8">
          <el-card shadow="hover">
            <div slot="header">响应时间统计 (ms)</div>
            <el-table :data="rtStatsData" border size="small">
              <el-table-column prop="label" label="指标" />
              <el-table-column prop="value" label="响应时间" align="right">
                <template slot-scope="{ row }">
                  {{ row.value != null ? row.value + ' ms' : '-' }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
        <el-col :span="16">
          <el-card shadow="hover">
            <div slot="header">响应时间分布</div>
            <div ref="rtDistChart" style="height: 220px;"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Charts -->
      <el-row :gutter="16" style="margin-bottom: 20px;">
        <el-col :span="12">
          <el-card shadow="hover">
            <div slot="header">响应时间趋势</div>
            <div ref="rtChart" style="height: 280px;"></div>
          </el-card>
        </el-col>
        <el-col :span="12">
          <el-card shadow="hover">
            <div slot="header">吞吐量趋势</div>
            <div ref="rpsChart" style="height: 280px;"></div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Scenario Stats -->
      <el-row v-if="report.scenario_stats && Object.keys(report.scenario_stats).length > 0" :gutter="16">
        <el-col :span="24">
          <el-card shadow="hover">
            <div slot="header">场景分布</div>
            <el-table :data="scenarioStatsData" border>
              <el-table-column prop="name" label="场景名称" />
              <el-table-column prop="total_requests" label="总请求数" align="center" />
              <el-table-column label="成功/失败" align="center">
                <template slot-scope="{ row }">
                  <span style="color: #67C23A;">{{ row.successful_requests }}</span>
                  /
                  <span style="color: #F56C6C;">{{ row.failed_requests }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="avg_response_time" label="平均响应时间" align="center">
                <template slot-scope="{ row }">
                  {{ row.avg_response_time != null ? row.avg_response_time + ' ms' : '-' }}
                </template>
              </el-table-column>
              <el-table-column label="占比" align="center">
                <template slot-scope="{ row }">
                  {{ row.percentage }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-col>
      </el-row>
    </div>
  </div>
</template>

<script>
import { getPerformanceTestReport } from '@/api/performance-test'
import * as echarts from 'echarts'

export default {
  name: 'PerformanceTestReport',
  data() {
    return {
      loading: false,
      report: {},
      rtChart: null,
      rpsChart: null,
      rtDistChart: null
    }
  },
  computed: {
    errorRate() {
      return ((this.report.error_rate || 0) * 100).toFixed(2)
    },
    rtStatsData() {
      return [
        { label: '平均响应时间 (Avg)', value: this.report.avg_response_time },
        { label: '中位数 (P50)', value: this.report.median_response_time },
        { label: 'P90', value: this.report.p90_response_time },
        { label: 'P95', value: this.report.p95_response_time },
        { label: 'P99', value: this.report.p99_response_time },
        { label: '最大响应时间 (Max)', value: this.report.max_response_time },
        { label: '最小响应时间 (Min)', value: this.report.min_response_time },
        { label: '标准差 (StdDev)', value: this.report.stddev_response_time }
      ]
    },
    scenarioStatsData() {
      if (!this.report.scenario_stats) return []
      const total = Object.values(this.report.scenario_stats).reduce((s, sc) => s + sc.total_requests, 0)
      return Object.entries(this.report.scenario_stats).map(([name, sc]) => ({
        name,
        total_requests: sc.total_requests,
        successful_requests: sc.successful_requests,
        failed_requests: sc.failed_requests,
        avg_response_time: sc.avg_response_time,
        percentage: total > 0 ? ((sc.total_requests / total) * 100).toFixed(1) + '%' : '0%'
      }))
    }
  },
  async mounted() {
    await this.loadReport()
    this.$nextTick(() => {
      this.initCharts()
    })
  },
  beforeDestroy() {
    this.disposeCharts()
  },
  methods: {
    goBack() {
      this.$router.push('/performance/index')
    },
    async loadReport() {
      this.loading = true
      try {
        const id = this.$route.params.id
        const res = await getPerformanceTestReport(id)
        if (res && res.code === '0' && res.data) {
          this.report = res.data
        }
      } catch (e) {
        this.$message.error('加载报告失败')
      } finally {
        this.loading = false
      }
    },
    initCharts() {
      this.rtChart = echarts.init(this.$refs.rtChart)
      this.rpsChart = echarts.init(this.$refs.rpsChart)
      this.rtDistChart = echarts.init(this.$refs.rtDistChart)
      this.updateCharts()
    },
    disposeCharts() {
      if (this.rtChart) { this.rtChart.dispose(); this.rtChart = null }
      if (this.rpsChart) { this.rpsChart.dispose(); this.rpsChart = null }
      if (this.rtDistChart) { this.rtDistChart.dispose(); this.rtDistChart = null }
    },
    updateCharts() {
      const timeline = this.report.timeline_data || []
      const rtOption = {
        tooltip: { trigger: 'axis' },
        xAxis: {
          type: 'category',
          data: timeline.map((t, i) => i + 1),
          name: 'Time (s)'
        },
        yAxis: {
          type: 'value',
          name: 'Response Time (ms)',
          axisLabel: { formatter: '{value} ms' }
        },
        series: [
          {
            name: '平均RT',
            type: 'line',
            data: timeline.map(t => t.avg_rt || 0),
            smooth: true,
            lineStyle: { width: 2 },
            areaStyle: { opacity: 0.1 }
          },
          {
            name: 'P90',
            type: 'line',
            data: timeline.map(t => t.p90_rt || 0),
            smooth: true,
            lineStyle: { width: 1, type: 'dashed' }
          }
        ],
        legend: { data: ['平均RT', 'P90'] },
        grid: { left: '12%', right: '4%', bottom: '10%' }
      }

      const rpsOption = {
        tooltip: { trigger: 'axis' },
        xAxis: {
          type: 'category',
          data: timeline.map((t, i) => i + 1),
          name: 'Time (s)'
        },
        yAxis: {
          type: 'value',
          name: 'Requests/s'
        },
        series: [
          {
            name: 'RPS',
            type: 'bar',
            data: timeline.map(t => t.rps || 0),
            itemStyle: { color: '#409EFF', opacity: 0.7 }
          }
        ],
        grid: { left: '12%', right: '4%', bottom: '10%' }
      }

      const p50 = this.report.median_response_time || 0
      const p90 = this.report.p90_response_time || 0
      const p95 = this.report.p95_response_time || 0
      const p99 = this.report.p99_response_time || 0
      const max = this.report.max_response_time || 0

      const distOption = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        xAxis: {
          type: 'category',
          data: ['Min', 'P50', 'P90', 'P95', 'P99', 'Max']
        },
        yAxis: {
          type: 'value',
          name: 'ms',
          axisLabel: { formatter: '{value}ms' }
        },
        series: [{
          name: '响应时间',
          type: 'bar',
          data: [
            { value: this.report.min_response_time || 0, itemStyle: { color: '#67C23A' } },
            { value: p50, itemStyle: { color: '#E6A23C' } },
            { value: p90, itemStyle: { color: '#409EFF' } },
            { value: p95, itemStyle: { color: '#9B59B6' } },
            { value: p99, itemStyle: { color: '#F56C6C' } },
            { value: max, itemStyle: { color: '#E74C3C' } }
          ],
          label: { show: true, formatter: '{c}ms', position: 'top' }
        }],
        grid: { left: '12%', right: '4%', bottom: '10%' }
      }

      this.rtChart.setOption(rtOption)
      this.rpsChart.setOption(rpsOption)
      this.rtDistChart.setOption(distOption)

      window.addEventListener('resize', () => {
        this.rtChart && this.rtChart.resize()
        this.rpsChart && this.rpsChart.resize()
        this.rtDistChart && this.rtDistChart.resize()
      })
    }
  }
}
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  margin-bottom: 20px;
}
.metric-card {
  text-align: center;
}
.metric-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 8px;
}
.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: #303133;
}
</style>
