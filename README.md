# XRP GitHub Pages 5분 갱신 대시보드

## 구조

- `xrp_analyzer.py` : XRP 대시보드 HTML과 `data/live_data.json`, `data/xrpl_stats.json` 생성
- `.github/workflows/update-pages.yml` : GitHub Actions가 5분마다 실행
- `requirements.txt` : Python 의존성

## GitHub Pages 설정

1. 이 폴더 내용을 GitHub 저장소 루트에 업로드합니다.
2. GitHub 저장소 `Settings → Pages`에서 Source를 `GitHub Actions`로 선택합니다.
3. `Actions → Update XRP Dashboard → Run workflow`로 첫 실행을 합니다.
4. 이후 `cron: */5 * * * *` 기준으로 5분마다 자동 갱신됩니다.

## TPS 처리 방식

- `server_info`로 최신 validated ledger를 확인합니다.
- 최근 ledger 샘플을 직접 조회해 트랜잭션 수와 close_time 차이로 평균 TPS를 계산합니다.
- 수집 실패 또는 캐시 부재 시 `0.00 TPS`가 아니라 `TPS 수집중`으로 표시합니다.
- `data/live_data.json`을 프론트엔드가 5분마다 다시 읽습니다.

## 선택 사항

CoinMarketCap 정확도를 높이고 싶으면 저장소 Secrets에 `CMC_API_KEY`를 등록하세요.
