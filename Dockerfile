FROM python:3.11-slim

WORKDIR /app

# 1. ต้องสั่งติดตั้งเครื่องมือเสริมของ MySQL ตรงนี้ก่อนเลย (ห้ามไปอยู่ข้างล่าง)
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# 2. จากนั้นค่อยก๊อปปี้ไฟล์และสั่งติดตั้งไลบรารี Python
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# 3. ก๊อปปี้โค้ดทั้งหมดที่เหลือ
COPY . /app/

CMD python manage.py migrate && gunicorn car.wsgi:application --bind 0.0.0.0:8000