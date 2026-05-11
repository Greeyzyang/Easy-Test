<template>
  <div class="app-container">
    <div class="filter-container">
      <el-button class="filter-item" type="primary" icon="el-icon-plus" @click="handleCreate">
        添加模型
      </el-button>
      <el-link
        class="filter-item"
        type="primary"
        icon="el-icon-link"
        href="https://openrouter.ai/"
        target="_blank"
        :underline="false"
      >
        OpenRouter 官网
      </el-link>
    </div>

    <el-row :gutter="24">
      <el-col v-for="item in list" :key="item.id" :span="6" style="margin-bottom: 24px;">
        <el-card :body-style="{ padding: '0px' }" class="model-card" :class="{ 'active-card': item.is_active }">
          <div class="card-header" :class="getProviderClass(item.provider)">
            <div class="provider-icon">
              <img
                v-if="getProviderLogo(item.provider)"
                :src="getProviderLogo(item.provider)"
                class="logo-img"
                @error="(e) => handleImageError(e, item.provider)"
              >
              <i v-else :class="getProviderIcon(item.provider)" />
            </div>
            <div class="model-info">
              <span class="model-name">{{ item.name }}</span>
              <span class="provider-name">{{ item.provider }}</span>
            </div>
            <div v-if="item.is_active" class="status-badge">
              <el-tag type="success" effect="dark" size="small" class="status-tag">
                <i class="el-icon-check" /> 当前使用
              </el-tag>
            </div>
          </div>

          <div class="card-body">
            <div class="info-item">
              <span class="label">调用模型名</span>
              <span class="value" :title="item.model_name">{{ item.model_name }}</span>
            </div>
            <div class="info-item">
              <span class="label">Base URL</span>
              <span class="value" :title="item.base_url">{{ item.base_url }}</span>
            </div>
            <div class="info-item description">
              <span class="label">描述</span>
              <span class="value">{{ item.description || '暂无描述' }}</span>
            </div>
          </div>

          <div class="card-footer">
            <div class="left-actions">
              <el-button
                v-if="!item.is_active"
                type="text"
                class="activate-btn"
                @click="handleActivate(item)"
              >
                激活
              </el-button>
              <el-button
                v-else
                type="text"
                class="deactivate-btn"
                @click="handleDeactivate(item)"
              >
                禁用
              </el-button>
            </div>
            <div class="right-actions">
              <el-button
                type="text"
                class="edit-btn"
                icon="el-icon-edit"
                @click="handleUpdate(item)"
              >
                编辑
              </el-button>
              <el-button
                type="text"
                class="delete-btn"
                icon="el-icon-delete"
                @click="handleDelete(item)"
              >
                删除
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog :title="textMap[dialogStatus]" :visible.sync="dialogFormVisible" width="500px" custom-class="model-dialog">
      <el-form ref="dataForm" :rules="rules" :model="temp" label-position="top" class="model-form" autocomplete="off">
        <el-row :gutter="20">
          <el-col :span="12">
            <el-form-item label="名称" prop="name">
              <el-input v-model="temp.name" placeholder="请输入名称" autocomplete="off" />
            </el-form-item>
          </el-col>
          <el-col :span="12">
            <el-form-item label="供应商" prop="provider">
              <el-select v-model="temp.provider" class="filter-item" placeholder="请选择" style="width: 100%" @change="handleProviderChange">
                <el-option v-for="item in providerOptions" :key="item" :label="item" :value="item">
                  <span style="float: left; display: flex; align-items: center;">
                    <img
                      v-if="getProviderLogo(item)"
                      :src="getProviderLogo(item)"
                      style="width: 20px; height: 20px; margin-right: 8px;"
                      @error="(e) => handleImageError(e, item)"
                    >
                    {{ item }}
                  </span>
                  <span style="float: right; color: #8492a6; font-size: 13px">
                    <i v-if="!getProviderLogo(item)" :class="getProviderIcon(item)" />
                  </span>
                </el-option>
              </el-select>
            </el-form-item>
          </el-col>
        </el-row>

        <el-form-item label="调用模型名" prop="model_name">
          <el-input v-model="temp.model_name" :placeholder="getModelNamePlaceholder()" autocomplete="off" />
          <div v-if="temp.provider === 'openrouter'" class="form-tip">
            <i class="el-icon-info" />
            模型ID请参考 <a href="https://openrouter.ai/models" target="_blank">OpenRouter 模型列表</a>。
            <div style="margin-top: 8px;">
              <span style="display: block; margin-bottom: 4px; color: #606266; font-weight: 500;">推荐配置:</span>
              <el-tooltip 
                v-for="model in openRouterModels"
                :key="model.id"
                :content="model.desc"
                placement="top"
              >
                <el-tag 
                  size="small" 
                  :type="temp.model_name === model.id ? 'success' : 'info'"
                  effect="plain" 
                  style="cursor: pointer; margin-right: 8px; margin-bottom: 8px;" 
                  @click="handleSelectModel(model.id)"
                >
                  {{ model.name }}
                </el-tag>
              </el-tooltip>
            </div>
          </div>
        </el-form-item>
        <el-form-item label="API Key" prop="api_key">
          <el-input v-model="temp.api_key" placeholder="请输入 API Key" show-password autocomplete="new-password" />
        </el-form-item>
        <el-form-item label="Base URL" prop="base_url">
          <el-input v-model="temp.base_url" placeholder="请输入 Base URL" autocomplete="off" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="temp.description" :autosize="{ minRows: 2, maxRows: 4}" type="textarea" placeholder="备注信息" />
        </el-form-item>
      </el-form>
      <div slot="footer" class="dialog-footer">
        <el-button @click="dialogFormVisible = false">取消</el-button>
        <el-button type="success" :loading="isTestingConnection" icon="el-icon-connection" @click="handleTestConnection">
          测试连接
        </el-button>
        <el-button type="primary" @click="dialogStatus==='create'?createData():updateData()">
          确认
        </el-button>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { getAIModels, createAIModel, activateAIModel, deactivateAIModel, updateAIModel, deleteAIModel, testConnection } from '@/api/ai-model'

