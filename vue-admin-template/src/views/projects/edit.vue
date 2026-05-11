<template>
  <div class="app-container">
    <el-form ref="form" :model="form" :rules="rules" label-width="120px" v-loading="loading">
      <el-form-item label="项目名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入项目名称" />
      </el-form-item>
      <el-form-item label="项目描述" prop="description">
        <el-input v-model="form.description" type="textarea" rows="4" placeholder="请输入项目描述" />
      </el-form-item>

      <el-form-item style="margin-top: 20px;">
        <el-button type="primary" @click="onSubmit" :loading="submitLoading">保存</el-button>
        <el-button @click="onCancel">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { getProjectDetail, updateProject } from '@/api/project'

export default {
  name: 'ProjectEdit',
  data() {
    return {
      loading: false,
      submitLoading: false,
      form: {
        name: '',
        description: '',
        headers: {},
        variables: {}
      },
      rules: {
        name: [
          { required: true, message: '请输入项目名称', trigger: 'blur' },
          { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
        ],
        description: [
          { required: true, message: '请输入项目描述', trigger: 'blur' },
          { max: 500, message: '描述不能超过500个字符', trigger: 'blur' }
        ]
      }
    }
  },
  created() {
    this.getProject()
  },
  methods: {
    getProject() {
      this.loading = true
      getProjectDetail(this.$route.params.id)
        .then(response => {
          console.log('获取项目详情响应:', response)
          if (response && response.data) {
            const data = response.data
            this.form = {
              name: data.name || '',
              description: data.description || '',
              headers: data.headers || {},
              variables: data.variables || {}
            }
          } else {
            this.$message.error('获取项目详情失败：数据格式错误')
          }
        })
        .catch(error => {
          console.error('获取项目详情失败:', error)
          this.$message.error(error.response?.data?.detail || error.message || '获取项目详情失败')
        })
        .finally(() => {
          this.loading = false
        })
    },
    onSubmit() {
      this.$refs.form.validate(valid => {
        if (!valid) {
          return false
        }

        const loading = this.$loading({
          lock: true,
          text: '更新中...',
          spinner: 'el-icon-loading',
          background: 'rgba(0, 0, 0, 0.7)'
        })

        this.submitLoading = true
        updateProject(this.$route.params.id, this.form)
          .then(response => {
            console.log('更新项目响应:', response)
            if (response.code === '0') {
              this.$message({
                message: '更新成功',
                type: 'success'
              })
              this.$router.push('/design/projects')
            } else {
              this.$message.error(response.msg || '更新失败')
            }
          })
          .catch(error => {
            console.error('更新项目失败:', error)
            this.$message.error(error.response?.data?.detail || error.message || '更新失败，请检查网络连接')
          })
          .finally(() => {
            loading.close()
            this.submitLoading = false
          })
      })
    },
    onCancel() {
      this.$router.push('/design/projects')
    }
  }
}
</script>

<style scoped>
.app-container {
  padding: 20px;
}
.editor-container {
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  overflow: hidden;
  height: 300px;
}
</style> 