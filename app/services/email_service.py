import asyncio
import smtplib
import logging
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.config import (
    SMTP_SERVER,
    SMTP_PORT,
    SMTP_USERNAME,
    SMTP_PASSWORD,
    FROM_EMAIL,
    SMTP_USE_TLS,
    SMTP_USE_SSL,
    VERIFY_BASE_URL,
    RESET_BASE_URL,
)


logger = logging.getLogger(__name__)


class EmailService:
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        plain_content: Optional[str] = None,
    ) -> bool:
        """发送邮件（异步包装，尽量避免事件循环阻塞）"""

        msg = MIMEMultipart("alternative")
        msg["From"] = FROM_EMAIL or SMTP_USERNAME or ""
        msg["To"] = to_email
        msg["Subject"] = subject

        if plain_content:
            msg.attach(MIMEText(plain_content, "plain", "utf-8"))
        msg.attach(MIMEText(html_content, "html", "utf-8"))

        def _send() -> None:
            logger.debug(
                f"SMTP 连接: server={SMTP_SERVER}, port={SMTP_PORT}, tls={SMTP_USE_TLS}, ssl={SMTP_USE_SSL}, user={'SET' if SMTP_USERNAME else 'EMPTY'}"
            )
            if SMTP_USE_SSL:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT, context=context, timeout=20) as server:
                    try:
                        server.ehlo()
                        logger.debug("SMTP_SSL: EHLO 成功")
                    except Exception as e:
                        logger.warning(f"SMTP_SSL: EHLO 失败: {e}")
                    if not (SMTP_USERNAME and SMTP_PASSWORD):
                        logger.error("SMTP 凭据缺失：请设置 SMTP_USERNAME 与 SMTP_PASSWORD（授权码）")
                        raise RuntimeError("SMTP credentials missing: require AUTH before sendmail")
                    try:
                        server.login(SMTP_USERNAME, SMTP_PASSWORD)
                        logger.debug("SMTP_SSL: 登录成功")
                    except Exception as e:
                        logger.error("SMTP_SSL 登录失败，请检查用户名/密码或授权码")
                        raise
                    server.sendmail(msg["From"], [to_email], msg.as_string())
                    logger.info(f"邮件已发送至 {to_email}，主题: {subject}")
            else:
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=20) as server:
                    # 初始问候，声明客户端能力
                    try:
                        server.ehlo()
                        logger.debug("SMTP: 初次 EHLO 成功")
                    except Exception as e:
                        logger.warning(f"SMTP 初次 EHLO 失败: {e}")
                    if SMTP_USE_TLS:
                        try:
                            server.starttls()
                            logger.debug("SMTP: 已启用 STARTTLS")
                        except Exception as e:
                            logger.error(f"SMTP STARTTLS 失败: {e}")
                            raise
                        # STARTTLS 后需要再次 EHLO
                        try:
                            server.ehlo()
                            logger.debug("SMTP: STARTTLS 后 EHLO 成功")
                        except Exception as e:
                            logger.warning(f"SMTP STARTTLS 后 EHLO 失败: {e}")
                    # 校验并执行认证
                    if not (SMTP_USERNAME and SMTP_PASSWORD):
                        logger.error("SMTP 凭据缺失：请设置 SMTP_USERNAME 与 SMTP_PASSWORD（授权码）")
                        raise RuntimeError("SMTP credentials missing: require AUTH before sendmail")
                    try:
                        server.login(SMTP_USERNAME, SMTP_PASSWORD)
                        logger.debug("SMTP: 登录成功")
                    except Exception as e:
                        logger.error("SMTP 登录失败，请检查用户名/密码或授权码")
                        raise
                    server.sendmail(msg["From"], [to_email], msg.as_string())
                    logger.info(f"邮件已发送至 {to_email}，主题: {subject}")

        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, _send)
            return True
        except Exception as e:
            logger.exception(
                f"发送邮件失败: to={to_email}, subject={subject}, server={SMTP_SERVER}:{SMTP_PORT}, tls={SMTP_USE_TLS}. 错误: {e}"
            )
            return False

    async def send_verification_email(
        self, to_email: str, username: str, token: str
    ) -> bool:
        subject = "请验证您的邮箱 - Easy Test Platform"
        verification_url = f"{VERIFY_BASE_URL}?token={token}"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height:1.6;">
          <h3>亲爱的 {username},</h3>
          <p>感谢您注册 Easy Test Platform！请点击下面的按钮验证您的邮箱地址：</p>
          <p style="text-align:center; margin:24px 0;">
            <a href="{verification_url}" style="display:inline-block; padding:10px 18px; background:#007bff; color:#fff; text-decoration:none; border-radius:4px;">
              验证邮箱
            </a>
          </p>
          <p>如果按钮无法点击，您也可以复制以下链接到浏览器中打开：</p>
          <p style="word-break:break-all; background:#f8f9fa; padding:10px; border-radius:4px; font-size:12px;">
            {verification_url}
          </p>
          <p>此链接将在24小时后失效。</p>
        </div>
        """
        text_content = f"亲爱的 {username}, 请验证您的邮箱: {verification_url}"
        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_password_reset_email(
        self, to_email: str, username: str, token: str
    ) -> bool:
        subject = "重置您的密码 - Easy Test Platform"
        reset_url = f"{RESET_BASE_URL}?token={token}"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height:1.6;">
          <h3>亲爱的 {username},</h3>
          <p>收到您的密码重置请求。请点击下面的按钮重置密码：</p>
          <p style="text-align:center; margin:24px 0;">
            <a href="{reset_url}" style="display:inline-block; padding:10px 18px; background:#28a745; color:#fff; text-decoration:none; border-radius:4px;">
              重置密码
            </a>
          </p>
          <p>如果按钮无法点击，您也可以复制以下链接到浏览器中打开：</p>
          <p style="word-break:break-all; background:#f8f9fa; padding:10px; border-radius:4px; font-size:12px;">
            {reset_url}
          </p>
          <p>此链接将在24小时后失效。</p>
        </div>
        """
        text_content = f"亲爱的 {username}, 重置密码链接: {reset_url}"
        return await self.send_email(to_email, subject, html_content, text_content)

    async def send_welcome_email(self, to_email: str, username: str) -> bool:
        subject = "欢迎加入 - Easy Test Platform"
        html_content = f"""
        <div style="font-family: Arial, sans-serif; line-height:1.6;">
          <h3>亲爱的 {username},</h3>
          <p>欢迎加入 Easy Test Platform！祝您使用愉快。</p>
        </div>
        """
        text_content = f"亲爱的 {username}, 欢迎加入 Easy Test Platform！"
        return await self.send_email(to_email, subject, html_content, text_content)

# 全局邮件服务实例
email_service: Optional[EmailService] = None

def get_email_service() -> EmailService:
    """获取邮件服务实例"""
    global email_service
    if email_service is None:
        email_service = EmailService()
    return email_service
