<template>
  <div>
    <el-dialog title="运行配置" :visible.sync="visible" width="50%" :before-close="handleClose">
      <el-form :model="runForm" label-width="120px">
        <el-form-item label="入口函数名">
          <el-input v-model="runForm.entry_name" placeholder="例如: add" />
        </el-form-item>
        <el-form-item label="参数（按顺序）"></el-form-item>
        <el-form-item v-for="(p, idx) in runForm.parameters" :key="idx" :label="`参数${idx+1}`">
          <el-input v-model="p.value" placeholder="请输入参数">
            <template slot="append">
              <el-button type="text" @click="removeParam(idx)">删除</el-button>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item label=" ">
          <el-button type="primary" plain size="mini" icon="el-icon-plus" @click="addParam">添加参数</el-button>
        </el-form-item>
      </el-form>
      <div slot="footer" class="dialog-footer">
        <el-button @click="handleClose">取消</el-button>
        <el-button type="primary" @click="submitRun" :loading="loading">执行</el-button>
      </div>
    </el-dialog>

    <el-dialog title="运行结果" :visible.sync="resultVisible" width="70%">
      <div v-if="runResult">
        <el-alert
          :title="runResult.success ? '执行成功' : '执行失败'"
          :type="runResult.success ? 'success' : 'error'"
          :closable="false"
          show-icon
        />
        <div class="run-result-content">
          <div v-if="runResult.stdout" class="result-section">
            <h4>标准输出：</h4>
            <pre>{{ runResult.stdout }}</pre>
          </div>
          <div v-if="runResult.stderr" class="result-section">
            <h4>标准错误：</h4>
            <pre>{{ runResult.stderr }}</pre>
          </div>
          <div v-if="runResult.error" class="result-section">
            <h4>错误信息：</h4>
            <pre>{{ runResult.error }}</pre>
          </div>
          <div v-if="runResult.result !== undefined" class="result-section">
            <h4>返回值：</h4>
            <pre>{{ JSON.stringify(runResult.result, null, 2) }}</pre>
          </div>
        </div>
      </div>
      <div slot="footer" class="dialog-footer">
        <el-button @click="resultVisible = false">
          关闭
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { runFunction } from '@/api/function'

export default {
  name: 'RunFunctionDialog',
  props: {
    visible: {
      type: Boolean,
      default: false
    },
    code: {
      type: String,
      default: ''
    }
  },
  data() {
    return {
      loading: false,
      runForm: {
        entry_name: '',
        parameters: []
      },
      resultVisible: false,
      runResult: null
    }
  },
  watch: {
    visible(val) {
      if (val) {
        this.initForm()
      }
    }
  },
  methods: {
    initForm() {
      // 尝试从代码中提取入口函数名
      const m = (this.code || '').match(/def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/)
      this.runForm.entry_name = m ? m[1] : ''
      // 预估参数个数并预填空值
      let paramsCount = 0
      try {
        const sig = (this.code || '').match(/def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(([^)]*)\)/)
        if (sig && sig[1]) {
          paramsCount = sig[1]
            .split(',')
            .map(s => s.trim())
            .filter(s => s && !s.startsWith('*'))
            .length
        }
      } catch (e) {}
      this.runForm.parameters = Array.from({ length: paramsCount }, () => ({ value: '' }))
    },
    handleClose() {
      this.$emit('update:visible', false)
    },
    addParam() {
      this.runForm.parameters.push({ value: '' })
    },
    removeParam(idx) {
      this.runForm.parameters.splice(idx, 1)
    },
    async submitRun() {
      this.loading = true
      const payload = {}
      const params = (this.runForm.parameters || []).map(p => String(p.value))
      payload.code = this.code
      if (this.runForm.entry_name) payload.entry_name = this.runForm.entry_name
      payload.parameters = params
      
      try {
        const response = await runFunction(payload)
        this.runResult = response.data
        this.handleClose()
        this.resultVisible = true
      } catch (e) {
        this.$message.error(e.message || '执行失败')
      } finally {
        this.loading = false
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.run-result-content {
  margin-top: 20px;
  padding: 15px;
  background-color: #f8f8f8;
  border-radius: 4px;

  .result-section {
    margin-bottom: 15px;

    h4 {
      margin: 0 0 10px 0;
      color: #606266;
    }
    
    pre {
      white-space: pre-wrap;
      word-wrap: break-word;
      background: #333;
      color: #eee;
      padding: 10px;
      border-radius: 4px;
    }
  }
}
</style>
