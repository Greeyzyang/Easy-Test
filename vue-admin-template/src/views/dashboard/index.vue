<template>
  <div class="dashboard-container" v-loading="loading">
    <!-- 顶部欢迎区域 -->
    <el-card class="hero-card" shadow="hover">
      <div class="hero-content">
        <div class="hero-title">欢迎回来</div>
        <div class="hero-name">{{ name }}</div>
        <div class="hero-subtitle">自动化测试平台 · 概览</div>
      </div>
      <i class="el-icon-s-custom hero-icon"></i>
    </el-card>

    <!-- 指标卡片 -->
    <el-row :gutter="24" class="metrics-row">
      <el-col :xs="24" :sm="12" :md="6" v-for="card in cards" :key="card.key">
        <el-card class="metric-card" shadow="hover">
          <div class="metric-card__bg"></div>
          <div class="metric-card__content">
            <div class="metric-card__icon">
              <i :class="card.icon"></i>
            </div>
            <div class="metric-card__text">
              <div class="metric-title">{{ card.title }}</div>
              <div class="metric-value">
                {{ (metrics[card.key] !== undefined && metrics[card.key] !== null) ? metrics[card.key] : 0 }}
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 最近一次报告摘要 -->
    <el-card class="recent-report" v-if="metrics.last_report" shadow="always">
      <div slot="header" class="recent-header clearfix">
        <span>最近一次报告</span>
        <el-tag size="mini" :type="statusTagType(metrics.last_report.status)" class="status-tag">
          {{ metrics.last_report.status }}
        </el-tag>
      </div>
      <el-row :gutter="12" class="recent-body">
        <el-col :xs="24" :md="12">
          <div class="recent-item">ID：{{ metrics.last_report.id }}</div>
          <div class="recent-item">用例：{{ metrics.last_report.total_cases }}</div>
          <div class="recent-item">通过：{{ metrics.last_report.passed_cases }} · 失败：{{ metrics.last_report.failed_cases }} · 跳过：{{ metrics.last_report.skipped_cases }}</div>
        </el-col>
        <el-col :xs="24" :md="12">
          <div style="height: 160px;">
            <RingProgress :value="Number(metrics.last_report.pass_rate) || 0" label="通过率" />
          </div>
          <div class="recent-item">时长：{{ Number(metrics.last_report.duration_ms).toFixed(0) }} ms</div>
        </el-col>
      </el-row>
    </el-card>

    <!-- Jira Bug 模块分布（高级样式） -->
    <el-card class="jira-bug-card" shadow="hover">
      <div slot="header" class="jira-card-header">
        <div class="title">
          <i class="el-icon-pie-chart"></i>
          <span>Jira Bug 模块分布</span>
          <span class="subtitle" v-if="jiraDateRange && jiraDateRange.length === 2">日期：{{ jiraDateRange[0] }} 至 {{ jiraDateRange[1] }}</span>
        </div>
        <div class="jira-controls">
          <el-input
            v-model="bugProjectKey"
            size="mini"
            placeholder="选择项目（如 Gino）"
            style="width: 160px; margin-right: 8px;"
            prefix-icon="el-icon-search"
            clearable
            @keyup.enter.native="fetchJiraBugDistribution"
            @keydown.enter.native="fetchJiraBugDistribution"
            @keypress.enter.native="fetchJiraBugDistribution"
          />
          <el-select
            v-model="selectedFixVersionsBug"
            multiple
            clearable
            filterable
            collapse-tags
            :loading="loadingFixVersionsBug"
            size="mini"
            placeholder="修复版本"
            style="width: 240px; margin-right: 8px;"
            @visible-change="onFixVersionDropdownBug"
          >
            <el-option
              v-for="v in fixVersionOptionsBug"
              :key="v.id || v.name"
              :label="v.name"
              :value="v.name"
            />
          </el-select>
          <el-date-picker
            v-model="jiraDateRange"
            type="daterange"
            size="mini"
            style="width: 280px;"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="yyyy-MM-dd"
            unlink-panels
          />
          <el-button type="primary" size="mini" style="margin-left: 8px;" icon="el-icon-refresh"
                     :loading="jiraLoading" @click="fetchJiraBugDistribution">刷新</el-button>
        </div>
      </div>
      <el-row :gutter="16">
        <el-col :xs="24" :md="14" v-loading="jiraLoading">
          <div style="height: 360px;">
            <PieChart v-if="bugChartData" :chartData="bugChartData" :centerText="`总 Bug：${jiraSummary.total_bugs}`" />
            <div v-else class="empty-holder">
              <template v-if="!jiraQueried && !jiraLoading">尚未查询，点击右上角“刷新”手动开始</template>
              <template v-else>暂无数据</template>
            </div>
          </div>

          <div v-if="bugSeverityChartData" class="top-title" style="margin-top: 12px;">Bug 严重等级</div>
          <div style="height: 240px;">
            <PieChart
              v-if="bugSeverityChartData"
              :chartData="bugSeverityChartData"
              :centerText="`总 Bug：${jiraSummary.total_bugs}`"
              seriesName="严重等级"
            />
          </div>
        </el-col>
        <el-col :xs="24" :md="10">
          <div class="jira-summary">
            <div class="summary-row">
              <div class="summary-block">
                <div class="label">项目</div>
                <div class="value">{{ bugProjectKey }}</div>
              </div>
              <div class="summary-block primary">
                <div class="label">总 Bug</div>
                <div class="value">{{ jiraSummary.total_bugs }}</div>
              </div>
            </div>

            <div class="top-title" v-if="jiraSummary.items && jiraSummary.items.length">Top 模块</div>
            <ul class="top-list" v-if="jiraSummary.items && jiraSummary.items.length">
              <li v-for="(item, idx) in jiraSummary.items" :key="idx" class="top-item">
                <span class="dot" :style="{ backgroundColor: (bugChartData && bugChartData.datasets && bugChartData.datasets[0] && bugChartData.datasets[0].backgroundColor[idx]) || '#409EFF' }"></span>
                <span class="name">{{ item.module }}</span>
                <span class="spacer"></span>
                <span class="count">{{ item.bug_count }}</span>
                <span class="percent" v-if="jiraSummary.total_bugs">{{ ((item.bug_count / jiraSummary.total_bugs) * 100).toFixed(1) }}%</span>
              </li>
            </ul>

            

            <div v-if="jiraError" class="jira-error">{{ jiraError }}</div>
          </div>
        </el-col>
      </el-row>
    </el-card>

    <!-- 版本趋势折线图 -->
    <el-card class="version-trend-card" shadow="hover">
      <div slot="header" class="jira-card-header">
        <div class="title">
          <i class="el-icon-data-line"></i>
          <span>版本 Bug/需求趋势</span>
        </div>
        <div class="jira-controls">
          <el-input
            v-model="versionProjectKey"
            size="mini"
            placeholder="选择项目（如 Gino）"
            style="width: 160px; margin-right: 8px;"
            prefix-icon="el-icon-search"
            clearable
            @keyup.enter.native="fetchJiraVersionTrend"
            @keydown.enter.native="fetchJiraVersionTrend"
            @keypress.enter.native="fetchJiraVersionTrend"
          />
          <el-select
            v-model="selectedFixVersionsTrend"
            multiple
            clearable
            filterable
            collapse-tags
            :loading="loadingFixVersionsTrend"
            size="mini"
            placeholder="修复版本"
            style="width: 240px; margin-right: 8px;"
            @visible-change="onFixVersionDropdownTrend"
          >
            <el-option
              v-for="v in fixVersionOptionsTrend"
              :key="v.id || v.name"
              :label="v.name"
              :value="v.name"
            />
          </el-select>
          <el-button type="primary" size="mini" style="margin-left: 8px;" icon="el-icon-refresh"
                     :loading="versionTrendLoading" @click="fetchJiraVersionTrend">刷新</el-button>
        </div>
      </div>
      <div style="height: 360px;" v-loading="versionTrendLoading">
        <div ref="versionLineChart" style="width: 100%; height: 100%;"></div>
      </div>
    </el-card>
  </div>
