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
        新建 MCP Server
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
      <el-table-column label="名称" min-width="120">
        <template slot-scope="scope">
          <span class="link-type" @click="handleUpdate(scope.row)">{{ scope.row.name }}</span>
        </template>
      </el-table-column>
      <el-table-column label="描述" min-width="180">
        <template slot-scope="scope">
          <EllipsisCell :value="scope.row.description || '-'" :detect-json="false" />
        </template>
      </el-table-column>
      <el-table-column label="传输类型" width="120" align="center">
        <template slot-scope="scope">
          <el-tag :type="scope.row.transport === 'stdio' ? 'success' : 'primary'" size="small">
            {{ scope.row.transport.toUpperCase() }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="命令 / URL" min-width="200">
        <template slot-scope="scope">
          <EllipsisCell :value="scope.row.command || scope.row.url || '-'" :detect-json="false" />
        </template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template slot-scope="scope">
          <el-switch
            v-model="scope.row.enabled"
            active-color="#13ce66"
            inactive-color="#ff4949"
            @change="handleToggle(scope.row)"
          />
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
      <el-table-column label="操作" align="center" min-width="150">
        <template slot-scope="scope">
          <el-button type="primary" size="mini" @click="handleUpdate(scope.row)">
            编辑
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
import { getMCPServerList, deleteMCPServer, toggleMCPServer } from '@/api/mcp-server'
import { formatDateTime } from '@/utils/format'
import Pagination from '@/components/Layout/Pagination'
import EllipsisCell from '@/components/Common/EllipsisCell'

export default {
  name: 'MCPServerList',
  components: { Pagination, EllipsisCell },
  data() {
    return {
      list: [],
      total: 0,
      listLoading: false,
      listQuery: {
        page: 1,
        limit: 10,
        name: ''
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
        const response = await getMCPServerList(this.listQuery)
        if (response && response.code === '0' && response.data) {
          const { items, total } = response.data
          this.list = (items || []).map(item => ({
            id: item.id,
            name: item.name,
            description: item.description,
            transport: item.transport,
            command: item.command,
            url: item.url,
            args: item.args,
            env: item.env,
            enabled: item.enabled,
            created_time: item.created_time,
            updated_time: item.updated_time
          }))
          this.total = total || 0
        } else {
          this.$message.error('获取 MCP Server 列表失败：数据格式错误')
        }
      } catch (error) {
        console.error('获取 MCP Server 列表失败:', error)
        const errorMessage = error.response?.data?.detail || error.message || '获取 MCP Server 列表失败'
        this.$message.error(errorMessage)
      } finally {
        this.listLoading = false
      }
    },
    handleCreate() {
      this.$router.push('/system/mcp-servers/create')
    },
    handleUpdate(row) {
      this.$router.push(`/system/mcp-servers/edit/${row.id}`)
    },
    async handleDelete(row) {
      try {
        await this.$confirm('此操作将永久删除该 MCP Server, 是否继续?', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await deleteMCPServer(row.id)
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
          console.error('删除 MCP Server 失败:', error)
          const errorMessage = error.response?.data?.detail || error.message || '删除失败'
          this.$message.error(errorMessage)
        }
      }
    },
    async handleToggle(row) {
      try {
        await toggleMCPServer(row.id)
        this.$message({
          type: 'success',
          message: row.enabled ? '已启用' : '已禁用'
        })
      } catch (error) {
        console.error('切换 MCP Server 状态失败:', error)
        row.enabled = !row.enabled
        const errorMessage = error.response?.data?.detail || error.message || '切换状态失败'
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
