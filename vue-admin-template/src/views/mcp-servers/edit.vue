<template>
  <div class="app-container" v-loading="loading">
    <el-form ref="form" :model="form" :rules="rules" label-width="140px">
      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="服务器名称" prop="name">
            <el-input v-model="form.name" placeholder="例如: tencent-docs" />
          </el-form-item>
        </el-col>
        <el-col :span="12">
          <el-form-item label="传输类型" prop="transport">
            <el-select v-model="form.transport" placeholder="请选择传输类型" style="width: 100%;">
              <el-option label="Stdio (本地子进程)" value="stdio" />
              <el-option label="HTTP" value="http" />
              <el-option label="SSE" value="sse" />
            </el-select>
          </el-form-item>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="12">
          <el-form-item label="启用状态">
            <el-switch v-model="form.enabled" active-color="#13ce66" inactive-color="#ff4949" />
          </el-form-item>
        </el-col>
      </el-row>

      <el-form-item label="描述">
        <el-input v-model="form.description" type="textarea" rows="2" placeholder="服务器用途描述（可选）" />
      </el-form-item>

      <template v-if="form.transport === 'stdio'">
        <el-form-item label="启动命令" prop="command">
          <el-input v-model="form.command" placeholder="例如: npx, python, /usr/local/bin/server" />
        </el-form-item>

        <el-form-item label="启动参数 (JSON)">
          <el-input
            v-model="argsText"
            type="textarea"
            rows="3"
            placeholder='例如: ["@playwright/mcp@latest"]'
            @blur="parseArgs"
          />
          <div class="form-tip">每行一个参数，或输入 JSON 数组格式</div>
        </el-form-item>

        <el-form-item label="环境变量 (JSON)">
          <el-input
            v-model="envText"
            type="textarea"
            rows="3"
            placeholder='例如: {"API_KEY": "xxx"}'
            @blur="parseEnv"
          />
        </el-form-item>
      </template>

      <template v-else>
        <el-form-item label="服务端点 URL" prop="url">
          <el-input v-model="form.url" placeholder="例如: https://docs.qq.com/openapi/mcp" />
        </el-form-item>

        <el-form-item label="请求头 (JSON)">
          <el-input
            v-model="headersText"
            type="textarea"
            rows="3"
            placeholder='例如: {"Authorization": "Bearer xxx"}'
            @blur="parseHeaders"
          />
          <div class="form-tip">HTTP/SSE 模式下的请求头，例如 Authorization</div>
        </el-form-item>
      </template>

      <el-form-item style="margin-top: 20px;">
        <el-button type="primary" @click="onSubmit" :loading="submitLoading">保存</el-button>
        <el-button @click="onCancel">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { getMCPServerDetail, updateMCPServer } from '@/api/mcp-server'

export default {
  name: 'MCPServerEdit',
  data() {
    return {
      loading: false,
      submitLoading: false,
      form: {
        name: '',
        description: '',
        transport: 'http',
        command: '',
        args: [],
        env: {},
        url: '',
        headers: {},
        enabled: true
      },
      argsText: '',
      envText: '',
      headersText: '',
      rules: {
        name: [
          { required: true, message: '请输入服务器名称', trigger: 'blur' },
          { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
        ],
        transport: [
          { required: true, message: '请选择传输类型', trigger: 'change' }
        ],
        command: [
          { required: true, message: '请输入启动命令（Stdio 模式必填）', trigger: 'blur' }
        ],
        url: [
          { required: true, message: '请输入服务端点 URL（HTTP/SSE 模式必填）', trigger: 'blur' }
        ]
      }
    }
  },
  created() {
    this.getDetail()
  },
  methods: {
    getDetail() {
      this.loading = true
      getMCPServerDetail(this.$route.params.id)
        .then(response => {
          if (response && response.data) {
            const d = response.data
            this.form = {
              name: d.name || '',
              description: d.description || '',
              transport: d.transport || 'stdio',
              command: d.command || '',
              args: d.args || [],
              env: d.env || {},
              url: d.url || '',
              headers: d.headers || {},
              enabled: d.enabled !== undefined ? d.enabled : true
            }
            this.argsText = JSON.stringify(this.form.args || [], null, 2)
            this.envText = JSON.stringify(this.form.env || {}, null, 2)
            this.headersText = JSON.stringify(this.form.headers || {}, null, 2)
          } else {
            this.$message.error('获取 MCP Server 详情失败：数据格式错误')
          }
        })
        .catch(error => {
          console.error('获取 MCP Server 详情失败:', error)
          this.$message.error(error.response?.data?.detail || error.message || '获取详情失败')
        })
        .finally(() => {
          this.loading = false
        })
    },
    parseArgs() {
      if (!this.argsText.trim()) {
        this.form.args = []
        return
      }
      try {
        const parsed = JSON.parse(this.argsText)
        this.form.args = Array.isArray(parsed) ? parsed : []
      } catch {
        const lines = this.argsText.split('\n').map(l => l.trim()).filter(Boolean)
        this.form.args = lines.length > 0 ? lines : []
      }
    },
    parseEnv() {
      if (!this.envText.trim()) {
        this.form.env = {}
        return
      }
      try {
        const parsed = JSON.parse(this.envText)
        this.form.env = typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
      } catch {
        this.form.env = {}
      }
    },
    parseHeaders() {
      if (!this.headersText.trim()) {
        this.form.headers = {}
        return
      }
      try {
        const parsed = JSON.parse(this.headersText)
        this.form.headers = typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {}
      } catch {
        this.form.headers = {}
      }
    },
    onSubmit() {
      this.$refs.form.validate(async valid => {
        if (!valid) return

        const loading = this.$loading({
          lock: true,
          text: '更新中...',
          spinner: 'el-icon-loading',
          background: 'rgba(0, 0, 0, 0.7)'
        })

        this.submitLoading = true
        try {
          this.parseArgs()
          this.parseEnv()
          this.parseHeaders()
          const payload = { ...this.form }
          if (payload.transport === 'stdio') {
            payload.url = null
            payload.headers = {}
          } else {
            payload.command = null
            payload.args = []
            payload.env = {}
          }

          const response = await updateMCPServer(this.$route.params.id, payload)
          if (response.code === '0') {
            this.$message({ message: '更新成功', type: 'success' })
            this.$router.push('/system/mcp-servers')
          } else {
            this.$message.error(response.msg || '更新失败')
          }
        } catch (error) {
          console.error('更新 MCP Server 失败:', error)
          this.$message.error(error.response?.data?.detail || error.message || '更新失败')
        } finally {
          loading.close()
          this.submitLoading = false
        }
      })
    },
    onCancel() {
      this.$router.push('/system/mcp-servers')
    }
  }
}
</script>

<style scoped>
.app-container {
  padding: 20px;
}
.form-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
  line-height: 1.4;
}
</style>
