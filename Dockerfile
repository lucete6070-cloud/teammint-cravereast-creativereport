# 서버(Cloud Run 등)용 이미지. 로컬 실행에는 필요 없다.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 APP_MODE=server PORT=8080
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m appuser && chown -R appuser /app
USER appuser
CMD ["python", "app.py"]
