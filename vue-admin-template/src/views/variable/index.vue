<template>
  <div class="app-container">
    <!-- 搜索和操作栏 -->
    <div class="filter-container">
      <el-input
        v-model="listQuery.key"
        placeholder="变量名"
        style="width: 200px;"
        class="filter-item"
        @keyup.enter.native="handleFilter"
      />
      <el-button class="filter-item" type="primary" icon="el-icon-search" @click="handleFilter">
        搜索
      </el-button>
      <el-button
        class="filter-item"
        style="margin-left: 10px;"
        type="primary"
        icon="el-icon-plus"
        @click="handleCreate"
      >
        新建变量
      </el-button>
    </div>

    <!-- 变量表格 -->
    <el-table
      v-loading="listLoading"
      :data="list"
      element-loading-text="加载中..."
      border
      fit
      highlight-current-row
      style="width: 100%;"
    >
      <el-table-column prop="key" label="变量名" min-width="150" />
      <el-table-column prop="value" label="变量值" min-width="200">
        <template slot-scope="{row}">
          <EllipsisCell :value="row.value" />
        </template>
      </el-table-column>
      <el-table-column prop="description" label="描述" />
      <el-table-column prop="created_time" label="创建时间" width="160" align="center">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.created_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="updated_time" label="更新时间" width="160" align="center">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.updated_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="180" align="center">
        <template slot-scope="scope">
          <el-button type="primary" size="mini" @click="handleEdit(scope.row)">编辑</el-button>
          <el-button size="mini" type="danger" @click="handleDelete(scope.row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页组件 -->
    <pagination
      v-show="total>0"
      :total="total"
      :page.sync="listQuery.page"
      :limit.sync="listQuery.limit"
      @pagination="getList"
    />
  </div>
</template>

<script>
import { getList, deleteVariable } from '@/api/variable'
import Pagination from '@/components/Layout/Pagination'
import EllipsisCell from '@/components/Common/EllipsisCell'

export default {
  name: 'VariableIndex',
  components: { Pagination, EllipsisCell },
  data() {
    return {
      list: [],
      total: 0,
      listLoading: false,
      listQuery: {
        page: 1,
        limit: 10,
        key: undefined
      }
    }
  },
  created() {
    this.getList()
  },
  methods: {
    async getList() {
      this.listLoading = true
      try {
        const response = await getList(this.listQuery)
        // 后端返回 { code: '0', data: { items: [...], total: 100 } }
        if (response && response.code === '0' && response.data) {
          this.list = response.data.items || []
          this.total = response.data.total || 0
        } else {
          this.$message.error('获取变量列表失败：数据格式错误')
        }
      } catch (error) {
        this.$message.error(error.response?.data?.msg || error.message || '获取变量列表失败')
      } finally {
        this.listLoading = false
      }
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleCreate() {
      this.$router.push({ path: '/design/variables/create' })
    },
    handleEdit(row) {
      this.$router.push({ path: '/design/variables/edit', query: { id: row.id }})
    },
    async handleDelete(row) {
      try {
        await this.$confirm('确定要删除该变量吗？', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await deleteVariable(row.id)
        this.$message.success('删除成功')
        if (this.list.length === 1 && this.listQuery.page > 1) {
          this.listQuery.page--
        }
        this.getList()
      } catch (error) {
        if (error !== 'cancel') {
          this.$message.error(error.response?.data?.msg || error.message || '删除失败')
        }
      }
    },
    formatDateTime(val) {
      if (!val) return '-'
      const date = new Date(val)
      return date.toLocaleString()
    }
  }
}
</script>

<style scoped>
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
</style>
