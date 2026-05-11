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

    <run-function-dialog
      v-if="runTargetRow"
      :visible.sync="runConfigDialogVisible"
      :code="runTargetRow.code"
    />
  </div>
</template>

<script>
import { getFunctionList, deleteFunction } from '@/api/function'
import waves from '@/directive/waves'
import Pagination from '@/components/Layout/Pagination'
import { formatDateTime } from '@/utils/format'
import RunFunctionDialog from './components/RunFunctionDialog'

export default {
  name: 'Functions',
  components: { 
    Pagination,
    RunFunctionDialog
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
      runTargetRow: null
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
          const { items, total } = response.data
          this.list = items || []
          this.total = total || 0
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
      this.$router.push('/design/functions/create')
    },
    handleUpdate(row) {
      this.$router.push(`/design/functions/edit/${row.id}`)
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
      this.runConfigDialogVisible = true
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
</style> 