</template>

<script>
import { mapGetters } from 'vuex'
import { getDashboardMetrics, getJiraBugDistribution, getJiraFixVersions, getJiraVersionTrend } from '@/api/metrics'
import PieChart from '@/components/Charts/PieChart.vue'
import RingProgress from '@/components/Charts/RingProgress.vue'
import * as echarts from 'echarts'

export default {
  name: 'Dashboard',
  components: { PieChart, RingProgress },
  computed: {
    ...mapGetters(['name'])
  },
  data() {
    return {
      loading: false,
      metrics: {
        testcase_count: 0,
        testsuite_count: 0,
        interface_count: 0,
        report_count: 0,
        recent_24h: { reports: 0, failed_steps: 0 },
        last_report: null
      },
      cards: [
        { key: 'testcase_count', title: '测试用例', icon: 'el-icon-document' },
        { key: 'testsuite_count', title: '测试任务', icon: 'el-icon-s-order' },
        { key: 'interface_count', title: '接口数量', icon: 'el-icon-link' },
        { key: 'report_count', title: '测试报告', icon: 'el-icon-data-analysis' }
      ],
      // Jira bug distribution state
      bugProjectKey: 'Gino',
      // 日期范围默认置空，由用户选择
      jiraDateRange: [],
      jiraSummary: { total_bugs: 0, items: [] },
      bugChartData: null,
      bugSeverityChartData: null,
      jiraError: '',
      jiraLoading: false,
      jiraQueried: false,
      // 修复版本筛选
      fixVersionOptionsBug: [],
      selectedFixVersionsBug: [],
      loadingFixVersionsBug: false,
      // 版本趋势
      versionTrendLoading: false,
      versionTrendItems: [],
      versionChart: null,
      versionProjectKey: 'Gino',
      fixVersionOptionsTrend: [],
      selectedFixVersionsTrend: [],
      loadingFixVersionsTrend: false
    }
  },
  mounted() {
    this.$nextTick(() => {
      this.initVersionChart()
    })
  },
  created() {
    this.fetchMetrics()
  },
  methods: {
    async fetchMetrics() {
      this.loading = true
      try {
        const res = await getDashboardMetrics()
        // 兼容后端 ResponseModel 包装，优先取 res.data.data
        const data = (res && res.data && (res.data.data || res.data)) || {}
        this.metrics = {
          ...this.metrics,
          ...data
        }
      } catch (e) {
        // 交由全局拦截器弹出错误，这里只做降级
        // eslint-disable-next-line no-console
        console.error('fetchMetrics error:', e)
      } finally {
        this.loading = false
      }
    },
    async fetchJiraBugDistribution() {
      this.jiraError = ''
      this.jiraLoading = true
      this.jiraQueried = true
      try {
        const range = Array.isArray(this.jiraDateRange) ? this.jiraDateRange : []
        const startDate = range[0]
        const endDate = range[1]
        const res = await getJiraBugDistribution(this.bugProjectKey, startDate, endDate, this.selectedFixVersionsBug)
        const data = (res && res.data && (res.data.data || res.data)) || {}
        this.jiraSummary = {
          total_bugs: data.total_bugs || 0,
          items: Array.isArray(data.items) ? data.items : [],
          bug_severity: Array.isArray(data.bug_severity) ? data.bug_severity : []
        }

        const labels = this.jiraSummary.items.map(it => it.module)
        const values = this.jiraSummary.items.map(it => it.bug_count)
        const colors = this.genColors(values.length)
        this.bugChartData = {
          labels,
          datasets: [{ data: values, backgroundColor: colors }]
        }
        const severityOrder = {
          '紧急': 1,
          'Important': 2,
          'Medium': 3,
          'Low': 4,
          'Lowest': 5
        }
        const severityColor = {
          '紧急': '#F56C6C',
          'Important': '#E6A23C',
          'Medium': '#409EFF',
          'Low': '#67C23A',
          'Lowest': '#909399'
        }
        const sevSorted = [...this.jiraSummary.bug_severity]
          .sort((a, b) => (severityOrder[a.name] || 99) - (severityOrder[b.name] || 99))
        const sevLabels = sevSorted.map(s => s.name)
        const sevValues = sevSorted.map(s => s.count)
        const sevColors = sevLabels.map(l => severityColor[l] || '#409EFF')
        this.bugSeverityChartData = {
          labels: sevLabels,
          datasets: [{ data: sevValues, backgroundColor: sevColors }]
        }
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('fetchJiraBugDistribution error:', e)
        this.jiraError = '获取 Jira 数据失败'
        this.bugChartData = null
        this.jiraSummary = { total_bugs: 0, items: [] }
      } finally {
        this.jiraLoading = false
      }
    },
    async fetchJiraVersionTrend() {
      this.versionTrendLoading = true
      try {
        const res = await getJiraVersionTrend(this.versionProjectKey, this.selectedFixVersionsTrend)
        const data = (res && res.data && (res.data.data || res.data)) || {}
        const items = Array.isArray(data.items) ? data.items : []
        this.versionTrendItems = items
        this.updateVersionChart()
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('getJiraVersionTrend error:', e)
        this.versionTrendItems = []
        this.updateVersionChart(true)
      } finally {
        this.versionTrendLoading = false
      }
    },
    initVersionChart() {
      if (this.versionChart) return
      const el = this.$refs.versionLineChart
      if (!el) return
      this.versionChart = echarts.init(el)
      this.updateVersionChart()
    },
    updateVersionChart(empty = false) {
      if (!this.versionChart) return
      const sorted = [...this.versionTrendItems].sort((a, b) => {
        const pa = String(a.version).trim().replace(/^v/i, '').split('.')
        const pb = String(b.version).trim().replace(/^v/i, '').split('.')
        const len = Math.max(pa.length, pb.length)
        for (let i = 0; i < len; i++) {
          const na = parseInt((pa[i] || '0').replace(/[^0-9]/g, ''), 10) || 0
          const nb = parseInt((pb[i] || '0').replace(/[^0-9]/g, ''), 10) || 0
          if (na !== nb) return na - nb
        }
        return 0
      })
      const versions = sorted.map(it => it.version)
      const bugCounts = sorted.map(it => it.bug_count)
      const demandCounts = sorted.map(it => it.demand_count)
      const option = {
        tooltip: { trigger: 'axis' },
        legend: { data: ['Bug', '需求'] },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', boundaryGap: false, data: versions },
        yAxis: { type: 'value' },
        series: [
          { name: 'Bug', type: 'line', smooth: true, data: bugCounts, itemStyle: { color: '#F56C6C' } },
          { name: '需求', type: 'line', smooth: true, data: demandCounts, itemStyle: { color: '#409EFF' } }
        ]
      }
      if (empty) {
        option.xAxis.data = []
        option.series.forEach(s => { s.data = [] })
      }
      this.versionChart.setOption(option)
    },
    async onFixVersionDropdownBug(visible) {
      if (!visible || this.fixVersionOptionsBug.length) return
      this.loadingFixVersionsBug = true
      try {
        const res = await getJiraFixVersions(this.bugProjectKey)
        const data = (res && res.data && (res.data.data || res.data)) || {}
        this.fixVersionOptionsBug = Array.isArray(data.versions) ? data.versions : []
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('getJiraFixVersions error:', e)
        this.$message.error('修复版本加载失败')
      } finally {
        this.loadingFixVersionsBug = false
      }
    },
    async onFixVersionDropdownTrend(visible) {
      if (!visible || this.fixVersionOptionsTrend.length) return
      this.loadingFixVersionsTrend = true
      try {
        const res = await getJiraFixVersions(this.versionProjectKey)
        const data = (res && res.data && (res.data.data || res.data)) || {}
        this.fixVersionOptionsTrend = Array.isArray(data.versions) ? data.versions : []
      } catch (e) {
        // eslint-disable-next-line no-console
        console.error('getJiraFixVersions error:', e)
        this.$message.error('修复版本加载失败')
      } finally {
        this.loadingFixVersionsTrend = false
      }
    },
    genColors(n) {
      const palette = [
        '#409EFF', '#67C23A', '#E6A23C', '#F56C6C', '#909399',
        '#9C27B0', '#00BCD4', '#8BC34A', '#FF9800', '#795548',
        '#03A9F4', '#4CAF50', '#FFC107', '#FF5722', '#607D8B'
      ]
      if (n <= palette.length) return palette.slice(0, n)
      const colors = palette.slice(0)
      while (colors.length < n) {
        // 生成更多颜色（简单变体）
        const r = Math.floor(100 + Math.random() * 155)
        const g = Math.floor(100 + Math.random() * 155)
        const b = Math.floor(100 + Math.random() * 155)
        colors.push(`#${r.toString(16)}${g.toString(16)}${b.toString(16)}`)
      }
      return colors.slice(0, n)
    },
    statusTagType(status) {
      if (!status) return 'info'
      const s = String(status).toUpperCase()
      if (s === 'COMPLETED' || s === 'SUCCESS') return 'success'
      if (s === 'RUNNING' || s === 'IN_PROGRESS') return 'warning'
      if (s === 'FAILED' || s === 'ERROR') return 'danger'
      return 'info'
    }
  }
}
</script>

