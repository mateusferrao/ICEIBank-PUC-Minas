# Imagem de uma agência do ICEIBank. O mesmo código roda 3 vezes (containers
# diferentes), identificado por AGENCIA_ID. Preparação para o Sprint 4 (Nuvem).
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src ./src
COPY mesclar_logs.py .

# Porta padrão da agência 0; cada serviço no docker-compose sobrescreve o
# comando com a porta correta (4000 + AGENCIA_ID).
EXPOSE 4000
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "4000"]
