# -*- coding: utf-8 -*-
"""Gmail 발송 — smtplib 로 본인 Gmail 계정에서 메일 전송.

Gmail은 일반 비밀번호가 아니라 '앱 비밀번호'(16자리)로 로그인합니다.
설정 방법은 README 참고. (2단계 인증 켜기 → 앱 비밀번호 발급)
"""

import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

import config


def send_email(subject: str, body: str):
    """리포트를 이메일로 전송."""
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr(("주식 리포트", config.GMAIL_ADDRESS))
    msg["To"] = config.MAIL_TO

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login(config.GMAIL_ADDRESS, config.GMAIL_APP_PASSWORD)
        server.sendmail(config.GMAIL_ADDRESS, config.MAIL_TO, msg.as_string())
    print("  메일 전송 성공")
