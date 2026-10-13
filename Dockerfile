FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 TZ=America/Sao_Paulo
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY mo_obrigacoes ./mo_obrigacoes
EXPOSE 8000
CMD ["python", "-m", "mo_obrigacoes", "serve", "--porta", "8000"]
