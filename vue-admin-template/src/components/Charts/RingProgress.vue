<template>
  <div class="ring-wrapper">
    <div ref="ring" class="ring"></div>
  </div>
</template>

<script>
import * as echarts from 'echarts'

export default {
  name: 'RingProgress',
  props: {
    value: { type: Number, required: true },
    color: { type: String, default: '#67C23A' },
    trackColor: { type: String, default: '#EBEEF5' },
    label: { type: String, default: '' }
  },
  data() {
    return { chart: null }
  },
  watch: {
    value(val) { this.update(val) },
    color() { this.update(this.value) }
  },
  mounted() {
    this.chart = echarts.init(this.$refs.ring)
    this.update(this.value)
  },
  beforeDestroy() {
    if (this.chart) { this.chart.dispose(); this.chart = null }
  },
  methods: {
    update(val) {
      if (!this.chart) return
      const v = Math.max(0, Math.min(100, Number(val) || 0))
      const option = {
        title: { text: this.label ? `${this.label}` : '', left: 'center', top: '72%', textStyle: { fontSize: 12, color: '#606266' } },
        series: [
          {
            type: 'pie',
            radius: ['70%', '85%'],
            silent: true,
            label: { show: false },
            data: [
              { value: v, name: 'value', itemStyle: { color: this.color } },
              { value: 100 - v, name: 'rest', itemStyle: { color: this.trackColor } }
            ]
          },
          {
            type: 'pie',
            radius: ['0%', '60%'],
            silent: true,
            label: { show: true, position: 'center', formatter: `{c}%`, fontSize: 18, fontWeight: 600, color: '#303133' },
            data: [{ value: v, itemStyle: { color: '#ffffff' } }]
          }
        ]
      }
      this.chart.setOption(option)
    }
  }
}
</script>

<style scoped>
.ring-wrapper { width: 100%; height: 100%; }
.ring { width: 100%; height: 100%; }
</style>
