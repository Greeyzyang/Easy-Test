<template>
  <div class="variable-extract-config">
    <el-form-item label="变量名称">
      <el-input v-model="variableName" placeholder="请输入变量名称" />
    </el-form-item>

    <el-form-item label="数据来源">
      <el-select v-model="source" placeholder="请选择数据来源">
        <el-option label="响应体" value="response" />
        <el-option label="响应头" value="headers" />
        <el-option label="Cookie" value="cookies" />
      </el-select>
    </el-form-item>

    <el-form-item :label="source === 'response' ? 'JSONPath表达式' : '键名'">
      <el-input 
        v-model="path" 
        :placeholder="getPathPlaceholder"
      >
        <template v-if="source === 'response'" slot="append">
          <el-tooltip content="JSONPath语法帮助" placement="top">
            <el-button icon="el-icon-question" @click="showJsonPathHelp" />
          </el-tooltip>
        </template>
      </el-input>
    </el-form-item>

    <!-- JSONPath帮助对话框 -->
    <el-dialog
      title="JSONPath语法帮助"
      :visible.sync="jsonPathHelpVisible"
      width="600px"
    >
      <div class="jsonpath-help">
        <h4>常用语法示例：</h4>
        <ul>
          <li><code>$.data</code> - 获取data字段的值</li>
          <li><code>$.data.list[0]</code> - 获取data.list数组的第一个元素</li>
          <li><code>$.data.list[*].id</code> - 获取data.list数组中所有元素的id字段</li>
          <li><code>$.data.list[?(@.type=='test')]</code> - 获取data.list数组中type为test的元素</li>
        </ul>
      </div>
    </el-dialog>
  </div>
</template>

<script>
export default {
  name: 'VariableExtractConfig',
  props: {
    value: {
      type: Object,
      default: () => ({})
    }
  },
  data() {
    return {
      variableName: '',
      source: 'response',
      path: '',
      jsonPathHelpVisible: false
    }
  },
  computed: {
    getPathPlaceholder() {
      return this.source === 'response'
        ? '示例: $.data.list[0].id'
        : '请输入键名'
    },
    extractConfig() {
      return {
        [this.variableName]: this.source === 'response'
          ? this.path // 如果是response，直接使用path作为jsonpath
          : { // 否则使用对象格式
            source: this.source,
            path: this.path
          }
      }
    }
  },
  watch: {
    value: {
      handler(newVal) {
        if (newVal) {
          const [variableName, config] = Object.entries(newVal)[0] || []
          this.variableName = variableName || ''
          if (typeof config === 'string') {
            this.source = 'response'
            this.path = config
          } else {
            this.source = config?.source || 'response'
            this.path = config?.path || ''
          }
        }
      },
      immediate: true
    },
    extractConfig: {
      handler(newVal) {
        this.$emit('input', newVal)
      },
      deep: true
    }
  },
  methods: {
    showJsonPathHelp() {
      this.jsonPathHelpVisible = true
    }
  }
}
</script>

<style scoped>
.variable-extract-config {
  margin-bottom: 20px;
}
.jsonpath-help {
  font-size: 14px;
}
.jsonpath-help code {
  background: #f5f7fa;
  padding: 2px 4px;
  border-radius: 3px;
}
</style>