FROM python:3.12-slim

WORKDIR /app

# 환경변수 설정
# - PYTHONDONTWRITEBYTECODE / PYTHONUNBUFFERED: 파이썬 컨테이너 표준 최적화
# - DB_PATH: SQLite 데이터베이스 파일(shorturl.db) 영구 보존(Persistent Volume)을 위한 디렉토리 경로
# - DEFAULT_PREFIX: 웹앱의 기본 Base URL 서브패스 설정 (기본값: /shorturl)
# - PORT: 기본 리슨 포트 (5000)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/app/data \
    DEFAULT_PREFIX=/shorturl \
    PORT=5000

# SQLite 데이터베이스 Persistent Volume 마운트 디렉토리 생성
RUN mkdir -p /app/data
VOLUME ["/app/data"]

# 의존성 패키지 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 소스 복사
COPY . .

# 서비스 노출 포트 (5000번)
EXPOSE 5000

# 컨테이너 헬스체크 정의 (요청한 사양에 맞춘 Prefix 경로 연동)
HEALTHCHECK --interval=30s --timeout=10s --retries=3 --start-period=5s \
    CMD python -c "import os, requests; prefix = os.getenv('DEFAULT_PREFIX', ''); requests.get(f'http://localhost:5000{prefix}/api/status')"

# 시작 CMD (다음 2개 중 선택 사용 가능)
# 1) Gunicorn 운영서버로 기동 시 (FastAPI ASGI 호환을 위해 uvicorn worker와 함께 사용하거나 아래 옵션 참조)
# CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:5000", "--workers", "2", "--log-level", "debug", "--access-logfile", "-", "--error-logfile", "-", "--capture-output", "main:app"]

# 2) Run the FastAPI server using Uvicorn on port 5000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
