import json
import os
import smtplib
import ssl
from datetime import datetime, timezone, timedelta
from email.message import EmailMessage
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "public" / "data"
MODELS = ["G80", "GV80", "GV70"]
RECIPIENT = os.getenv("EMAIL_TO", "minseok.lee@gmail.com")


def load_model(model):
    with (DATA_DIR / f"{model}.json").open("r", encoding="utf-8") as f:
        return json.load(f)


def text_section(data):
    lines = [
        f"[{data['model']}] scanned={data['scanned']} matched={data['matched']} report={data['reportFile']}"
    ]
    if not data["candidates"]:
        lines.append("조건을 통과한 차량이 없습니다.")
        return "\n".join(lines)

    for car in data["candidates"]:
        lines.append(
            " | ".join(
                [
                    f"#{car['rank']}",
                    car["title"],
                    car["price"],
                    car["year"],
                    car["mileage"],
                    f"상세: {car['url']}",
                ]
            )
        )
    return "\n".join(lines)


def html_section(data):
    rows = []
    for car in data["candidates"]:
        rows.append(
            f"""
            <tr>
              <td>{escape(str(car['rank']))}</td>
              <td>{escape(car['title'])}</td>
              <td>{escape(car['price'])}</td>
              <td>{escape(car['year'])}</td>
              <td>{escape(car['mileage'])}</td>
              <td><a href="{escape(car['url'])}">보기</a></td>
            </tr>
            """
        )

    body = (
        "\n".join(rows)
        if rows
        else '<tr><td colspan="6">조건을 통과한 차량이 없습니다.</td></tr>'
    )

    return f"""
      <h2>{escape(data['model'])}</h2>
      <p>스캔 {data['scanned']}대, 후보 {data['matched']}대<br>
      리포트: {escape(data['reportFile'])}</p>
      <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
        <thead>
          <tr>
            <th>순위</th>
            <th>차량</th>
            <th>가격</th>
            <th>연식</th>
            <th>주행거리</th>
            <th>상세</th>
          </tr>
        </thead>
        <tbody>{body}</tbody>
      </table>
    """


def require_env(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def main():
    smtp_host = require_env("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = require_env("SMTP_USER")
    smtp_password = require_env("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    now_kst = datetime.now(timezone.utc).astimezone(timezone(timedelta(hours=9)))
    subject = f"K Car 후보 차량 리스트 - {now_kst:%Y-%m-%d}"
    datasets = [load_model(model) for model in MODELS]

    text_body = "\n\n".join(text_section(data) for data in datasets)
    html_body = f"""
    <!doctype html>
    <html lang="ko">
      <body>
        <h1>K Car 후보 차량 리스트</h1>
        <p>기준: 2023년 1월 이후, 내차 피해 없음, 주의이력 없음, 무사고, 렌트 이력 없음</p>
        <p>웹앱: <a href="https://warabica.github.io/carsearch/">https://warabica.github.io/carsearch/</a></p>
        {''.join(html_section(data) for data in datasets)}
      </body>
    </html>
    """

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = smtp_from
    msg["To"] = RECIPIENT
    msg.set_content(text_body)
    msg.add_alternative(html_body, subtype="html")

    if smtp_port == 465:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(smtp_host, smtp_port, context=context) as server:
            server.login(smtp_user, smtp_password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(smtp_user, smtp_password)
            server.send_message(msg)

    print(f"Sent daily car list email to {RECIPIENT}")


if __name__ == "__main__":
    main()
