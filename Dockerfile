# Python 3.13 slim image
FROM python:3.13-slim

# Paketlarni o'rnatish
RUN apt-get update && apt-get install -y --no-install-recommends \
    git curl build-essential libssl-dev zlib1g-dev \
    libbz2-dev libreadline-dev libsqlite3-dev wget \
    libncurses5-dev libncursesw5-dev xz-utils tk-dev \
    libffi-dev liblzma-dev python3-openssl libgdbm-dev libnss3-dev \
    && rm -rf /var/lib/apt/lists/*

# Ishlash papkasi
WORKDIR /app

# Loyihani containerga ko'chirish
COPY . /app

# Python paketlarini o‘rnatish
RUN pip install --no-cache-dir -r requirements.txt

# Bot ishga tushadigan buyruq
CMD ["python", "bot.py"]
