<template>
  <div class="app-container">
    <el-form ref="form" :model="form" :rules="rules" label-width="120px" v-loading="loading">
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
        <el-button type="primary" @click="onSubmit" :loading="submitLoading">保存</el-button>
        <el-button @click="onCancel">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script>
import { fetchModule, updateModule } from '@/api/module'
import { getProjectList } from '@/api/project'

export default {
  name: 'ModuleEdit',
  data() {
    return {
      loading: false,
      submitLoading: false,
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
    this.getModule()
  },
  methods: {
    getModule() {
      this.loading = true
      fetchModule(this.$route.params.id).then(response => {
        const moduleData = response.data
        this.form = {
          name: moduleData.name,
          description: moduleData.description,
          project_id: moduleData.project_id
        }
        this.loading = false
      }).catch(error => {
        this.loading = false
      })
    },
    getProjects() {
      getProjectList().then(response => {
        this.projectOptions = response.data
      })
    },
    onSubmit() {
      this.$refs.form.validate(valid => {
        if (valid) {
          this.submitLoading = true
          updateModule(this.$route.params.id, this.form).then(response => {
            this.$message({
              message: '更新成功',
              type: 'success'
            })
            this.submitLoading = false
            this.$router.push('/modules/list')
          }).catch(error => {
            this.submitLoading = false
          })
        } else {
          return false
        }
      })
    },
    onCancel() {
      this.$router.push('/modules/list')
    }
  }
}
</script> 