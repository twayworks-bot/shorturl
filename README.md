# ShortURL — 프리뷰 메타 브릿지 및 스마트 링크 관리 서비스

**ShortURL**은 길고 복잡한 원본 URL(Long URL)을 `https://domain/{prefix}/{short_code}` 형태의 간결한 단축 링크로 변환하고, 링크 공유 시 **타겟 사이트의 메타정보(제목, 대표 이미지, 파비콘)와 사용자 링크 설명 텍스트를 Open Graph 프리뷰 메타로 제공**하면서 클릭 시에는 **기다림 없이 즉시 타겟 사이트로 전환(Zero-Wait Redirect)**하는 FastAPI + SQLite 기반 웹 애플리케이션입니다.

또한 **Docker 컨테이너 배포**, **SQLite Persistent Volume(`DB_PATH`) 연동**, **`DEFAULT_PREFIX` 환경변수를 통한 Subpath 라우팅**, **Prefix 연동 컨테이너 헬스체크(`{prefix}/api/status`)**를 기본 지원합니다.

---

## 1. 프로젝트 목적 (Project Purpose)

1. **사용자 편의성 및 가독성 극대화**
   - 복잡한 쿼리 파라미터가 포함된 긴 URL을 직관적인 6자리 난수 코드 또는 사용자 지정 별칭(Custom Alias)으로 단축하여 어디서든 쉽게 공유할 수 있도록 지원합니다.
2. **환경변수 `DEFAULT_PREFIX` 기반 하위 Subpath 네비게이션 지원**
   - 리버스 프록시(Nginx, Traefik, Ingress 등)나 도메인 하위 경로 배포 환경에 맞춰 `DEFAULT_PREFIX` 환경변수(기본값 `"/shorturl"`, `DEFAUL_PREFIX`도 호환)만 지정하면 대시보드, API, 헬스체크, 정적 파일, Swagger 문서, 단축 링크 생성/이동 경로가 모두 해당 Subpath 기준으로 자동 동작합니다.
3. **프리뷰 메타정보 노출 + 대기 없는 즉시 리다이렉션**
   - 단축 링크를 메신저(카카오톡, 슬랙, 디스코드 등)나 SNS에 공유할 때 타겟 사이트의 **제목(`og:title`), 설명(`og:description`), 대표 썸네일 이미지(`og:image`)**를 크롤러가 읽을 수 있도록 프리뷰 메타 브릿지 HTML을 응답합니다.
   - 실제 사용자가 링크를 클릭하여 접속할 때에는 중간 대기 시간(카운트다운) 없이 `<meta http-equiv="refresh" content="0; url=...">`와 `window.location.replace(...)`를 통해 **즉시 타겟 링크로 전환**됩니다.
4. **사용자 링크 설명 텍스트(`custom_description`) 메타 반영**
   - 링크 생성 시(또는 대시보드에서 수정 시) 사용자가 직접 링크 설명 텍스트를 입력하면, 타겟 사이트의 기본 설명 대신 **사용자가 입력한 설명 텍스트가 프리뷰 메타정보(`og:description`, `twitter:description`, `description`)에 우선 반영**됩니다.
5. **체계적인 링크 수명주기 관리 (1년 자동 만료 및 소멸)**
   - SQLite 데이터베이스로 모든 링크 매핑을 관리하며, 생성 시 별도 만료일을 지정하지 않으면 **생성 후 1년(365일)** 뒤 자동으로 만료/소멸되도록 설계하여 불필요한 장기 방치 링크를 방지합니다.
6. **직관적인 실시간 검색 및 메타정보 강제 갱신(Refresh)**
   - 웹 대시보드에서 이미 생성된 링크를 검색·관리하고, 타겟 사이트의 제목이나 썸네일이 변경되었을 때 **[↻ 메타갱신]** 버튼 하나로 최신 메타정보를 즉시 재수집할 수 있습니다.

---

## 2. 주요 구현 내용 및 핵심 기능 (Key Features)

### 2.1 `DEFAULT_PREFIX` 기반 라우팅 구조 (기본값: `/shorturl`)
- **`GET /` (루트 접속 시)**
  - 설정된 하위 Subpath 대시보드(`{DEFAULT_PREFIX}/`, 기본 `/shorturl/`)로 자동 `307 Temporary Redirect` 수행
