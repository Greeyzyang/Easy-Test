<template>
  <div class="app-container">
    <div class="filter-container">
      <el-input
        v-model="listQuery.name"
        placeholder="接口名称/URL"
        style="width: 200px;"
        class="filter-item"
        @keyup.enter.native="handleFilter"
      />
      <el-select
        v-model="listQuery.moduleId"
        placeholder="所属模块"
        clearable
        style="width: 200px"
        class="filter-item"
      >
        <el-option
          v-for="item in moduleOptions"
          :key="item.id"
          :label="item.name"
          :value="item.id"
        />
      </el-select>
      <el-button
        v-waves
        class="filter-item"
        type="primary"
        icon="el-icon-search"
        @click="handleFilter"
      >
        搜索
      </el-button>
      <el-button
        class="filter-item"
        style="margin-left: 10px;"
        type="primary"
        icon="el-icon-plus"
        @click="handleCreate"
      >
        新建接口
      </el-button>
      <el-button
        class="filter-item"
        style="margin-left: 10px;"
        type="success"
        icon="el-icon-download"
        @click="handleImportSwagger"
      >
        导入 Swagger
      </el-button>
    </div>

    <el-table
      :key="tableKey"
      v-loading="listLoading"
      :data="list"
      border
      fit
      highlight-current-row
      style="width: 100%;"
    >
      <el-table-column label="接口名称">
        <template slot-scope="scope">
          <span class="link-type" @click="handleUpdate(scope.row)">{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="请求地址" min-width="300">
        <template slot-scope="scope">
          <el-tag :type="getMethodType(scope.row.method)" size="small" style="margin-right: 8px; width: 65px; text-align: center; font-weight: bold;">
            {{ scope.row.method }}
          </el-tag>
          <span style="color: #606266;">{{ scope.row.url }}</span>
        </template>
      </el-table-column>
      <el-table-column label="所属模块" align="center">
        <template slot-scope="scope">
          <span>{{ scope.row.module_name || '-' }}</span>
        </template>
      </el-table-column>
      <el-table-column label="版本" width="100" align="center">
        <template slot-scope="scope">
          <span>{{ scope.row.version }}</span>
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="180" align="center">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.created_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="180" align="center">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.updated_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" min-width="230">
        <template slot-scope="scope">
          <el-button type="primary" size="mini" @click="handleUpdate(scope.row)">
            编辑
          </el-button>
          <el-button type="warning" size="mini" @click="handleAiGenerate(scope.row)">
            AI生成
          </el-button>
          <el-button type="success" size="mini" @click="handleCopy(scope.row)">
            复制
          </el-button>
          <el-button type="danger" size="mini" @click="handleDelete(scope.row)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <pagination
      v-show="total>0"
      :total="total"
      :page.sync="listQuery.page"
      :limit.sync="listQuery.limit"
      @pagination="getList"
    />

    <!-- Swagger 导入弹窗 -->
    <el-dialog title="导入 Swagger 接口" :visible.sync="swaggerDialogVisible" width="500px">
      <el-form ref="swaggerForm" :model="swaggerForm" label-width="100px" :rules="swaggerRules">
        <el-form-item label="Swagger URL" prop="url">
          <el-input v-model="swaggerForm.url" placeholder="请输入 OpenAPI JSON 地址" />
        </el-form-item>
        <el-form-item label="所属项目" prop="projectId">
          <el-select v-model="swaggerForm.projectId" placeholder="请选择导入到的项目" style="width: 100%">
            <el-option
              v-for="item in projectOptions"
              :key="item.id"
              :label="item.name"
              :value="item.id"
            />
          </el-select>
          <div style="font-size: 12px; color: #909399; margin-top: 5px;">
            系统将根据 Swagger 中的 Tags 自动创建并归类模块
          </div>
        </el-form-item>
      </el-form>
      <div slot="footer" class="dialog-footer">
        <div v-if="importing" style="margin-bottom: 10px; text-align: left;">
          <el-progress :percentage="importProgress" :status="importStatus === 'FAILURE' ? 'exception' : (importStatus === 'SUCCESS' ? 'success' : null)" />
          <div style="font-size: 12px; color: #606266; margin-top: 5px;">{{ importMessage }}</div>
        </div>
        <el-button :disabled="importing && importStatus !== 'SUCCESS' && importStatus !== 'FAILURE'" @click="handleImportDialogClose">取消</el-button>
        <el-button type="primary" :loading="importing && importStatus !== 'SUCCESS' && importStatus !== 'FAILURE'" @click="confirmImportSwagger">
          {{ importing ? '导入中...' : '确定导入' }}
        </el-button>
      </div>
    </el-dialog>

    <!-- AI 生成用例弹窗 -->
    <el-dialog
      title="AI 生成测试用例"
      :visible.sync="aiDialogVisible"
      width="800px"
      :close-on-click-modal="false"
      @close="handleAiDialogClose"
    >
      <div v-if="aiGenerating" style="padding: 20px; text-align: center;">
        <el-progress type="circle" :percentage="aiProgress" :status="aiStatus === 'FAILURE' ? 'exception' : (aiStatus === 'SUCCESS' ? 'success' : null)" />
        <div style="margin-top: 20px; color: #606266; font-size: 16px; font-weight: 500;">{{ aiMessage }}</div>
        <div v-if="aiModelName" style="margin-top: 15px;">
          <el-tag type="info" size="medium" effect="plain">
            <i class="el-icon-cpu" style="margin-right: 5px;" />
            正在调用模型：<span style="color: #409EFF; font-weight: bold;">{{ aiModelName }}</span>
          </el-tag>
        </div>
      </div>

      <div v-else-if="generatedTestcases.length > 0">
        <el-table :data="generatedTestcases" border stripe style="width: 100%" max-height="400">
          <el-table-column type="expand">
            <template slot-scope="props">
              <el-form label-position="left" inline class="demo-table-expand">
                <el-form-item label="前置条件">
                  <span>{{ props.row.precondition || '无' }}</span>
                </el-form-item>
                <el-form-item label="测试步骤">
                  <div v-for="(step, index) in props.row.steps" :key="index">
                    {{ step }}
                  </div>
                </el-form-item>
                <el-form-item v-if="Object.keys(props.row.params || {}).length > 0" label="请求参数 (Params)">
                  <pre>{{ JSON.stringify(props.row.params, null, 2) }}</pre>
                </el-form-item>
                <el-form-item v-if="props.row.body" label="请求体 (Body)">
                  <pre>{{ JSON.stringify(props.row.body, null, 2) }}</pre>
                </el-form-item>
                <el-form-item v-if="(props.row.assertions || []).length > 0" label="验证配置 (Assertions)">
                  <div v-for="(assert, index) in props.row.assertions" :key="index">
                    {{ assert.type }}: {{ assert.expression || '' }} {{ assert.expected || assert.value }}
                  </div>
                </el-form-item>
              </el-form>
            </template>
          </el-table-column>
          <el-table-column width="55" align="center">
            <template slot-scope="scope">
              <el-checkbox v-model="scope.row.selected" />
            </template>
          </el-table-column>
          <el-table-column label="标题" min-width="150">
            <template slot-scope="scope">
              <EllipsisCell :value="scope.row.title" :detect-json="false" />
            </template>
          </el-table-column>
          <el-table-column label="优先级" prop="priority" width="80" align="center">
            <template slot-scope="scope">
              <el-tag :type="scope.row.priority === 'P0' ? 'danger' : 'info'" size="mini">
                {{ scope.row.priority }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column label="预期结果" min-width="200">
            <template slot-scope="scope">
              <EllipsisCell :value="scope.row.expected_result" :detect-json="false" />
            </template>
          </el-table-column>
        </el-table>
        <div style="margin-top: 15px; font-size: 13px; color: #909399;">
          * 请勾选需要保存的测试用例。AI 生成的用例仅供参考，请在保存后根据实际需求进行微调。
        </div>
      </div>

      <div v-else style="padding: 40px; text-align: center; color: #909399;">
        <i class="el-icon-warning-outline" style="font-size: 48px;" />
        <p style="margin-top: 15px;">{{ aiStatus === 'FAILURE' ? 'AI 生成失败' : '未生成任何有效的测试用例' }}</p>
        <el-button v-if="aiStatus === 'FAILURE'" type="text" @click="handleAiGenerate({id: currentInterfaceId})">重试</el-button>
      </div>

      <div slot="footer" class="dialog-footer">
        <el-button @click="aiDialogVisible = false">取 消</el-button>
        <el-button type="primary" :loading="savingGenerated" :disabled="aiGenerating || generatedTestcases.filter(t => t.selected).length === 0" @click="confirmSaveGenerated">
          保存选中的用例
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getInterfaceList, deleteInterface, importSwagger, getImportStatus } from '@/api/interface'
import { startInterfaceAiGenerationTask, saveGeneratedTestcases } from '@/api/testcase'
import { getModuleList } from '@/api/module'
import { getProjectList } from '@/api/project'
import waves from '@/directive/waves'
import Pagination from '@/components/Layout/Pagination'
import EllipsisCell from '@/components/Common/EllipsisCell'
import { formatDateTime } from '@/utils/format'

export default {
  name: 'InterfaceList',
  components: { Pagination, EllipsisCell },
  directives: { waves },
  data() {
    return {
      tableKey: 0,
      list: [],
      total: 0,
      listLoading: true,
      listQuery: {
        page: 1,
        limit: 20,
        name: undefined,
        moduleId: undefined
      },
      moduleOptions: [],
      projectOptions: [],
      executeDialogVisible: false,
      currentInterface: null,
      executeResult: null,
      executing: false,
      swaggerDialogVisible: false,
      importing: false,
      importProgress: 0,
      importStatus: '',
      importMessage: '',
      pollingTimer: null,
      swaggerForm: {
        url: '',
        projectId: undefined
      },
      swaggerRules: {
        url: [{ required: true, message: '请输入 Swagger URL', trigger: 'blur' }],
        projectId: [{ required: true, message: '请选择所属项目', trigger: 'change' }]
      },
      // AI 生成相关
      aiDialogVisible: false,
      aiGenerating: false,
      aiProgress: 0,
      aiStatus: '',
      aiMessage: '',
      aiModelName: '',
      generatedTestcases: [],
      savingGenerated: false,
      currentInterfaceId: null,
      ws: null,
      importWs: null
    }
  },
  computed: {
    safeSteps() {
      return Array.isArray(this.form.steps)
        ? this.form.steps.filter(step => !!step && typeof step === 'object')
        : []
    }
  },
  created() {
    this.getProjects()
    this.getModules()
    this.getList()
  },
  beforeDestroy() {
    if (this.pollingTimer) {
      clearInterval(this.pollingTimer)
      this.pollingTimer = null
    }
    this.closeWebSocket()
    this.closeImportWebSocket()
  },
  methods: {
    async getProjects() {
      try {
        const response = await getProjectList()
        if (response.code === '0' && response.data) {
          this.projectOptions = response.data.items || response.data
        }
      } catch (error) {
        console.error('获取项目列表失败:', error)
      }
    },
    getMethodType(method) {
      const typeMap = {
        GET: 'success',
        POST: 'primary',
        PUT: 'warning',
        DELETE: 'danger',
        PATCH: 'info'
      }
      return typeMap[method] || 'info'
    },
    async getModules() {
      try {
        const response = await getModuleList()
        if (response.code === '0' && response.data) {
          const items = response.data.items || response.data
          this.moduleOptions = items.map(module => ({
            id: module.id,
            name: module.name
          }))
        } else {
          throw new Error(response.message || '获取模块列表失败')
        }
      } catch (error) {
        console.error('获取模块列表失败:', error)
        this.$message.error(error.message || '获取模块列表失败，请稍后重试')
      }
    },
    async getList() {
      this.listLoading = true
      try {
        const response = await getInterfaceList(this.listQuery)
        if (response.code === '0') {
          const { items, total } = response.data
          this.list = items.map(item => ({
            ...item,
            module: {
              ...item.module,
              project: item.module?.project || null
            }
          }))
          this.total = total
        } else {
          throw new Error(response.message || '获取接口列表失败')
        }
      } catch (error) {
        console.error('获取接口列表失败:', error)
        this.$message.error(error.message || '获取接口列表失败，请稍后重试')
      } finally {
        this.listLoading = false
      }
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleCreate() {
      this.$router.push({ name: 'DesignInterfaceCreate' })
    },
    handleImportSwagger() {
      this.swaggerDialogVisible = true
      this.importing = false
      this.importProgress = 0
      this.importStatus = ''
      this.importMessage = ''
      if (this.pollingTimer) {
        clearInterval(this.pollingTimer)
        this.pollingTimer = null
      }
      this.$nextTick(() => {
        this.$refs.swaggerForm.resetFields()
      })
    },
    confirmImportSwagger() {
      this.$refs.swaggerForm.validate(async valid => {
        if (valid) {
          this.importing = true
          this.importProgress = 0
          this.importStatus = 'PENDING'
          this.importMessage = '正在启动导入任务...'
          try {
            const response = await importSwagger({
              url: this.swaggerForm.url,
              project_id: this.swaggerForm.projectId
            })
            if (response.code === '0' && response.data.task_id) {
              this.initImportWebSocket(response.data.task_id)
            } else {
              throw new Error(response.message || '启动导入任务失败')
            }
          } catch (error) {
            console.error('Swagger 导入启动失败:', error)
            this.$message.error(error.message || '启动导入失败，请检查 URL 是否正确且可访问')
            this.importing = false
          }
        }
      })
    },
    initImportWebSocket(taskId) {
      if (this.importWs) {
        this.importWs.close()
      }

      const baseApi = process.env.VUE_APP_BASE_API
      let wsHost
      if (baseApi.startsWith('http')) {
        wsHost = baseApi.replace(/^http/, 'ws')
      } else {
        wsHost = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host + baseApi
      }

      // 注意：这里需要确保后端有对应的 /ws/import/ 路由
      const wsUrl = `${wsHost}/rest/v1/interfaces/ws/import/${taskId}`
      console.log('Connecting to Import WebSocket:', wsUrl)

      this.importWs = new WebSocket(wsUrl)

      this.importWs.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('Import WebSocket message:', data)

          if (data.progress !== undefined) {
            this.importProgress = data.progress
          }
          if (data.text) {
            this.importMessage = data.text
          }
          if (data.status) {
            this.importStatus = data.status
          }

          if (data.status === 'SUCCESS') {
            this.importProgress = 100
            this.$message.success(data.text || '导入成功')
            setTimeout(() => {
              this.swaggerDialogVisible = false
              this.importing = false
              this.getModules()
              this.getList()
            }, 1500)
            this.closeImportWebSocket()
          } else if (data.status === 'FAILURE') {
            this.importing = false
            this.$message.error(data.text || '导入失败')
            this.closeImportWebSocket()
          }
        } catch (error) {
          console.error('解析 WebSocket 消息失败:', error)
        }
      }

      this.importWs.onerror = (error) => {
        console.error('Import WebSocket 错误:', error)
        this.pollImportStatus(taskId) // 如果 WS 失败，降级回轮询
      }

      this.importWs.onclose = () => {
        console.log('Import WebSocket closed')
      }
    },
    closeImportWebSocket() {
      if (this.importWs) {
        this.importWs.close()
        this.importWs = null
      }
    },
    handleImportDialogClose() {
      this.swaggerDialogVisible = false
      this.closeImportWebSocket()
      if (this.pollingTimer) {
        clearInterval(this.pollingTimer)
        this.pollingTimer = null
      }
    },
    async pollImportStatus(taskId) {
      this.pollingTimer = setInterval(async() => {
        try {
          const response = await getImportStatus(taskId)
          if (response.code === '0') {
            const { status, progress, result } = response.data
            this.importStatus = status

            if (status === 'PROGRESS' && progress) {
              this.importProgress = Math.round((progress.current / progress.total) * 100)
              this.importMessage = progress.status || '正在处理接口...'
            } else if (status === 'SUCCESS') {
              clearInterval(this.pollingTimer)
              this.pollingTimer = null
              this.importProgress = 100
              this.importMessage = result.message || '导入成功'
              this.$message.success(this.importMessage)
              // 延迟关闭弹窗
              setTimeout(() => {
                this.swaggerDialogVisible = false
                this.importing = false
                this.getModules()
                this.getList()
              }, 1500)
            } else if (status === 'FAILURE' || (result && result.status === 'error')) {
              clearInterval(this.pollingTimer)
              this.pollingTimer = null
              this.importStatus = 'FAILURE'
              this.importMessage = (result && result.message) || '导入失败'
              this.$message.error(this.importMessage)
              this.importing = false
            }
          }
        } catch (error) {
          console.error('查询导入状态失败:', error)
          clearInterval(this.pollingTimer)
          this.pollingTimer = null
          this.importing = false
        }
      }, 2000)
    },
    handleUpdate(row) {
      if (!row || !row.id) {
        this.$message.error('无法获取接口ID')
        return
      }
      console.log('跳转编辑接口, ID:', row.id)
      this.$router.push({
        name: 'DesignInterfaceEdit',
        params: { id: row.id }
      })
    },
    handleCopy(row) {
      const newInterface = { ...row }
      delete newInterface.id
      delete newInterface.created_time
      delete newInterface.updated_time
      newInterface.name = `${newInterface.name}-copy`
      this.$router.push({
        path: '/design/interfaces/create',
        query: { data: JSON.stringify(newInterface) }
      })
    },
    async handleDelete(row) {
      try {
        await this.$confirm('此操作将永久删除该接口，是否继续？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })

        const response = await deleteInterface(row.id)
        if (response.code === '0') {
          this.$message({
            type: 'success',
            message: '删除成功!'
          })
          this.getList()
        } else {
          throw new Error(response.message || '删除接口失败')
        }
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除接口失败:', error)
          this.$message.error(error.message || '删除接口失败，请稍后重试')
        }
      }
    },
    formatDateTime,
    // AI 生成相关方法
    async handleAiGenerate(row) {
      this.currentInterfaceId = row.id
      this.aiDialogVisible = true
      this.aiGenerating = true
      this.aiProgress = 0
      this.aiStatus = 'PENDING'
      this.aiMessage = '正在准备 AI 生成任务...'
      this.aiModelName = ''
      this.generatedTestcases = []

      try {
        const response = await startInterfaceAiGenerationTask({ interface_id: row.id })
        if (response.code === '0' && response.data.task_id) {
          this.initWebSocket(response.data.task_id)
        } else {
          throw new Error(response.message || '启动 AI 生成任务失败')
        }
      } catch (error) {
        console.error('AI 生成启动失败:', error)
        this.$message.error(error.message || '启动 AI 生成失败')
        this.aiGenerating = false
      }
    },
    initWebSocket(taskId) {
      if (this.ws) {
        this.ws.close()
      }

      const baseApi = process.env.VUE_APP_BASE_API
      let wsHost
      if (baseApi.startsWith('http')) {
        wsHost = baseApi.replace(/^http/, 'ws')
      } else {
        wsHost = (window.location.protocol === 'https:' ? 'wss://' : 'ws://') + window.location.host + baseApi
      }

      const wsUrl = `${wsHost}/rest/v1/testcases/ws/progress/${taskId}`
      console.log('Connecting to WebSocket:', wsUrl)

      this.ws = new WebSocket(wsUrl)

      this.ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          console.log('WebSocket message:', data)

          if (data.progress !== undefined) {
            this.aiProgress = data.progress
          }
          if (data.text) {
            this.aiMessage = data.text
          }
          if (data.status) {
            this.aiStatus = data.status
          }
          if (data.model_name) {
            this.aiModelName = data.model_name
          }

          if (data.status === 'SUCCESS') {
            this.aiGenerating = false
            if (data.result) {
              // 解析 AI 生成的结果
              this.generatedTestcases = this.parseAiResult(data.result)
            }
            this.closeWebSocket()
          } else if (data.status === 'FAILURE') {
            this.aiGenerating = false
            this.$message.error(data.text || 'AI 生成失败')
            this.closeWebSocket()
          }
        } catch (error) {
          console.error('解析 WebSocket 消息失败:', error)
        }
      }

      this.ws.onerror = (error) => {
        console.error('WebSocket 错误:', error)
        this.aiMessage = '连接进度服务失败，尝试轮询...'
      }

      this.ws.onclose = () => {
        console.log('WebSocket connection closed')
      }
    },
    closeWebSocket() {
      if (this.ws) {
        this.ws.close()
        this.ws = null
      }
    },
    handleAiDialogClose() {
      this.closeWebSocket()
      this.aiGenerating = false
    },
    parseAiResult(result) {
      // 兼容字符串和对象格式
      let cases = []
      try {
        if (typeof result === 'string') {
          cases = JSON.parse(result)
        } else if (Array.isArray(result)) {
          cases = result
        } else if (result && typeof result === 'object' && result.testcases) {
          cases = result.testcases
        }
      } catch (e) {
        console.error('解析 AI 结果失败:', e)
      }

      return cases.map(c => ({
        ...c,
        selected: true // 默认全选
      }))
    },
    async confirmSaveGenerated() {
      const selectedTestcases = this.generatedTestcases.filter(tc => tc.selected)
      if (selectedTestcases.length === 0) {
        this.$message.warning('请至少勾选一个用例')
        return
      }

      this.savingGenerated = true
      try {
        const response = await saveGeneratedTestcases({
          interface_id: this.currentInterfaceId,
          testcases: selectedTestcases
        })
        if (response.code === '0') {
          this.$message.success(response.data.message || '保存成功')
          this.aiDialogVisible = false
        } else {
          throw new Error(response.message || '保存失败')
        }
      } catch (error) {
        console.error('保存 AI 用例失败:', error)
        this.$message.error(error.message || '保存失败')
      } finally {
        this.savingGenerated = false
      }
    }
  }
}
</script>

<style lang="scss" scoped>
.app-container {
  padding: 20px;
  background: #fff;
}

.filter-container {
  padding-bottom: 10px;
  .filter-item {
    display: inline-block;
    vertical-align: middle;
    margin-bottom: 10px;
    margin-right: 10px;
  }
}

.link-type {
  color: #409EFF;
  cursor: pointer;
  &:hover {
    color: #66b1ff;
  }
}

.demo-table-expand {
  font-size: 0;
}
.demo-table-expand label {
  width: 90px;
  color: #99a9bf;
}
.demo-table-expand .el-form-item {
  margin-right: 0;
  margin-bottom: 0;
  width: 100%;
}
.demo-table-expand pre {
  margin: 0;
  background: #f5f7fa;
  padding: 5px;
  border-radius: 4px;
}
</style>