export default {
  name: 'AIModels',
  data() {
    return {
      list: [],
      failedLogos: [],
      dialogFormVisible: false,
      isTestingConnection: false,
      dialogStatus: '',
      textMap: {
        update: '编辑模型',
        create: '添加模型'
      },
      temp: {
        id: undefined,
        name: '',
        provider: '',
        model_name: '',
        api_key: '',
        base_url: '',
        description: ''
      },
      providerOptions: ['deepseek', 'doubao', 'glm', 'openai', 'openrouter'],
      openRouterModels: [
        { id: 'openrouter/auto', name: 'Auto (智能路由)', desc: '自动选择最佳模型' },
        { id: 'openai/gpt-5.4', name: 'GPT-5.4', desc: 'OpenAI 2026 最新旗舰' },
        { id: 'anthropic/claude-4.6-sonnet', name: 'Claude 4.6 Sonnet', desc: '强力代码与逻辑推理' },
        { id: 'google/gemini-3.1-flash-lite', name: 'Gemini 3.1 Flash', desc: '极速高性价比' },
        { id: 'deepseek/deepseek-v3.2', name: 'DeepSeek V3.2', desc: '开源性价比之王' }
      ],
      rules: {
        name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
        provider: [{ required: true, message: '请选择供应商', trigger: 'change' }],
        model_name: [{ required: true, message: '请输入调用模型名', trigger: 'blur' }],
        api_key: [{ required: true, message: '请输入API Key', trigger: 'blur' }],
        base_url: [{ required: true, message: '请输入Base URL', trigger: 'blur' }]
      }
    }
  },
  created() {
    this.getList()
  },
  methods: {
    getList() {
      getAIModels().then(response => {
        this.list = response.data
      })
    },
    resetTemp() {
      this.temp = {
        id: undefined,
        name: '',
        provider: '',
        model_name: '',
        api_key: '',
        base_url: '',
        description: ''
      }
    },
    getProviderIcon(provider) {
      const map = {
        deepseek: 'el-icon-cpu',
        doubao: 'el-icon-chat-dot-round',
        glm: 'el-icon-connection',
        openai: 'el-icon-sunny',
        openrouter: 'el-icon-link'
      }
      return map[provider] || 'el-icon-box'
    },
    getProviderLogo(provider) {
      if (this.failedLogos.includes(provider)) {
        return null
      }
      const map = {
        deepseek: 'https://registry.npmmirror.com/@lobehub/icons-static-png/latest/files/light/deepseek.png',
        doubao: 'https://registry.npmmirror.com/@lobehub/icons-static-png/latest/files/light/doubao.png',
        glm: 'https://registry.npmmirror.com/@lobehub/icons-static-png/latest/files/light/zhipu.png',
        openai: 'https://registry.npmmirror.com/@lobehub/icons-static-png/latest/files/light/openai.png'
      }
      return map[provider] || null
    },
    handleImageError(e, provider) {
      if (!this.failedLogos.includes(provider)) {
        this.failedLogos.push(provider)
      }
    },
    handleProviderChange(value) {
      // 仅当 Base URL 为空时自动填充
      if (!this.temp.base_url) {
        const defaultUrls = {
          deepseek: 'https://api.deepseek.com',
          openai: 'https://api.openai.com/v1',
          doubao: 'https://ark.cn-beijing.volces.com/api/v3',
          glm: 'https://open.bigmodel.cn/api/paas/v4/',
          openrouter: 'https://openrouter.ai/api/v1'
        }
        if (defaultUrls[value]) {
          this.temp.base_url = defaultUrls[value]
        }
      }
    },
    handleSelectModel(modelId) {
      // 使用 $set 确保响应式更新
      this.$set(this.temp, 'model_name', modelId)
    },
    getModelNamePlaceholder() {
      if (this.temp.provider === 'openrouter') {
        return '例如: openrouter/auto (智能推荐), openai/gpt-5.4'
      }
      return '请输入模型名称'
    },
    getProviderClass(provider) {
      return `provider-${provider}`
    },
    handleTestConnection() {
      this.$refs['dataForm'].validate((valid) => {
        if (valid) {
          this.isTestingConnection = true
          testConnection(this.temp).then(response => {
            this.isTestingConnection = false
            if (response.data.success) {
              this.$message.success(response.data.msg)
            } else {
              this.$message.error('连接失败: ' + (response.data.error || '未知错误'))
            }
          }).catch((err) => {
            this.isTestingConnection = false
            this.$message.error('连接请求失败: ' + err.message)
          })
        } else {
          this.$message.warning('请先完善必填信息')
        }
      })
    },
    handleCreate() {
      this.resetTemp()
      this.dialogStatus = 'create'
      this.dialogFormVisible = true
      this.$nextTick(() => {
        this.$refs['dataForm'].clearValidate()
      })
    },
    handleUpdate(row) {
      this.temp = Object.assign({}, row) // copy obj
      this.dialogStatus = 'update'
      this.dialogFormVisible = true
      this.$nextTick(() => {
        this.$refs['dataForm'].clearValidate()
      })
    },
    createData() {
      this.$refs['dataForm'].validate((valid) => {
        if (valid) {
          createAIModel(this.temp).then(() => {
            this.dialogFormVisible = false
            this.$notify({
              title: 'Success',
              message: '添加成功',
              type: 'success',
              duration: 2000
            })
            this.getList()
          })
        }
      })
    },
    updateData() {
      this.$refs['dataForm'].validate((valid) => {
        if (valid) {
          const tempData = Object.assign({}, this.temp)
          updateAIModel(tempData.id, tempData).then(() => {
            this.dialogFormVisible = false
            this.$notify({
              title: 'Success',
              message: '更新成功',
              type: 'success',
              duration: 2000
            })
            this.getList()
          })
        }
      })
    },
    handleActivate(row) {
      const activeModel = this.list.find(item => item.is_active)
      if (activeModel) {
        this.$confirm(`确认切换模型? 当前激活的 [${activeModel.name}] 将被禁用。`, '提示', {
          confirmButtonText: '切换',
          cancelButtonText: '取消',
          type: 'warning'
        }).then(() => {
          this.executeActivate(row)
        })
      } else {
        this.executeActivate(row)
      }
    },
    executeActivate(row) {
      activateAIModel(row.id).then(() => {
        this.$notify({
          title: 'Success',
          message: '模型已激活',
          type: 'success',
          duration: 2000
        })
        this.getList()
      })
    },
    handleDeactivate(row) {
      const activeCount = this.list.filter(item => item.is_active).length
      if (activeCount <= 1) {
        this.$confirm('确认禁用当前模型? 禁用后将没有可用模型。', '提示', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        }).then(() => {
          this.executeDeactivate(row)
        })
      } else {
        this.executeDeactivate(row)
      }
    },
    executeDeactivate(row) {
      deactivateAIModel(row.id).then(() => {
        this.$notify({
          title: 'Success',
          message: '模型已禁用',
          type: 'success',
          duration: 2000
        })
        this.getList()
      })
    },
    handleDelete(row) {
      this.$confirm('确认删除该模型配置?', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }).then(() => {
        deleteAIModel(row.id).then(() => {
          this.$notify({
            title: 'Success',
            message: '删除成功',
            type: 'success',
            duration: 2000
          })
          this.getList()
        })
      })
    }
  }
}
</script>

