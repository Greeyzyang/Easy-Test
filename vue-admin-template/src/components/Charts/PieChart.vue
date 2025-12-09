<template>
  <div class="chart-wrapper">
    <div ref="pieChart" class="chart"></div>
  </div>
</template>

<script>
import * as echarts from 'echarts'

export default {
  name: 'PieChart',
  props: {
    chartData: {
      type: Object,
      required: true
    },
    // 可选：在圆心显示的文本，如 “总 Bug：1158”
    centerText: {
      type: String,
      default: ''
    },
    legendPosition: {
      type: String,
      default: 'left'
    },
    legendOrient: {
      type: String,
      default: 'vertical'
    },
    seriesName: {
      type: String,
      default: '数据分布'
    }
  },
  data() {
    return {
      chart: null
    }
  },
  watch: {
    chartData: {
      handler(newVal) {
        this.updateChart(newVal)
      },
      deep: true
    }
  },
  mounted() {
    this.initChart()
  },
  beforeDestroy() {
    if (this.chart) {
      this.chart.dispose()
      this.chart = null
    }
  },
  methods: {
    initChart() {
      this.chart = echarts.init(this.$refs.pieChart)
      this.updateChart(this.chartData)
    },
    updateChart(data) {
      if (!this.chart) return

      const values = (data && data.datasets && data.datasets[0] && Array.isArray(data.datasets[0].data))
        ? data.datasets[0].data
        : []
      const total = values.reduce((sum, v) => sum + (Number(v) || 0), 0)

      const option = {
        tooltip: {
          trigger: 'item',
          formatter: '{a} <br/>{b}: {c} ({d}%)'
        },
        legend: {
          type: 'scroll',
          orient: this.legendOrient,
          left: this.legendPosition === 'left' ? 0 : 'center',
          right: this.legendPosition === 'left' ? undefined : 0,
          bottom: this.legendPosition === 'bottom' ? 0 : undefined,
          top: this.legendPosition === 'left' ? 'middle' : undefined,
          itemWidth: 12,
          itemHeight: 12,
          textStyle: { color: '#606266' },
          pageTextStyle: { color: '#606266' },
          data: data.labels
        },
        // 圆心总计文本
        graphic: [
          {
            type: 'text',
            left: 'center',
            top: 'middle',
            style: {
              text: this.centerText || (total ? `总计\n${total}` : ''),
              textAlign: 'center',
              fontSize: 16,
              fontWeight: 600,
              lineHeight: 22,
              fill: '#303133'
            }
          }
        ],
        series: [
          {
            name: this.seriesName,
            type: 'pie',
            radius: ['50%', '70%'],
            avoidLabelOverlap: false,
            itemStyle: {
              borderRadius: 8,
              borderColor: '#fff',
              borderWidth: 2
            },
            label: {
              show: false,
              position: 'center'
            },
            emphasis: {
              label: {
                show: false
              }
            },
            labelLine: {
              show: false
            },
            data: data.labels.map((label, index) => ({
              value: data.datasets[0].data[index],
              name: label,
              itemStyle: {
                color: data.datasets[0].backgroundColor[index]
              }
            }))
          }
        ]
      }

      this.chart.setOption(option)
    }
  }
}
</script>

<style scoped>
.chart-wrapper {
  width: 100%;
  height: 100%;
}

.chart {
  width: 100%;
  height: 100%;
}
</style>
