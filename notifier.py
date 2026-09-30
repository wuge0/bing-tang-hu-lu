from abc import ABC, abstractmethod
import os
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import requests

class Notifier(ABC):
    """
    抽象通知类，定义统一的通知接口
    """
    @abstractmethod
    def send(self, message: str):
        """
        发送消息
        :param message: 消息内容
        """
        pass

class WeChatNotifier(Notifier):
    """
    企业微信群机器人推送
    """
    def __init__(self, webhook_url: str):
        if not webhook_url:
            raise ValueError("未提供企业微信机器人 Webhook 地址")
        self.webhook_url = webhook_url

    def send(self, message: str):
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": message,
                "mentioned_list": ["@all"],
                "mentioned_mobile_list": ["@all"]
            }
        }
        response = requests.post(url=self.webhook_url, json=payload)
        if response.status_code != 200:
            raise RuntimeError(f"企业微信通知失败，状态码 {response.status_code}：{response.text}")


class EmailNotifier(Notifier):
    """
    邮件推送，支持通过授权码或密码登录 SMTP 服务
    """
    def __init__(self, smtp_server: str, port: int, username: str, auth_code_or_password: str, sender_email: str, recipient_email: str):
        """
        初始化邮件推送配置
        :param smtp_server: SMTP 服务器地址
        :param port: SMTP 端口号（通常为 465 或 587）
        :param username: 邮箱用户名
        :param auth_code_or_password: 邮箱授权码或密码
        :param sender_email: 发送方邮箱
        :param recipient_email: 接收方邮箱
        """
        self.smtp_server = smtp_server
        self.port = port
        self.username = username
        self.auth_code_or_password = auth_code_or_password  # 可以是授权码或密码
        self.sender_email = sender_email
        self.recipient_email = recipient_email

    def send(self, message: str):
        """
        发送邮件，支持 TLS 和 SSL
        :param message: 邮件正文内容
        """
        msg = MIMEText(message, 'plain', 'utf-8')

        # 正确设置邮件头，使用 formataddr 来处理显示名称和邮箱地址
        from_header = formataddr((str(Header(self.sender_email, 'utf-8')), self.sender_email))
        to_header = formataddr((str(Header(self.recipient_email, 'utf-8')), self.recipient_email))

        msg['From'] = from_header
        msg['To'] = to_header
        msg['Subject'] = Header('通知', 'utf-8')

        try:
            with smtplib.SMTP_SSL(self.smtp_server, self.port) if self.port == 465 else smtplib.SMTP(self.smtp_server, self.port) as server:
                # server.set_debuglevel(1)  # 启用调试模式
                if self.port != 465:
                    server.starttls()  # 启用 TLS
                server.login(self.username, self.auth_code_or_password)
                server.sendmail(self.sender_email, [self.recipient_email], msg.as_string())
                server.quit()  # Ensure the server connection is properly closed
        except Exception as e:
            raise RuntimeError(f"邮件通知失败：{e}")

