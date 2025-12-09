<template>
  <div class="app-container">
    <div class="filter-container">
      <el-input
        v-model="listQuery.name"
        placeholder="函数名称"
        style="width: 200px;"
        class="filter-item"
        @keyup.enter.native="handleFilter"
      />
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
        新建函数
      </el-button>
    </div>

    <el-table
      v-loading="listLoading"
      :data="list"
      element-loading-text="Loading"
      border
      fit
      highlight-current-row
    >
      <el-table-column label="函数名称">
        <template slot-scope="scope">
          <span class="link-type" @click="handleUpdate(scope.row)">{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="描述">
        <template slot-scope="scope">
          {{ scope.row.description }}
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
      <el-table-column label="操作" align="center" width="300" class-name="small-padding fixed-width">
        <template slot-scope="{row}">
          <el-button type="primary" size="mini" @click="handleUpdate(row)">
            编辑
          </el-button>
          <el-button size="mini" type="success" @click="openRunConfig(row)">
            运行
          </el-button>
          <el-button size="mini" type="danger" @click="handleDelete(row)">
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

    <el-dialog title="运行配置" :visible.sync="runConfigDialogVisible" width="50%">
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
        <el-button @click="runConfigDialogVisible=false">取消</el-button>
        <el-button type="primary" @click="submitRun">执行</el-button>
      </div>
    </el-dialog>

    <el-dialog title="运行结果" :visible.sync="runDialogVisible" width="70%">
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
        <el-button @click="runDialogVisible = false">
          关闭
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getFunctionList, deleteFunction, runFunction } from '@/api/function'
import waves from '@/directive/waves'
import Pagination from '@/components/Pagination'
import { formatDateTime } from '@/utils/format'

export default {
  name: 'Functions',
  components: { 
    Pagination
  },
  directives: { waves },
  data() {
    return {
      list: null,
      total: 0,
      listLoading: true,
      listQuery: {
        page: 1,
        limit: 20,
        name: undefined
      },
      runConfigDialogVisible: false,
      runForm: {
        entry_name: '',
        parameters: []
      },
      runTargetRow: null,
      runDialogVisible: false,
      runResult: null
    }
  },
  created() {
    this.getList()
  },
  methods: {
    getList() {
      this.listLoading = true
      getFunctionList(this.listQuery).then(response => {
        if (response.code === '0' && response.data) {
          this.list = response.data
          this.total = response.data.length
        } else {
          this.list = []
          this.total = 0
          this.$message.error(response.msg || '获取函数列表失败')
        }
        this.listLoading = false
      }).catch(error => {
        console.error('获取函数列表失败:', error)
        this.listLoading = false
        this.$message.error(error.message || '获取函数列表失败')
      })
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleCreate() {
      this.$router.push('/functions/create')
    },
    handleUpdate(row) {
      this.$router.push(`/functions/edit/${row.id}`)
    },
    handleDelete(row) {
      this.$confirm('确认删除该函数?', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        deleteFunction(row.id).then(() => {
          const index = this.list.findIndex(v => v.id === row.id)
          this.list.splice(index, 1)
          this.$notify({
            title: '成功',
            message: '删除成功',
            type: 'success',
            duration: 2000
          })
        })
      })
    },
    openRunConfig(row) {
      this.runTargetRow = row
      // 尝试从代码中提取入口函数名
      const m = (row.code || '').match(/def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(/)
      this.runForm.entry_name = m ? m[1] : ''
      // 预估参数个数并预填空值
      let paramsCount = 0
      try {
        const sig = (row.code || '').match(/def\s+[A-Za-z_][A-Za-z0-9_]*\s*\(([^)]*)\)/)
        if (sig && sig[1]) {
          paramsCount = sig[1]
            .split(',')
            .map(s => s.trim())
            .filter(s => s && !s.startsWith('*'))
            .length
        }
      } catch (e) {}
      this.runForm.parameters = Array.from({ length: paramsCount }, () => ({ value: '' }))
      this.runConfigDialogVisible = true
    },
    addParam() {
      this.runForm.parameters.push({ value: '' })
    },
    removeParam(idx) {
      this.runForm.parameters.splice(idx, 1)
    },
    async submitRun() {
      const payload = {}
      const params = (this.runForm.parameters || []).map(p => String(p.value))
      payload.code = this.runTargetRow.code
      if (this.runForm.entry_name) payload.entry_name = this.runForm.entry_name
      payload.parameters = params
      try {
        const response = await runFunction(payload)
        this.runResult = response.data
        this.runConfigDialogVisible = false
        this.runDialogVisible = true
      } catch (e) {
        this.$message.error(e.message || '执行失败')
      }
    },
    formatDateTime
  }
}
</script>

<style lang="scss" scoped>
.app-container {
  padding: 20px;
  background: #fff;
}

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
      margin: 0;
      padding: 10px;
      background-color: #fff;
      border: 1px solid #dcdfe6;
      border-radius: 4px;
      white-space: pre-wrap;
      word-wrap: break-word;
    }
  }
}

.link-type {
  color: #409EFF;
  cursor: pointer;
  
  &:hover {
    color: #66b1ff;
  }
}
</style> 