<style lang="scss" scoped>
.app-container {
  background-color: #f0f2f5;
  min-height: 100vh;
  padding: 24px;
}

.model-card {
  border: none;
  border-radius: 12px;
  overflow: hidden;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  background: #ffffff;
  height: 100%;

  &:hover {
    transform: translateY(-8px);
    box-shadow: 0 12px 24px rgba(0,0,0,0.1);
  }

  &.active-card {
    box-shadow: 0 0 0 2px #52c41a, 0 8px 16px rgba(82, 196, 26, 0.2);
    transform: translateY(-4px);
  }
}

.card-header {
  padding: 24px;
  color: white;
  position: relative;
  display: flex;
  align-items: center;
  height: 100px;

  &.provider-deepseek { background: linear-gradient(135deg, #1890ff 0%, #36cfc9 100%); }
  &.provider-doubao { background: linear-gradient(135deg, #ff4d4f 0%, #ff7a45 100%); }
  &.provider-glm { background: linear-gradient(135deg, #722ed1 0%, #b37feb 100%); }
  &.provider-openai { background: linear-gradient(135deg, #52c41a 0%, #95de64 100%); }
  &.provider-openrouter { background: linear-gradient(135deg, #111827 0%, #374151 100%); }

  .provider-icon {
    margin-right: 16px;
    background: rgba(255,255,255,0.25);
    border-radius: 12px;
    width: 56px;
    height: 56px;
    display: flex;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);

    i {
      font-size: 32px;
      color: #fff;
    }

    .logo-img {
      width: 40px;
      height: 40px;
      object-fit: contain;
      background: white;
      border-radius: 8px;
      padding: 4px;
    }
  }

  .model-info {
    flex: 1;
    display: flex;
    flex-direction: column;
    overflow: hidden;

    .model-name {
      font-size: 20px;
      font-weight: 600;
      margin-bottom: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      text-shadow: 0 1px 2px rgba(0,0,0,0.1);
    }

    .provider-name {
      font-size: 12px;
      opacity: 0.9;
      text-transform: uppercase;
      letter-spacing: 0.5px;
      font-weight: 500;
    }
  }

  .status-badge {
    position: absolute;
    top: 16px;
    right: 16px;

    .status-tag {
      border: none;
      background: rgba(255, 255, 255, 0.2);
      backdrop-filter: blur(4px);
      color: #fff;
      font-weight: 500;
    }
  }
}

.card-body {
  padding: 24px;

  .info-item {
    margin-bottom: 16px;
    display: flex;
    align-items: flex-start;
    font-size: 14px;
    line-height: 1.5;

    .label {
      color: #909399;
      width: 80px;
      flex-shrink: 0;
      font-weight: 500;
    }

    .value {
      color: #303133;
      flex: 1;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
      font-family: monospace;
      background: #f5f7fa;
      padding: 2px 6px;
      border-radius: 4px;
    }

    &.description {
      .value {
        white-space: normal;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        -webkit-box-orient: vertical;
        font-family: inherit;
        background: none;
        padding: 0;
        color: #606266;
      }
    }
  }
}

.card-footer {
  padding: 16px 24px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fafafa;

  .left-actions {
    .activate-btn {
      color: #52c41a;
      font-weight: 600;
      padding: 0;

      &:hover {
        color: #73d13d;
      }
    }

    .deactivate-btn {
      color: #ff4d4f;
      font-weight: 600;
      padding: 0;

      &:hover {
        color: #ff7875;
      }
    }
  }

  .right-actions {
    display: flex;
    gap: 12px;

    .edit-btn {
      color: #409EFF;
      padding: 0;

      &:hover {
        color: #66b1ff;
      }
    }

    .delete-btn {
      color: #ff4d4f;
      padding: 0;

      &:hover {
        color: #ff7875;
      }
    }
  }
}

.model-form {
  .el-form-item {
    margin-bottom: 22px;
  }

  .form-tip {
    font-size: 12px;
    color: #909399;
    margin-top: 4px;
    line-height: 1.4;

    i {
      margin-right: 4px;
    }

    a {
      color: #409EFF;
      &:hover {
        text-decoration: underline;
      }
    }

    code {
      background: #f4f4f5;
      padding: 2px 4px;
      border-radius: 4px;
      color: #c0392b;
      font-family: monospace;
    }
  }
}
</style>