<style lang="scss" scoped>
.dashboard-container {
  margin: 24px;
}

.hero-card {
  position: relative;
  overflow: hidden;
  border: none;
  background: linear-gradient(135deg, #38b2ac 0%, #4299e1 40%, #805ad5 100%);
  color: #fff;
  margin-bottom: 18px;
  .el-card__body {
    padding: 20px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
  }
}
.hero-content {
  z-index: 1;
}
.hero-title {
  font-size: 14px;
  opacity: 0.85;
}
.hero-name {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.5px;
}
.hero-subtitle {
  font-size: 12px;
  opacity: 0.85;
  margin-top: 4px;
}
.hero-icon {
  font-size: 48px;
  opacity: 0.2;
}

.metrics-row {
  margin-top: 8px;
}

.metric-card {
  position: relative;
  border: none;
  border-radius: 12px;
  overflow: hidden;
  background: #ffffff;
  transition: all .25s ease;
  box-shadow: 0 6px 16px rgba(0,0,0,.06);
  .el-card__body {
    padding: 16px;
  }
}
.metric-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 24px rgba(0,0,0,.08);
}
.metric-card__bg {
  position: absolute;
  right: -30px;
  top: -30px;
  width: 160px;
  height: 160px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(64,158,255,.15), rgba(103,194,58,.15));
  filter: blur(6px);
}
.metric-card__content {
  display: flex;
  align-items: center;
}
.metric-card__icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #409EFF;
  background: rgba(64,158,255,.1);
  margin-right: 12px;
  i { font-size: 22px; }
}
.metric-title {
  font-size: 13px;
  color: #6b7280;
}
.metric-value {
  font-size: 28px;
  font-weight: 700;
  color: #111827;
  line-height: 1.2;
  margin-top: 2px;
}

