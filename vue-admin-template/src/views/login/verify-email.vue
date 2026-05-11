<template>
  <div class="login-container">
    <div class="login-form" style="text-align:center;">
      <h3 class="title">邮箱验证</h3>
      <div v-if="status==='pending'">
        正在验证您的邮箱，请稍候…
      </div>
      <div v-else-if="status==='success'">
        <el-alert title="邮箱验证成功，您现在可以登录账号" type="success" show-icon />
        <div style="margin-top:20px;">
          <el-button type="primary" @click="$router.push('/login')">前往登录</el-button>
        </div>
      </div>
      <div v-else>
        <el-alert :title="errorMessage" type="error" show-icon />
        <div style="margin-top:20px;">
          <el-button type="primary" @click="$router.push('/login')">返回登录</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { verifyEmail } from '@/api/user'

export default {
  name: 'VerifyEmail',
  data() {
    return {
      status: 'pending',
      errorMessage: '邮箱验证失败，请重新请求验证邮件或联系管理员'
    }
  },
  created() {
    const token = this.$route.query.token
    if (!token) {
      this.status = 'error'
      this.errorMessage = '缺少验证令牌'
      return
    }
    verifyEmail(token).then(() => {
      this.status = 'success'
    }).catch(err => {
      this.status = 'error'
      this.errorMessage = (err && err.message) || this.errorMessage
    })
  }
}
</script>

<style lang="scss" scoped>
.login-container {
  min-height: 100%;
  width: 100%;
  background-color: #2d3a4b;
  overflow: hidden;
}

.login-form {
  position: relative;
  width: 520px;
  max-width: 100%;
  padding: 160px 35px 0;
  margin: 0 auto;
  overflow: hidden;
}

.title {
  font-size: 26px;
  color: #eee;
  margin: 0px auto 40px auto;
  text-align: center;
  font-weight: bold;
}
</style>
