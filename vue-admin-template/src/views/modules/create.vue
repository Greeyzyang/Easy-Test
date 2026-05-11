<template>
  <div class="app-container">
    <el-form ref="form" :model="form" :rules="rules" label-width="120px">
      <el-form-item label="模块名称" prop="name">
        <el-input v-model="form.name" placeholder="请输入模块名称" />
      </el-form-item>
      <el-form-item label="所属项目" prop="project_id">
        <el-select v-model="form.project_id" placeholder="请选择项目" style="width: 100%">
          <el-option v-for="item in projectOptions" :key="item.id" :label="item.name" :value="item.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="模块描述" prop="description">
        <el-input v-model="form.description" type="textarea" rows="4" placeholder="请输入模块描述" />
      </el-form-item>
      <el-form-item>
        <el-button type="primary" @click="onSubmit">创建</el-button>
        <el-button @click="onCancel">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { createModule } from '@/api/module'
import { getProjectList } from '@/api/project'

export default {
  name: 'ModuleCreate',
  data() {
    return {
      projectOptions: [],
      form: {
        name: '',
        project_id: '',
        description: ''
      },
      rules: {
        name: [
          { required: true, message: '请输入模块名称', trigger: 'blur' },
          { min: 2, max: 50, message: '长度在 2 到 50 个字符', trigger: 'blur' }
        ],
        project_id: [
          { required: true, message: '请选择所属项目', trigger: 'change' }
        ],
        description: [
          { required: true, message: '请输入模块描述', trigger: 'blur' },
          { max: 500, message: '描述不能超过500个字符', trigger: 'blur' }
        ]
      }
    }
  },
  created() {
    this.getProjects()
    // 如果从项目详情页面跳转过来，自动选择项目
    const projectId = this.$route.query.project_id
    if (projectId) {
      this.form.project_id = projectId
    }
  },
  methods: {
    getProjects() {
      getProjectList().then(response => {
        this.projectOptions = response.data
      })
    },
    onSubmit() {
      this.$refs.form.validate(valid => {
        if (valid) {
          createModule(this.form).then(response => {
            this.$message({
              message: '创建成功',
              type: 'success'
            })
            // 创建成功后直接跳转到模块列表页
            this.$router.push('/design/modules')
          })
        } else {
          return false
        }
      })
    },
    onCancel() {
      // 取消时直接返回模块列表页
      this.$router.push('/design/modules')
    }
  }
}
</script> 