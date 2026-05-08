FROM python:3.12-slim

WORKDIR /app

# build context는 프로젝트 루트 (docker-compose에서 context: . 로 설정)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ .
COPY models/ /models/

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000"]
