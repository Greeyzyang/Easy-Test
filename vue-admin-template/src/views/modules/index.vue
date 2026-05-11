<template>
  <div class="app-container">
    <div class="filter-container">
      <el-input
        v-model="listQuery.name"
        placeholder="模块名称"
        style="width: 200px;"
        class="filter-item"
        @keyup.enter.native="handleFilter"
      />
      <el-select v-model="listQuery.project_id" placeholder="所属项目" clearable style="width: 200px" class="filter-item">
        <el-option v-for="item in projectOptions" :key="item.id" :label="item.name" :value="item.id" />
      </el-select>
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
        新建模块
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
      <el-table-column label="模块名称" min-width="150">
        <template slot-scope="scope">
          <span class="link-type" @click="handleUpdate(scope.row)">{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="所属项目" min-width="150">
        <template slot-scope="scope">
          <span>{{ scope.row.project ? scope.row.project.name : '-' }}</span>
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
import { getModuleList, deleteModule, createModule } from '@/api/module'
import { getProjectList } from '@/api/project'
import { formatDateTime } from '@/utils/format'
import Pagination from '@/components/Layout/Pagination'
import EllipsisCell from '@/components/Common/EllipsisCell'

export default {
  name: 'ModuleList',
  components: {
    Pagination,
    EllipsisCell
  },
  data() {
    return {
      list: [],
      total: 0,
      listLoading: false,
      projectOptions: [],
      listQuery: {
        page: 1,
        limit: 10,
        name: undefined,
        project_id: undefined
      }
    }
  },
  created() {
    this.getProjects().then(() => {
      this.getList()
    })
  },
  methods: {
    async getList() {
      this.listLoading = true
      try {
        const response = await getModuleList(this.listQuery)

        // 后端返回 { code: '0', data: { items: [...], total: 100 } }
        if (response && response.code === '0' && response.data) {
          const { items, total } = response.data
          this.list = (items || []).map(item => {
            const project = this.projectOptions.find(p => p.id === item.project_id)
            return {
              ...item,
              project: project || null,
              created_time: item.created_time ? new Date(item.created_time).toLocaleString() : '-',
              updated_time: item.updated_time ? new Date(item.updated_time).toLocaleString() : '-'
            }
          })
          this.total = total || 0
        } else {
          console.error('Unexpected response format:', response)
          this.$message.error('获取模块列表失败：数据格式错误')
        }
      } catch (error) {
        console.error('获取模块列表失败:', error)
        const errorMessage = error.response?.data?.msg || error.message || '获取模块列表失败'
        this.$message.error(errorMessage)
      } finally {
        this.listLoading = false
      }
    },
    async getProjects() {
      try {
        const response = await getProjectList({ limit: 100 })
        if (response && response.code === '0' && response.data) {
          const items = response.data.items || response.data
          this.projectOptions = items.map(item => ({
            id: item.id,
            name: item.name,
            description: item.description || '-'
          }))
        } else {
          console.error('Unexpected response format:', response)
          this.$message.error('获取项目列表失败：数据格式错误')
        }
      } catch (error) {
        console.error('获取项目列表失败:', error)
        const errorMessage = error.response?.data?.msg || error.message || '获取项目列表失败'
        this.$message.error(errorMessage)
      }
    },
    handleFilter() {
      this.listQuery.page = 1
      this.getList()
    },
    handleCreate() {
      this.$router.push('/design/modules/create')
    },
    handleUpdate(row) {
      this.$router.push(`/design/modules/edit/${row.id}`)
    },
    async handleDelete(row) {
      try {
        await this.$confirm('此操作将永久删除该模块, 是否继续?', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await deleteModule(row.id)
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
          console.error('删除模块失败:', error)
          const errorMessage = error.response?.data?.detail || error.message || '删除模块失败'
          this.$message.error(errorMessage)
        }
      }
    },
    async handleCopy(row) {
      try {
        // 获取所有模块名称
        const allModules = await getModuleList({ limit: 1000 })
        const existingNames = allModules.data.map(item => item.name)

        // 生成新名称
        let newName = row.name
        let counter = 1
        while (existingNames.includes(newName + ` (${counter})`)) {
          counter++
        }
        newName = newName + ` (${counter})`

        // 复制数据，修改名称
        const copyData = {
          ...row,
          name: newName,
          id: undefined,
          created_time: undefined,
          updated_time: undefined
        }

        // 创建新的模块
        await createModule(copyData)
        this.$message.success('复制成功')
        this.getList()
      } catch (error) {
        console.error('复制模块失败:', error)
        this.$message.error(error.response?.data?.msg || '复制模块失败')
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
