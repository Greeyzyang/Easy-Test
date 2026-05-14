<template>
  <div class="login-container">
    <el-form ref="registerForm" :model="registerForm" :rules="registerRules" class="login-form" auto-complete="on" label-position="left">

      <div class="title-container">
        <h3 class="title">注册账号</h3>
      </div>

      <el-form-item prop="email">
        <span class="svg-container">
          <svg-icon icon-class="user" />
        </span>
        <el-input
          ref="email"
          v-model="registerForm.email"
          placeholder="请输入邮箱"
          name="email"
          type="text"
          tabindex="1"
          auto-complete="on"
        />
      </el-form-item>

      <el-form-item prop="password">
        <span class="svg-container">
          <svg-icon icon-class="password" />
        </span>
        <el-input
          :key="passwordType"
          ref="password"
          v-model="registerForm.password"
          :type="passwordType"
          placeholder="请输入密码"
          name="password"
          tabindex="2"
          auto-complete="on"
          @keyup.enter.native="handleRegister"
        />
        <span class="show-pwd" @click="showPwd">
          <svg-icon :icon-class="passwordType === 'password' ? 'eye' : 'eye-open'" />
        </span>
      </el-form-item>

      <el-button :loading="loading" type="primary" style="width:100%;margin-bottom:30px;" @click.native.prevent="handleRegister">注册</el-button>

      <div style="text-align: right;">
        <router-link to="/login" class="link-type">已有账号？立即登录</router-link>
      </div>

    </el-form>
  </div>
</template>

<script>
import { register } from '@/api/user'
import { validateEmail } from '@/utils/validate'

export default {
  name: 'Register',
  data() {
    const validateEmailRule = (rule, value, callback) => {
      if (!validateEmail(value)) {
        callback(new Error('请输入有效的邮箱地址'))
      } else {
        callback()
      }
    }
    const validatePassword = (rule, value, callback) => {
      if (value.length < 8) {
        callback(new Error('密码长度不能少于8位'))
      } else {
        callback()
      }
    }
    return {
      registerForm: {
        email: '',
        password: ''
      },
      registerRules: {
        email: [{ required: true, trigger: 'blur', validator: validateEmailRule }],
        password: [{ required: true, trigger: 'blur', validator: validatePassword }]
      },
      loading: false,
      passwordType: 'password'
    }
  },
  methods: {
    showPwd() {
      if (this.passwordType === 'password') {
        this.passwordType = ''
      } else {
        this.passwordType = 'password'
      }
      this.$nextTick(() => {
        this.$refs.password.focus()
      })
    },
    handleRegister() {
      this.$refs.registerForm.validate(valid => {
        if (valid) {
          this.loading = true
          register(this.registerForm)
            .then((res) => {
              this.loading = false
              const emailSent = res?.data?.email_sent !== false
              if (emailSent) {
                this.$confirm(
                  '注册成功！验证邮件已发送到您的邮箱，请点击邮件中的链接完成验证后再登录。',
                  '注册成功',
                {
                  confirmButtonText: '好的，我先去验证邮箱',
                  cancelButtonText: '留在当前页',
                  type: 'success',
                  showClose: false,
                  closeOnClickModal: false
                }
              ).then(() => {
                // 引导用户去邮箱验证，不跳转登录页
              }).catch(() => {
                // 用户留在当前页，不做跳转
              })
              } else {
                this.$confirm(
                  '账号创建成功！但验证邮件发送失败（可能未送达或被拦截），如果您未收到邮件，可以稍后在登录页点击"重发验证邮件"。',
                  '注册成功',
                  {
                    confirmButtonText: '我知道了',
                    showCancelButton: false,
                    type: 'warning',
                    showClose: false,
                    closeOnClickModal: false
                  }
                ).catch(() => {})
              }
            })
            .catch((err) => {
              this.loading = false
              let msg = '注册失败，请稍后重试'
              if (err && err.data && err.data.detail) {
                msg = err.data.detail
              } else if (err && err.message) {
                msg = err.message
              }
              this.$message({
                message: msg,
                type: 'error',
                duration: 5000
              })
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
/* 修复input背景不协调 和光标变色 */
/* Detail see https://github.com/PanJiaChen/vue-element-admin/pull/927 */

$bg:#283443;
$light_gray:#fff;
$cursor: #fff;

@supports (-webkit-mask: none) and (not (cater-color: $cursor)) {
  .login-container .el-input input {
    color: $cursor;
  }
}

/* reset element-ui css */
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

  .tips {
    font-size: 14px;
    color: #fff;
    margin-bottom: 10px;

    span {
      &:first-of-type {
        margin-right: 16px;
      }
    }
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

  .show-pwd {
    position: absolute;
    right: 10px;
    top: 7px;
    font-size: 16px;
    color: $dark_gray;
    cursor: pointer;
    user-select: none;
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