.recent-report {
  margin-top: 18px;
  border-radius: 12px;
  overflow: hidden;
}
.recent-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.status-tag {
  margin-left: 8px;
}
.recent-body {
  .recent-item {
    font-size: 13px;
    color: #4b5563;
    margin: 6px 0;
  }
}
.jira-bug-card {
  margin-top: 18px;
  .el-card__body { padding: 12px 16px; }
}
.jira-controls {
  float: right;
  display: flex;
  align-items: center;
}
.empty-holder {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}
.jira-summary {
  padding: 8px 4px;
}
.summary-item { margin-bottom: 8px; }
.summary-list { margin: 6px 0 0 0; padding-left: 18px; }
.jira-error { color: #F56C6C; margin-top: 6px; }

/* 高级样式 */
.jira-bug-card {
  border-radius: 12px;
  overflow: hidden;
}
.jira-bug-card .el-card__header {
  background: linear-gradient(90deg, #f0f7ff 0%, #ffffff 100%);
  padding: 12px 16px;
  border-bottom: none;
}
.jira-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.jira-card-header .title {
  display: flex;
  align-items: center;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}
.jira-card-header .title i {
  color: #409EFF;
  margin-right: 6px;
}
.jira-card-header .subtitle {
  margin-left: 8px;
  font-size: 13px;
  color: #909399;
}
.jira-controls {
  display: flex;
  align-items: center;
}
.jira-summary .summary-row {
  display: flex;
  gap: 12px;
  margin-bottom: 10px;
}
.summary-block {
  flex: 1;
  background: #f8fafc;
  border-radius: 8px;
  padding: 10px 12px;
}
.summary-block.primary {
  background: #f0f7ff;
}
.summary-block .label {
  font-size: 12px;
  color: #909399;
}
.summary-block .value {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
}
.top-title {
  margin: 6px 0 8px 0;
  font-size: 13px;
  color: #606266;
}
.top-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.top-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 4px;
  border-bottom: 1px dashed #ebeef5;
}
.top-item:last-child {
  border-bottom: none;
}
.top-item .dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
}
.top-item .name { flex: 0 1 auto; font-weight: 500; color: #303133; }
.top-item .spacer { flex: 1; border-bottom: 1px dotted #ebeef5; opacity: 0.6; }
.top-item .count { font-weight: 600; color: #606266; }
.top-item .percent { font-size: 12px; color: #909399; }
</style>
