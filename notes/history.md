# 개발 요구사항 및 진행 이력 (`history.md`)

본 문서는 프로젝트의 매 회차별 개발 요구사항 요약, 계획 및 산출물 문서 링크, 주요 변경 내역을 기록합니다.

---

## [Iteration 1] 2026-10-17 13:44 - 초기 단축 URL 서비스 및 대시보드 구축
- **요구사항 요약**:
  - 긴 URL을 `https://domain/shorturl` 형태의 단축 링크로 변환하는 서비스
  - 웹 대시보드에서 Long URL 입력 시 Short URL 생성, 클릭 수 통계, 커스텀 단축 코드, QR 코드 생성, 만료일 설정 및 삭제 지원 (FastAPI + SQLite)
- **주요 구현 내역**:
  - `database.py`, `schemas.py`, `main.py`, `templates/index.html`, `templates/error.html`, `static/app.js`, `static/style.css`, `test_main.py` 최초 구현 및 테스트 통과

---

## [Iteration 2] 2026-10-17 13:54 - 타겟 메타정보 중간 랜딩 페이지, 1년 자동 만료/소멸, 메타 강제 갱신 및 문서화 체계 구축
- **요구사항 요약**:
  1. 루트 패스(`/`)는 웹 UI 대시보드 제공, 하위 패스(`/{shorturl}`)는 매핑 사이트로 연결하되 **타겟 사이트의 메타정보(제목, 미리보기 설명, 이미지 등)를 함께 볼 수 있는 중간 랜딩 페이지** 제공
  2. SQLite로 링크 매핑을 구현하고 **생성된 후 1년(365일)이 지나면 링크가 소멸** 가능하도록 구현
  3. UI 대시보드에서 이미 만들어진 링크를 검색·관리하고, **타겟 메타정보를 강제 갱신할 수 있는 리프레시 버튼** 추가
  4. `notes/` 디렉토리에 명세서, MVP 계획서, 요구사항 누적본, 요청/결과 이력 문서 작성
- **관련 기록 문서**:
  - 상세 명세서: `notes/SPECIFICATION.md`
  - 누적 요구사항: `notes/requirement.md`
  - 원본 요구사항 기록: `notes/req_202610171354.md`
  - MVP 및 세부 개발 계획: `notes/plan_202610171354.md`
  - 산출물 및 테스트 결과: `notes/result_202610171354.md`
- **주요 구현 결과**:
  - `metadata_scraper.py`를 통해 타겟 사이트의 Open Graph / HTML 메타정보(`meta_title`, `meta_description`, `meta_image`, `favicon_url`) 자동 추출
  - `templates/landing.html` 중간 랜딩 페이지 구현 (`/{short_code}` 접속 시 메타 프리뷰 카드 및 자동/수동 이동 제공, `?direct=1`로 즉시 이동 지원)
  - 생성 시 기본 만료일을 `+365일(1년)`로 설정하고 만료 링크 차단(`410 Gone`) 및 일괄 소멸 API(`DELETE /api/urls/expired/purge`) 구현
  - 대시보드 내 `[↻ 메타갱신]` 강제 리프레시 버튼 및 `POST /api/urls/{short_code}/refresh-meta` 연동 완료
  - `pytest` 5개 통합 시나리오 전체 통과


---

## [Iteration 3] 2026-10-17 14:10 - 프로젝트 종합 안내 문서(`README.md`) 작성
- **요구사항 요약**:
  - 프로젝트의 목적, 구현 내용, 사용법, 구체적인 활용 예시를 포함하여 `README.md` 작성
- **관련 기록 문서**:
  - 원본 요구사항 기록: `notes/req_202610171410.md`
  - 세부 계획: `notes/plan_202610171410.md`
  - 산출물 결과: `notes/result_202610171410.md`
- **주요 구현 결과**:
  - `README.md`에 서비스 목적, 핵심 아키텍처 및 라우팅 구조, 디렉토리 구성, 설치·실행 및 테스트 방법, REST API 요약표, 대시보드/메타갱신/cURL 활용 시나리오 문서화 완료


---

## [Iteration 4] 2026-10-17 14:29 - 프리뷰 메타 브릿지 즉시 리다이렉트 전환 및 사용자 링크 설명 텍스트 메타 반영
- **요구사항 요약**:
  1. `/{shorturl}` 임시 페이지가 링크 공유 시 프리뷰 메타정보만 제공하고, 접속 시에는 기다림(카운트다운) 없이 바로 타겟 링크로 전환되도록 변경
  2. 단축 링크 생성/관리 시 사용자 링크 설명 텍스트(`custom_description`)를 추가하여 프리뷰 메타정보(`og:description` 등)에 반영
- **관련 기록 문서**:
  - 원본 요구사항 기록: `notes/req_202610171429.md`
  - 세부 계획: `notes/plan_202610171429.md`
  - 산출물 결과: `notes/result_202610171429.md`
