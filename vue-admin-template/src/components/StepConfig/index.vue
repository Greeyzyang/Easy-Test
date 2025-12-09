<template>
  <div>
    <!-- HTTP请求配置 -->
    <template v-if="step.type === 'http'">
      <el-form-item label="请求方法" prop="config.method">
        <el-select v-model="step.config.method" placeholder="请选择请求方法">
          <el-option label="GET" value="GET" />
          <el-option label="POST" value="POST" />
          <el-option label="PUT" value="PUT" />
          <el-option label="DELETE" value="DELETE" />
          <el-option label="PATCH" value="PATCH" />
        </el-select>
      </el-form-item>

      <el-form-item label="请求URL" prop="config.url">
        <el-input v-model="step.config.url" placeholder="请输入请求URL" />
      </el-form-item>

      <el-form-item label="请求头">
        <div v-for="(header, index) in step.config.headers" :key="index" class="header-item">
          <el-input v-model="header.key" placeholder="Key" style="width: 200px;" />
          <el-input v-model="header.value" placeholder="Value" style="width: 200px; margin: 0 10px;" />
          <el-button type="danger" icon="el-icon-delete" circle @click="removeHeader(index)" />
        </div>
        <el-button type="primary" icon="el-icon-plus" @click="addHeader">添加请求头</el-button>
      </el-form-item>

      <el-form-item label="请求体" v-if="step.config.method !== 'GET'">
        <el-input
          v-model="step.config.body"
          type="textarea"
          :rows="4"
          placeholder="请输入请求体（JSON格式）"
        />
      </el-form-item>
    </template>

    <!-- UI操作配置 -->
    <template v-if="step.type === 'ui'">
      <el-form-item label="操作类型" prop="config.action">
        <el-select v-model="step.config.action" placeholder="请选择操作类型">
          <el-option label="点击" value="click" />
          <el-option label="输入" value="input" />
          <el-option label="等待" value="wait" />
          <el-option label="断言" value="assert" />
        </el-select>
      </el-form-item>

      <el-form-item label="元素定位" prop="config.selector">
        <el-input v-model="step.config.selector" placeholder="请输入元素选择器" />
      </el-form-item>

      <el-form-item label="输入值" v-if="step.config.action === 'input'">
        <el-input v-model="step.config.value" placeholder="请输入要填写的值" />
      </el-form-item>
    </template>

    <!-- 数据库操作配置 -->
    <template v-if="step.type === 'db'">
      <el-form-item label="SQL语句" prop="config.sql">
        <el-input
          v-model="step.config.sql"
          type="textarea"
          :rows="4"
          placeholder="请输入SQL语句"
        />
      </el-form-item>
    </template>

    <!-- 自定义脚本配置 -->
    <template v-if="step.type === 'custom'">
      <el-form-item label="Python脚本" prop="config.script">
        <el-input
          v-model="step.config.script"
          type="textarea"
          :rows="6"
          placeholder="请输入Python脚本"
        />
      </el-form-item>
    </template>
  </div>
</template>

<script>
export default {
  name: 'StepConfig',
  props: {
    step: {
      type: Object,
      required: true
    }
  },
  methods: {
    addHeader() {
      if (!this.step.config.headers) {
        this.$set(this.step.config, 'headers', [])
      }
      this.step.config.headers.push({ key: '', value: '' })
    },
    removeHeader(index) {
      this.step.config.headers.splice(index, 1)
    },
    getStepData() {
      return new Promise((resolve) => {
        const stepData = {
          ...this.step,
          config: JSON.stringify(this.step.config)
        }
        resolve(stepData)
      })
    }
  }
}
</script>

<style scoped>
.header-item {
  display: flex;
  align-items: center;
  margin-bottom: 10px;
}
</style> 