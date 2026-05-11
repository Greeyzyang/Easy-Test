<template>
  <div class="app-container">
    <el-form ref="form" :model="form" :rules="rules" label-width="120px">
      <el-form-item label="项目名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入项目名称" />
      </el-form-item>
      <el-form-item label="项目描述" prop="description">
        <el-input v-model="form.description" type="textarea" rows="4" placeholder="请输入项目描述" />
      </el-form-item>

      <el-form-item style="margin-top: 20px;">
        <el-button type="primary" @click="onSubmit">创建</el-button>
        <el-button @click="onCancel">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { createProject } from '@/api/project'

export default {
  name: 'ProjectCreate',
  data() {
    return {
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
  methods: {
    onSubmit() {
      this.$refs.form.validate(valid => {
        if (!valid) {
          return false
        }

        const loading = this.$loading({
          lock: true,
          text: '创建中...',
          spinner: 'el-icon-loading',
          background: 'rgba(0, 0, 0, 0.7)'
        })

        createProject(this.form)
          .then(response => {
            if (response.code === '0') {
              this.$message({
                message: '创建成功',
                type: 'success'
              })
              this.$router.push('/design/projects')
            } else {
              this.$message.error(response.msg || '创建失败')
            }
          })
          .catch(error => {
            console.error('创建项目失败:', error)
            this.$message.error(error.response?.data?.detail || error.message || '创建项目失败')
          })
          .finally(() => {
            loading.close()
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