- **`GET {DEFAULT_PREFIX}/` (예: `/shorturl/` — 웹 UI 대시보드)**
  - 원본 긴 URL 및 **사용자 링크 설명 텍스트(`custom_description`)** 입력, 단축 링크 즉시 생성
  - 사용자 지정 단축 코드(Custom Alias, 3~32자) 및 만료 일시 직접 지정 옵션
  - 생성된 전체 링크의 통계(총 링크 수, 누적 클릭 수, 활성 링크 수) 실시간 요약
  - 코드, 원본 URL, 사용자 설명, 메타 제목/설명 기반 통합 실시간 검색
  - 각 링크별 **[설명수정]**, **[↻ 메타갱신]**, **[복사]**, **[QR 코드 생성]**, **[삭제]** 및 **[만료 링크 일괄 정리]** 기능
- **`GET {DEFAULT_PREFIX}/api/status` (헬스체크 API)**
  - Docker 컨테이너 `HEALTHCHECK` 및 로드밸런서 상태 확인을 위해 현재 서비스 상태(`status: "ok"`), 적용된 `prefix`, SQLite DB 파일 경로를 JSON으로 반환
- **`GET {DEFAULT_PREFIX}/{short_code}` (예: `/shorturl/abc123` — 프리뷰 메타 노출 & 즉시 타겟 전환)**
  - 클릭 수(`clicks`) 자동 +1 증가
  - `<head>`에 타겟 사이트의 제목, 대표 이미지, 파비콘 및 **사용자 링크 설명이 반영된 Open Graph / Twitter Card 메타태그**를 포함하여 메신저/SNS 공유 시 풍부한 프리뷰 카드 제공
  - `<meta http-equiv="refresh" content="0; url=...">` 및 `window.location.replace(...)`를 통해 브라우저 접속 즉시 기다림 없이 타겟 링크로 전환

### 2.2 타겟 사이트 메타데이터 수집기 (`metadata_scraper.py`)
- `httpx`와 내장 `HTMLParser`를 활용하여 타겟 URL의 HTML에서 Open Graph(`og:title`, `og:description`, `og:image`), Twitter Card, `<title>`, `<meta name="description">`, `<link rel="icon">`을 추출합니다.
- 사용자가 입력한 `custom_description`이 존재하면 `meta_description`에 우선 적용하며, 비워둘 경우 타겟 사이트에서 수집한 설명을 자동으로 사용합니다.
- 상대 경로로 작성된 이미지나 파비콘 경로를 `urllib.parse.urljoin`으로 절대 URL로 자동 변환합니다.

### 2.3 SQLite 기반 저장소, Persistent Volume(`DB_PATH`) 및 1년(365일) 소멸 정책 (`database.py`)
- 환경변수 `DB_PATH` (또는 `DATA_DIR`)로 지정된 디렉토리 하위에 `shorturl.db` 파일을 생성·유지하여 Docker 컨테이너 재시작 시에도 데이터가 영구 보존됩니다.
- 생성 시 만료일(`expires_at`)을 비워두면 기본값으로 `created_at + 365일(1년)`이 자동 부여됩니다.
- 유효기간이 지난 링크로 접속 시 `410 Gone` 안내 페이지를 반환하며, 대시보드 또는 API를 통해 만료된 링크를 데이터베이스에서 일괄 소멸(Purge)시킬 수 있습니다.

---

## 3. 프로젝트 디렉토리 구조 (Directory Structure)

```text
C:\Dev\python\shoturl
├── main.py                 # FastAPI 애플리케이션, DEFAULT_PREFIX 라우터, /api/status 헬스체크 (기본 5000 포트)
├── database.py             # SQLite DB 연결(DB_PATH 볼륨 지원), ShortURL 모델(1년 만료 기본값)
├── schemas.py              # Pydantic 요청/응답 데이터 검증 스키마
├── metadata_scraper.py     # 타겟 사이트 Open Graph / HTML 메타정보 추출 모듈
├── test_main.py            # Pytest 기반 자동화 테스트 스위트
├── requirements.txt        # Python 의존성 패키지 목록
├── Dockerfile              # Docker 컨테이너 이미지 빌드 명세 (포트 5000, 볼륨 /app/data, HEALTHCHECK)
├── .dockerignore           # Docker 빌드 제외 파일 설정
├── README.md               # 프로젝트 소개, 구현 내용, 사용법, 배포 방법 및 활용 예시 문서
├── templates/
│   ├── index.html          # 웹 관리 대시보드 템플릿 (base_prefix 동적 네비게이션 적용)
│   ├── landing.html        # 프리뷰 메타 제공 및 즉시 리다이렉트 임시 페이지
│   └── error.html          # 404 Not Found / 410 Gone 에러 안내 페이지
├── static/
│   ├── app.js              # 대시보드 프론트엔드 로직 (window.BASE_PREFIX 기반 API 연동)
│   └── style.css           # 커스텀 스타일시트
└── notes/                  # 요구사항, 설계 명세(SPECIFICATION), 개발 계획 및 산출물 이력 문서
```

