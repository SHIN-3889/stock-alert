# 주식 자동 리포트 (GitHub Actions 자동 실행)

매일 정해진 시각(기본: 06:00 / 15:30 / 20:00 KST)에 보유 종목의
시세·자산 변동·인기 뉴스를 Gmail로 자동 발송합니다.

**컴퓨터가 꺼져 있어도 깃허브가 대신 실행**해줘서 PC를 켜둘 필요가 없습니다.

## 파일 구조

- `settings.json` — 보유종목/실행시각 (자유롭게 수정)
- `config.py` — 키는 환경변수, 설정은 settings.json 에서 읽음
- `prices.py` / `portfolio.py` / `news.py` / `mailer.py` / `message_builder.py` — 처리 로직
- `main.py` — 1회 실행 진입점
- `.github/workflows/stock_report.yml` — 자동 실행 스케줄

## 보유종목/평단가 변경

`settings.json` 의 값을 수정하고 커밋하면 다음 실행부터 반영됩니다.

## 자동 실행 시각 변경

`.github/workflows/stock_report.yml` 의 cron 값을 수정합니다.
GitHub Actions 는 UTC 기준이므로 **한국 시각에서 9시간을 뺀** 값을 적습니다.

## 비밀 키 등록 (GitHub Secrets)

저장소 Settings → Secrets and variables → Actions 에서 다음을 추가:
- NAVER_CLIENT_ID, NAVER_CLIENT_SECRET
- NEWSAPI_KEY
- GMAIL_ADDRESS, GMAIL_APP_PASSWORD, MAIL_TO

## 수동 실행

저장소의 Actions 탭 → "주식 리포트 자동 실행" → Run workflow.
