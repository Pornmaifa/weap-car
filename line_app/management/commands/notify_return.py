from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
# 👇 Import Booking จากแอปที่เก็บ Model (ถ้า Model อยู่ car_rental ก็ใช้ car_rental ตามเดิมครับ)
from car_rental.models import Booking  
from linebot import LineBotApi
from linebot.models import TextSendMessage
from datetime import timedelta

class Command(BaseCommand):
    help = 'แจ้งเตือนลูกค้าล่วงหน้า 1 วันก่อนคืนรถ (เก็บไว้ใน line_app)'

    def handle(self, *args, **kwargs):
        # 1. หาวันที่ "พรุ่งนี้"
        now = timezone.now()
        tomorrow = now.date() + timedelta(days=1)
        
        self.stdout.write(f"--- [Line App] เริ่มตรวจสอบการคืนรถสำหรับวันที่: {tomorrow} ---")

        # 2. ค้นหา Booking ที่ต้องคืนวันพรุ่งนี้
        bookings = Booking.objects.filter(
            dropoff_datetime__date=tomorrow,
            status__in=['picked_up', 'confirmed']
        )

        if not bookings.exists():
            self.stdout.write(self.style.WARNING("ไม่พบรายการที่ต้องคืนรถในวันพรุ่งนี้"))
            return

        # 3. เตรียมส่ง LINE
        line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
        count = 0

        # 4. วนลูปส่ง
        for booking in bookings:
            if booking.user and hasattr(booking.user, 'profile') and booking.user.profile.line_id:
                line_id = booking.user.profile.line_id
                
                msg_text = (
                    f"🔔 แจ้งเตือน: กำหนดคืนรถพรุ่งนี้\n"
                    f"รถ: {booking.car.brand} {booking.car.model}\n"
                    f"⏰ เวลาคืน: {booking.dropoff_datetime.strftime('%H:%M น.')}\n"
                    f"📍 สถานที่: {booking.location}\n\n"
                    f"โปรดตรวจสอบสัมภาระและเติมน้ำมันให้เรียบร้อยก่อนคืนรถนะครับ ขอบคุณครับ 🙏"
                )

                try:
                    line_bot_api.push_message(line_id, TextSendMessage(text=msg_text))
                    self.stdout.write(self.style.SUCCESS(f"✅ ส่งหาคุณ {booking.user.username} เรียบร้อย"))
                    count += 1
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"❌ ส่งไม่ผ่าน: {e}"))
            else:
                 self.stdout.write(self.style.WARNING(f"⚠️ User: {booking.user.username} ไม่ได้เชื่อมต่อ LINE"))

        self.stdout.write(self.style.SUCCESS(f"--- ส่งแจ้งเตือนทั้งหมด {count} รายการ ---"))