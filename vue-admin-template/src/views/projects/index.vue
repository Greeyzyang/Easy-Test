<template>
  <div class="app-container">
    <div class="filter-container">
      <el-button
        class="filter-item"
        style="margin-left: 10px;"
        type="primary"
        icon="el-icon-plus"
        @click="handleCreate"
      >
        新建项目
      </el-button>
    </div>

    <el-table
      v-loading="listLoading"
      :data="list"
      element-loading-text="加载中..."
      border
      fit
      highlight-current-row
      style="width: 100%;"
    >
      <el-table-column label="项目名称" min-width="100">
        <template slot-scope="scope">
          <span class="link-type" @click="handleUpdate(scope.row)">{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="200">
        <template slot-scope="scope">
          <EllipsisCell :value="scope.row.description || '-'" :detect-json="false" />
        </template>
      </el-table-column>
      <el-table-column label="创建时间" width="160" align="center">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.created_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="更新时间" width="160" align="center">
        <template slot-scope="scope">
          <span>{{ formatDateTime(scope.row.updated_time) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="操作" align="center" min-width="230">
        <template slot-scope="scope">
          <el-button type="primary" size="mini" @click="handleUpdate(scope.row)">
            编辑
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
  </div>
</template>

<script>
import { getProjectList, deleteProject, createProject } from '@/api/project'
import { formatDateTime } from '@/utils/format'
import Pagination from '@/components/Layout/Pagination'
import EllipsisCell from '@/components/Common/EllipsisCell'

export default {
  name: 'ProjectList',
  components: { Pagination, EllipsisCell },
  data() {
    return {
      list: [],
      total: 0,
      listLoading: false,
      listQuery: {
        page: 1,
        limit: 10
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
        const response = await getProjectList(this.listQuery)
        // 后端返回 { code: '0', data: { items: [...], total: 100 } }
        if (response && response.code === '0' && response.data) {
          const { items, total } = response.data
          this.list = (items || []).map(item => ({
            id: item.id,
            name: item.name,
            description: item.description,
            created_time: item.created_time,
            updated_time: item.updated_time
          }))
          this.total = total || 0
        } else {
          this.$message.error('获取项目列表失败：数据格式错误')
        }
      } catch (error) {
        console.error('获取项目列表失败:', error)
        const errorMessage = error.response?.data?.detail || error.message || '获取项目列表失败'
        this.$message.error(errorMessage)
      } finally {
        this.listLoading = false
      }
    },
    handleCreate() {
      this.$router.push('/design/projects/create')
    },
    handleUpdate(row) {
      this.$router.push(`/design/projects/edit/${row.id}`)
    },
    async handleDelete(row) {
      try {
        await this.$confirm('此操作将永久删除该项目, 是否继续?', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await deleteProject(row.id)
        this.$message({
          type: 'success',
          message: '删除成功!'
        })
        if (this.list.length === 1 && this.listQuery.page > 1) {
          this.listQuery.page--
        }
        this.getList()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除项目失败:', error)
          const errorMessage = error.response?.data?.detail || error.message || '删除项目失败'
          this.$message.error(errorMessage)
        }
      }
    },
    async handleCopy(row) {
      try {
        const allProjectsResponse = await getProjectList({ limit: 1000 })
        if (allProjectsResponse && allProjectsResponse.code === '0' && Array.isArray(allProjectsResponse.data)) {
          const existingNames = allProjectsResponse.data.map(item => item.name)

          let newName = row.name
          let counter = 1
          while (existingNames.includes(newName + ` (${counter})`)) {
            counter++
          }
          newName = newName + ` (${counter})`

          const copyData = {
            ...row,
            name: newName,
            id: undefined,
            created_time: undefined,
            updated_time: undefined
          }

          await createProject(copyData)
          this.$message.success('复制成功')
          this.getList()
        } else {
          this.$message.error('获取项目列表用于复制校验失败')
        }
      } catch (error) {
        console.error('复制项目失败:', error)
        const errorMessage = error.response?.data?.detail || error.response?.data?.msg || error.message || '复制项目失败'
        this.$message.error(errorMessage)
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

.pagination-container {
  margin-top: 20px;
  text-align: right;
}
</style>