- **주요 구현 결과**:
  - `templates/landing.html`에서 카운트다운 화면을 제거하고 `<meta property="og:...">` 태그와 `<meta http-equiv="refresh" content="0; url=...">` + `window.location.replace(...)`를 통해 대기 없이 즉시 타겟 사이트로 전환되도록 수정
  - `database.py`, `schemas.py`, `main.py`에 `custom_description` 필드 및 `PATCH /api/urls/{short_code}/description` API를 추가하여 사용자 설명이 `meta_description`에 우선 반영되도록 구현
  - 대시보드(`templates/index.html`, `static/app.js`)에 사용자 링크 설명 입력란, `사용자 설명` 배지, `[설명수정]` 버튼 추가 및 `pytest` 5개 테스트 전체 통과


---

## [Iteration 5] 2026-10-17 15:05 - 환경변수 `DEFAUL_PREFIX` (기본값 `"/shorturl"`) 기반 하위 Subpath 라우팅 및 네비게이션 지원
- **요구사항 요약**:
  - 환경변수 `DEFAUL_PREFIX`를 지정하면 해당 값(기본값 `"/shorturl"`)에 따라 하위 subpath를 지원하고 모든 UI/API 네비게이션이 해당 subpath 기준으로 동작하도록 구현
- **관련 기록 문서**:
  - 원본 요구사항 기록: `notes/req_202610171505.md`
  - 세부 계획: `notes/plan_202610171505.md`
  - 산출물 결과: `notes/result_202610171505.md`
- **주요 구현 결과**:
  - `main.py`에서 `DEFAUL_PREFIX` (및 `DEFAULT_PREFIX`) 환경변수를 읽어 `normalize_prefix`로 정규화(기본값 `"/shorturl"`)하고 `APIRouter(prefix=BASE_PREFIX)`로 전체 라우트 구성
  - 루트(`/`) 접속 시 `{BASE_PREFIX}/`로 자동 리다이렉트, 생성되는 `short_url`도 `https://domain{BASE_PREFIX}/{short_code}` 형태로 발급
  - `templates/index.html`, `templates/error.html`, `static/app.js`에서 `base_prefix` / `window.BASE_PREFIX`를 기반으로 모든 네비게이션 및 API 요청 연동 완료 (`pytest` 5개 테스트 전체 통과)


---

## [Iteration 6] 2026-10-17 15:20 - 기본 리슨 포트를 5000번 포트로 설정
- **요구사항 요약**:
  - 기본 서비스 리슨 포트를 `5000`번 포트로 변경
- **관련 기록 문서**:
  - 원본 요구사항 기록: `notes/req_202610171520.md`
  - 세부 계획: `notes/plan_202610171520.md`
  - 산출물 결과: `notes/result_202610171520.md`
- **주요 구현 결과**:
  - `main.py`에 `DEFAULT_PORT = int(os.getenv("PORT", "5000"))` 및 `python main.py` 직접 실행 시 `5000`번 포트로 구동되도록 설정
  - `README.md` 및 `test_main.py` 업데이트 완료 (`pytest` 5개 테스트 전체 통과)


---

## [Iteration 7] 2026-10-17 15:29 - Docker 컨테이너화(`Dockerfile`), Persistent Volume(`DB_PATH`), `DEFAULT_PREFIX` 헬스체크 연동 및 `README.md` 업데이트
- **요구사항 요약**:
  - SQLite DB 파일에 대한 Persistent Volume(`DB_PATH`) 연동, 노출 포트 `5000`, `DEFAULT_PREFIX` 기반 Subpath 동작, `{prefix}/api/status` 컨테이너 `HEALTHCHECK`, 시작 `CMD`를 포함한 `Dockerfile` 작성 및 `README.md` 업데이트
- **관련 기록 문서**:
  - 원본 요구사항 기록: `notes/req_202610171529.md`
  - 세부 계획: `notes/plan_202610171529.md`
  - 산출물 결과: `notes/result_202610171529.md`
- **주요 구현 결과**:
  - `Dockerfile` 및 `.dockerignore` 생성 완료
  - `database.py`에 `DB_PATH` 환경변수 기반 DB 경로 설정 추가
  - `main.py`에 `DEFAULT_PREFIX` 참조 및 `{prefix}/api/status` 헬스체크 API 구현
  - `README.md`에 Docker 빌드/실행/볼륨 연동 배포 가이드 추가 및 `pytest` 5개 테스트 전체 통과


---

## [Iteration 8] 2026-10-17 15:36 - 개인정보, 캐시 파일 및 민감 데이터 보호를 위한 `.gitignore`, `.dockerignore` 업데이트
- **요구사항 요약**:
  - `.gitignore`와 `.dockerignore`에 개인정보, 캐시 파일, 민감 데이터를 모두 제외하도록 파일 및 디렉토리 목록 업데이트
- **관련 기록 문서**:
  - 원본 요구사항 기록: `notes/req_202610171536.md`
  - 세부 계획: `notes/plan_202610171536.md`
  - 산출물 결과: `notes/result_202610171536.md`
- **주요 구현 결과**:
  - `.gitignore` 및 `.dockerignore`에 Python/pytest 캐시, 가상환경, SQLite DB 및 영구 볼륨 디렉토리(`*.db`, `data/`, `shorturl_data/`), 환경변수/시크릿/인증서(`.env*`, `*.pem`, `*.key`, `*secret*`, `*credentials*`), 로그 및 에디터/OS 파일 차단 규칙 반영 완료
