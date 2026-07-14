FROM python:3.12-slim

# Evita archivos .pyc y fuerza salida inmediata de logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Dependencias del sistema
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Instalar dependencias Python
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copiar proyecto
COPY . .

# Puerto
EXPOSE 8000

CMD ["uvicorn", "api2:app", "--host", "0.0.0.0", "--port", "8000"]