class PushPlusNotifier(Notifier):
    """
    pushplus（推送加）推送，支持一对一、一对多（topic）推送
    """
    API_URL = "https://www.pushplus.plus/send"

    def __init__(self, token: str, title: str = "葫芦侠三楼签到", topic: str = "", template: str = "markdown"):
        if not token:
            raise ValueError("未提供 pushplus token")
        self.token = token
        self.title = title or "葫芦侠三楼签到"
        self.topic = topic or ""
        self.template = template or "markdown"

    def send(self, message: str):
        payload = {
            "token": self.token,
            "title": self.title,
            "content": message,
            "template": self.template
        }
        if self.topic:
            payload["topic"] = self.topic
        response = requests.post(
            url=self.API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        if response.status_code != 200:
            raise RuntimeError(f"pushplus 通知失败，HTTP 状态码 {response.status_code}：{response.text}")
        try:
            result = response.json()
        except ValueError:
            raise RuntimeError(f"pushplus 返回内容无法解析：{response.text}")
        if result.get("code") != 200:
            raise RuntimeError(f"pushplus 通知失败，code={result.get('code')}，msg={result.get('msg')}")


class WxPusherNotifier(Notifier):
    """
    WxPusher 推送，支持按 UID 单发或按 topicId 群发
    """
    API_URL = "https://wxpusher.zjiecode.com/api/send/message"

    def __init__(self, app_token: str, uids=None, topic_ids=None,
                 content_type: int = 3, summary: str = "", url: str = ""):
        if not app_token:
            raise ValueError("未提供 WxPusher appToken")
        self.app_token = app_token
        self.uids = uids or []
        self.topic_ids = topic_ids or []
        if not self.uids and not self.topic_ids:
            raise ValueError("WxPusher 需要至少提供 uids 或 topicIds 之一")
        self.content_type = int(content_type or 3)
        self.summary = summary or ""
        self.url = url or ""

    def send(self, message: str):
        payload = {
            "appToken": self.app_token,
            "content": message,
            "contentType": self.content_type,
            "verifyPayType": 0,
        }
        if self.summary:
            payload["summary"] = self.summary
        if self.uids:
            payload["uids"] = self.uids
        if self.topic_ids:
            payload["topicIds"] = self.topic_ids
        if self.url:
            payload["url"] = self.url

        response = requests.post(
            url=self.API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        if response.status_code != 200:
            raise RuntimeError(f"WxPusher 通知失败，HTTP 状态码 {response.status_code}：{response.text}")
        try:
            result = response.json()
        except ValueError:
            raise RuntimeError(f"WxPusher 返回内容无法解析：{response.text}")
        if result.get("code") != 1000:
            raise RuntimeError(f"WxPusher 通知失败，code={result.get('code')}，msg={result.get('msg')}")

        # 外层 code=1000 只代表请求被受理，还需逐个校验每个 UID/topic 的投递结果
        # 常见内层错误：1001=用户未订阅应用，1002=参数错误等
        failures = []
        for item in (result.get("data") or []):
            item_code = item.get("code")
            if item_code != 1000:
                target = item.get("uid") or f"topicId={item.get('topicId')}"
                failures.append(f"{target}: code={item_code}, {item.get('status')}")
        if failures:
            raise RuntimeError(
                "WxPusher 投递失败（通常需要用户在微信中订阅该应用）：" + "；".join(failures)
            )

        self.last_result = result


class NoOpNotifier(Notifier):
    """
    无操作通知器，用于忽略通知请求
    """
    def send(self, message: str):
        # 不执行任何操作
        print(f"通知被忽略：{message}")


# 工厂函数：根据通知方式返回相应的通知器实例
def get_notifier(method: str, config: dict) -> Notifier:
    """
    根据指定的推送方式和配置，返回相应的通知实例
    :param method: 推送方式，支持 'wechat' 或 'email'
    :param config: 配置字典，根据不同推送方式需要提供不同配置
    :return: Notifier 实例
    """
    if method == 'wechat':
        return WeChatNotifier(webhook_url=config.get("webhook_url"))
    elif method == 'email':
        return EmailNotifier(
            smtp_server=config.get("smtp_server"),
            port=config.get("port"),
            username=config.get("username"),
            auth_code_or_password=config.get("auth_code_or_password"),
            sender_email=config.get("sender_email"),
            recipient_email=config.get("recipient_email")
        )
    elif method == 'pushplus':
        return PushPlusNotifier(
            token=config.get("pushplus_token"),
            title=config.get("pushplus_title"),
            topic=config.get("pushplus_topic"),
            template=config.get("pushplus_template")
        )
    elif method == 'wxpusher':
        return WxPusherNotifier(
            app_token=config.get("wxpusher_app_token"),
            uids=config.get("wxpusher_uids"),
            topic_ids=config.get("wxpusher_topic_ids"),
            content_type=config.get("wxpusher_content_type", 3),
            summary=config.get("wxpusher_summary"),
            url=config.get("wxpusher_url")
        )
    elif method == 'none':
        return NoOpNotifier()
    else:
        raise ValueError(f"不支持的通知方式：{method}")

# 示例代码，用于测试通知器
if __name__ == "__main__":
    # 环境变量配置
    # 示例配置
    notifier_type = os.getenv("NOTIFIER_TYPE", "email")  # 默认为 'none'
    config = {
        "webhook_url": os.getenv("WECHAT_ROBOT_URL"),  # 企业微信机器人 Webhook 地址
        "smtp_server": "smtp.qq.com",  # SMTP 服务器地址
        "port": 465,  # SMTP 端口号
        "username": "your_email@qq.com",  # 邮箱用户名
        "auth_code_or_password": "your_smtp_auth_code_or_password",  # 授权码或密码
        "sender_email": "your_email@qq.com",  # 发送方邮箱
        "recipient_email": "recipient_email@example.com"  # 接收方邮箱
    }

    try:
        notifier = get_notifier(notifier_type, config)
        notifier.send("这是一个测试通知！")
        print("通知发送成功！")
    except Exception as e:
        print(f"通知发送失败：{e}")