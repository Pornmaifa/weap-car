FROM python:3.11-slim

# ตั้งค่าพื้นที่ทำงานใน Container
WORKDIR /app

# ป้องกันไม่ให้ Python สร้างไฟล์ขยะ (.pyc) และล็อกการแสดงผล Log
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# ก๊อปปี้ไฟล์รายชื่อไลบรารีเข้ามาติดตั้งก่อน
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# ก๊อปปี้โค้ดทั้งหมดในโปรเจกต์ตามเข้ามา
COPY . /app/

# คำสั่งรัน Server จริงผ่าน Gunicorn (พอร์ต 8000)
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "car.wsgi:application"]