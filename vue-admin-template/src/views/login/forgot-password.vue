<template>
  <div class="login-container">
    <el-form ref="forgotForm" :model="forgotForm" :rules="forgotRules" class="login-form" auto-complete="on" label-position="left">

      <div class="title-container">
        <h3 class="title">找回密码</h3>
      </div>

      <el-form-item prop="email">
        <span class="svg-container">
          <svg-icon icon-class="user" />
        </span>
        <el-input
          ref="email"
          v-model="forgotForm.email"
          placeholder="请输入注册邮箱"
          name="email"
          type="text"
          tabindex="1"
          auto-complete="on"
        />
      </el-form-item>

      <el-button :loading="loading" type="primary" style="width:100%;margin-bottom:30px;" @click.native.prevent="handleForgot">发送重置链接</el-button>

      <div style="text-align: right;">
        <router-link to="/login" class="link-type">返回登录</router-link>
      </div>

    </el-form>
  </div>
</template>

<script>
import { forgotPassword } from '@/api/user'
import { validateEmail } from '@/utils/validate'

export default {
  name: 'ForgotPassword',
  data() {
    const validateEmailRule = (rule, value, callback) => {
      if (!validateEmail(value)) {
        callback(new Error('请输入有效的邮箱地址'))
      } else {
        callback()
      }
    }
    return {
      forgotForm: {
        email: ''
      },
      forgotRules: {
        email: [{ required: true, trigger: 'blur', validator: validateEmailRule }]
      },
      loading: false
    }
  },
  methods: {
    handleForgot() {
      this.$refs.forgotForm.validate(valid => {
        if (valid) {
          this.loading = true
          forgotPassword(this.forgotForm.email).then(() => {
            this.$message({
              message: '重置链接已发送，请检查您的邮箱（或后端控制台）',
              type: 'success',
              duration: 5000
            })
            this.loading = false
          }).catch(() => {
            this.loading = false
          })
        } else {
          return false
        }
      })
    }
  }
}
</script>

<style lang="scss">
/* 复用 login 样式 */
$bg:#283443;
$light_gray:#fff;
$cursor: #fff;

@supports (-webkit-mask: none) and (not (cater-color: $cursor)) {
  .login-container .el-input input {
    color: $cursor;
  }
}

.login-container {
  .el-input {
    display: inline-block;
    height: 47px;
    width: 85%;

    input {
      background: transparent;
      border: 0px;
      -webkit-appearance: none;
      border-radius: 0px;
      padding: 12px 5px 12px 15px;
      color: $light_gray;
      height: 47px;
      caret-color: $cursor;

      &:-webkit-autofill {
        box-shadow: 0 0 0px 1000px $bg inset !important;
        -webkit-text-fill-color: $cursor !important;
      }
    }
  }

  .el-form-item {
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(0, 0, 0, 0.1);
    border-radius: 5px;
    color: #454545;
  }
}
</style>

<style lang="scss" scoped>
$bg:#2d3a4b;
$dark_gray:#889aa4;
$light_gray:#eee;

.login-container {
  min-height: 100%;
  width: 100%;
  background-color: $bg;
  overflow: hidden;

  .login-form {
    position: relative;
    width: 520px;
    max-width: 100%;
    padding: 160px 35px 0;
    margin: 0 auto;
    overflow: hidden;
  }

  .svg-container {
    padding: 6px 5px 6px 15px;
    color: $dark_gray;
    vertical-align: middle;
    width: 30px;
    display: inline-block;
  }

  .title-container {
    position: relative;

    .title {
      font-size: 26px;
      color: $light_gray;
      margin: 0px auto 40px auto;
      text-align: center;
      font-weight: bold;
    }
  }

  .link-type {
    color: #fff;
    font-size: 14px;
    text-decoration: none;
    &:hover {
      color: #409EFF;
    }
  }
}
</style>