---

## 4. 로컬 설치 및 실행 방법 (Local Installation & Execution)

### 4.1 필수 패키지 설치
Python 3.10 이상 환경에서 아래 명령어로 의존성 패키지를 설치합니다:

```powershell
pip install -r requirements.txt
```

### 4.2 서버 실행 (기본 5000번 포트, `/shorturl` 프리픽스)
별도 환경변수를 지정하지 않으면 **5000번 포트**와 `DEFAULT_PREFIX="/shorturl"`이 기본 적용됩니다:

```powershell
# python으로 직접 실행 (기본 5000번 포트 자동 사용)
python main.py

# 또는 uvicorn 명령어로 실행
uvicorn main:app --reload --host 0.0.0.0 --port 5000
```

### 4.3 사용자 정의 `DEFAULT_PREFIX` 및 `DB_PATH` 지정 실행
```powershell
# PowerShell 예시
$env:DEFAULT_PREFIX="/go"; $env:DB_PATH="./data"; python main.py
```

### 4.4 접속 주소 (기본 5000번 포트, `DEFAULT_PREFIX="/shorturl"` 기준)
- **웹 대시보드**: [http://localhost:5000/shorturl/](http://localhost:5000/shorturl/) (`http://localhost:5000/` 접속 시에도 자동 이동)
- **헬스체크 엔드포인트**: [http://localhost:5000/shorturl/api/status](http://localhost:5000/shorturl/api/status)
- **Swagger API 문서**: [http://localhost:5000/shorturl/docs](http://localhost:5000/shorturl/docs)
- **ReDoc API 문서**: [http://localhost:5000/shorturl/redoc](http://localhost:5000/shorturl/redoc)

### 4.5 자동화 테스트 실행
```powershell
pytest -v
```

---

## 5. 웹앱 Docker 컨테이너 배포 방법 (Docker Deployment)

### 5.1 환경변수 명세
| 환경변수명 | 기본값 | 설명 |
| :--- | :--- | :--- |
| `DEFAULT_PREFIX` | `/shorturl` | 웹 대시보드, API, 단축 링크, 헬스체크의 기본 Base Subpath (`DEFAUL_PREFIX`도 호환 지원) |
| `DB_PATH` | `/app/data` (로컬 `.`) | SQLite 데이터베이스(`shorturl.db`) 파일이 저장될 Persistent Volume 디렉토리 경로 |
| `PORT` | `5000` | 웹 애플리케이션 리슨 포트 |

### 5.2 Docker 이미지 빌드
프로젝트 루트 디렉토리에서 아래 명령어로 Docker 이미지를 빌드합니다:

```bash
docker build -t shorturl-app:latest .
```

### 5.3 Docker 컨테이너 실행 (Persistent Volume 및 `DEFAULT_PREFIX` 연동)
호스트의 `./shorturl_data` 디렉토리를 컨테이너의 `/app/data`(`DB_PATH`)에 볼륨 마운트하여 컨테이너 재시작/재배포 시에도 SQLite 데이터가 영구 유지되도록 실행합니다:

```bash
# 기본 /shorturl 프리픽스로 5000번 포트 실행
docker run -d \
  --name shorturl \
  -p 5000:5000 \
  -e DEFAULT_PREFIX=/shorturl \
  -e DB_PATH=/app/data \
  -v $(pwd)/shorturl_data:/app/data \
  shorturl-app:latest
```

PowerShell 환경에서 실행할 경우:
```powershell
docker run -d `
  --name shorturl `
  -p 5000:5000 `
  -e DEFAULT_PREFIX=/shorturl `
  -e DB_PATH=/app/data `
  -v "${PWD}/shorturl_data:/app/data" `
  shorturl-app:latest
```

### 5.4 컨테이너 헬스체크 및 시작 CMD 구성 (`Dockerfile`)
- **헬스체크(`HEALTHCHECK`)**: `DEFAULT_PREFIX` 환경변수를 자동으로 읽어 `http://localhost:5000{prefix}/api/status` 엔드포인트를 30초 주기로 점검합니다:
  ```dockerfile
  HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
      CMD python -c "import os, requests; prefix = os.getenv('DEFAULT_PREFIX', ''); requests.get(f'http://localhost:5000{prefix}/api/status')"
  ```
- **시작 명령(`CMD`)**: 기본적으로 Uvicorn 서버(`CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]`)로 기동되며, 멀티 워커 운영 환경에서는 `Dockerfile`에 포함된 Gunicorn 명령어로 전환하여 기동할 수 있습니다.

---

## 6. REST API 명세 요약 (`{prefix}` 기본값: `/shorturl`)

| 메서드 | 엔드포인트 | 설명 |
| :--- | :--- | :--- |
| `GET` | `{prefix}/` | 웹 UI 대시보드 페이지 렌더링 |
| `GET` | `{prefix}/api/status` | 컨테이너 및 서비스 헬스체크 상태 반환 (`{"status": "ok", ...}`) |
| `POST` | `{prefix}/api/urls` | 단축 URL 생성 (`https://domain{prefix}/{short_code}`), 사용자 설명 반영 및 타겟 메타 수집 |
| `GET` | `{prefix}/api/urls?q={keyword}` | 생성된 단축 URL 목록 조회 및 통합 키워드 검색 |
| `GET` | `{prefix}/api/urls/{short_code}` | 특정 단축 URL의 상세 정보, 클릭 수, 메타정보 조회 |
| `PATCH` | `{prefix}/api/urls/{short_code}/description` | **사용자 링크 설명 텍스트 수정 및 프리뷰 메타정보 즉시 반영** |
| `POST` | `{prefix}/api/urls/{short_code}/refresh-meta` | **타겟 사이트의 최신 메타정보(제목, 설명, 이미지) 강제 재수집 및 갱신** |
| `DELETE` | `{prefix}/api/urls/expired/purge` | 유효기간(1년 등)이 경과한 만료 링크 일괄 소멸(삭제) |
| `DELETE` | `{prefix}/api/urls/{short_code}` | 특정 단축 URL 즉시 삭제 |
| `GET` | `{prefix}/{short_code}` | 프리뷰 메타정보(OG 태그) 노출과 동시에 타겟 링크로 대기 없이 즉시 전환 |

---

## 7. 구체적인 활용 예시 (Practical Examples)

### 예시 1: 웹 대시보드에서 사용자 설명을 포함한 단축 링크 만들기
1. 브라우저에서 `http://localhost:5000/shorturl/`에 접속합니다.
2. **원본 긴 URL** 입력란에 `https://fastapi.tiangolo.com/ko/tutorial/`을 입력합니다.
3. **사용자 링크 설명 텍스트** 입력란에 `"사내 백엔드 개발자 온보딩용 FastAPI 공식 가이드입니다."`를 입력합니다.
4. **사용자 지정 단축 코드**에 `fastapi-ko`를 입력하고 **[단축 URL 생성]** 버튼을 클릭합니다.
5. 생성된 `http://localhost:5000/shorturl/fastapi-ko` 링크를 메신저에 공유하면 제목·대표 이미지와 함께 입력한 사용자 설명이 프리뷰로 노출되며, 클릭 시 기다림 없이 즉시 원본 사이트로 이동합니다.

### 예시 2: cURL / API를 활용한 자동화 연동 (기본 5000번 포트, `/shorturl` 기준)

```bash
# 0) 서비스 헬스체크 확인
curl "http://localhost:5000/shorturl/api/status"

# 1) 사용자 링크 설명을 포함하여 단축 URL 생성
curl -X POST "http://localhost:5000/shorturl/api/urls" \
     -H "Content-Type: application/json" \
     -d '{
           "original_url": "https://github.com/tiangolo/fastapi",
           "custom_alias": "gh-fastapi",
           "custom_description": "FastAPI 공식 GitHub 저장소 바로가기"
         }'

# 2) 사용자 링크 설명 텍스트 수정
curl -X PATCH "http://localhost:5000/shorturl/api/urls/gh-fastapi/description" \
     -H "Content-Type: application/json" \
     -d '{"custom_description": "2026년 업데이트된 FastAPI 공식 저장소"}'

# 3) 타겟 사이트 메타정보 강제 갱신 (Refresh)
curl -X POST "http://localhost:5000/shorturl/api/urls/gh-fastapi/refresh-meta"

# 4) 만료된 링크 일괄 소멸(정리)
curl -X DELETE "http://localhost:5000/shorturl/api/urls/expired/purge"
```
