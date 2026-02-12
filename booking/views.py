import random
import string
import qrcode
import base64
from io import BytesIO
from datetime import datetime, timedelta

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from django.conf import settings
from django.urls import reverse
from django.http import HttpResponseRedirect

from linebot import LineBotApi
from linebot.models import TextSendMessage

# Models
from booking.forms import RefundForm
from car_rental.models import (
    Car, GuestCustomer, Promotion, PlatformSetting, 
    Booking, PromotionUsage, Review, RenterReview, 
    BookingInspection, RenterReply, ReviewReply, 
    Payment, 
    PromotionUsage
)
from car_rental.forms import InspectionForm
from booking.utils import generate_promptpay_payload
from django.utils.translation import gettext as _
# ✅ สร้างฟังก์ชันช่วยส่ง LINE (จะได้เรียกใช้ง่ายๆ)
def send_line_push(user_line_id, message_text):
    if not user_line_id:
        return
    
    line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
    try:
        line_bot_api.push_message(user_line_id, TextSendMessage(text=message_text))
        print(f"ส่ง LINE สำเร็จ: {user_line_id}")
    except Exception as e:
        print(f"ส่ง LINE ผิดพลาด: {e}")


def user_info(request, car_id):
    car = get_object_or_404(Car, id=car_id)

    # ป้องกันเจ้าของรถจองรถตัวเอง
    if car.owner == request.user:
        messages.error(request, "คุณไม่สามารถจองรถของตัวเองได้")
        return redirect('car_detail', car_id=car.id)
    
    # รับค่าจาก URL (Query Params)
    pickup_str = request.GET.get("pickup_datetime")
    dropoff_str = request.GET.get("dropoff_datetime")
    location = request.GET.get("location", "กรุงเทพฯ")

    # แปลง String เป็น DateTime
    try:
        pickup_datetime = datetime.fromisoformat(pickup_str)
        dropoff_datetime = datetime.fromisoformat(dropoff_str)
    except (ValueError, TypeError):
        pickup_datetime = datetime.now() + timedelta(days=1)
        dropoff_datetime = datetime.now() + timedelta(days=4)

    # คำนวณวันและราคา
    rental_duration = dropoff_datetime - pickup_datetime
    rental_days = rental_duration.days + (1 if rental_duration.seconds > 0 else 0)
    if rental_days < 1: rental_days = 1 # กันติดลบ
    original_total_price = float(car.price_per_day * rental_days)
    

    # เช็คว่าส่วนลดใน session เป็นของรถคันนี้จริงๆ (กันลูกค้าเปลี่ยนรถแต่ส่วนลดค้าง)
    # 3. 🟢 ส่วนที่แก้ไข: คำนวณส่วนลดใหม่ (Re-calculate Logic)
    discount_amount = 0
    applied_code = request.session.get('booking_promo_code') # ดึงโค้ดที่เพิ่งใส่มาจาก Session

    if applied_code:
        try:
            # ดึง Object จริงจาก DB มาคำนวณ
            promo = Promotion.objects.get(code=applied_code, is_active=True)
            
            # เช็คเงื่อนไขซ้ำ (เผื่อหมดอายุระหว่างที่กดเล่น)
            now = timezone.now().date()
            valid_date = promo.start_date <= now <= promo.end_date
            valid_limit = promo.used_count < promo.usage_limit

            if valid_date and valid_limit:
                # ✅ คำนวณยอดลดตามเปอร์เซ็นต์ (discount_rate)
                # สูตร: ราคารวม x (เปอร์เซ็นต์ / 100)
                discount_amount = original_total_price * (float(promo.discount_rate) / 100)
                
                # กันส่วนลดเกินราคาจริง
                if discount_amount > original_total_price:
                    discount_amount = original_total_price
            else:
                # ถ้าโค้ดไม่ผ่านเกณฑ์แล้ว ให้ลบออกจาก session เงียบๆ
                del request.session['booking_promo_code']
                applied_code = None
                
        except Promotion.DoesNotExist:
            del request.session['booking_promo_code']
            applied_code = None

    # 1. คำนวณค่าเช่าหลังหักส่วนลด
    rental_price_after_discount = original_total_price - discount_amount
    if rental_price_after_discount < 0: rental_price_after_discount = 0

    # 2. ดึงค่ามัดจำ (Security Deposit)
    security_deposit = float(car.deposit) if car.deposit else 0

    # 3. ✅ ราคาสุทธิ = (ค่าเช่าหลังลด) + ค่ามัดจำ
    final_total_price = rental_price_after_discount + security_deposit


    # 📌 จุดสำคัญ 1: บันทึก "บริบทการจอง" ลง Session เสมอ
    request.session['booking_context'] = {
        'car_id': car.id,
        'pickup_datetime': pickup_datetime.isoformat(),
        'dropoff_datetime': dropoff_datetime.isoformat(),
        'location': location,
        
        # เก็บค่าต่างๆ แยกกันให้ชัดเจน
        'original_total_price': original_total_price,       # ค่าเช่าเต็ม
        'discount_amount': discount_amount,                 # ยอดส่วนลด
        'rental_price_after_discount': rental_price_after_discount, # ค่าเช่าหลังลด
        'security_deposit': security_deposit,               # ค่ามัดจำ
        'total_price': final_total_price,                   # ยอดรวมสุทธิ (ใช้โชว์และบันทึก)
        
        'applied_promo_code': applied_code,
        'rental_days': rental_days
    }

    # กรณีลูกค้ากด Submit (POST) ไปหน้า Checkout
    if request.method == "POST":
        request.session['guest_info_temp'] = {
            'first_name': request.POST.get("first_name"),
            'last_name': request.POST.get("last_name"),
            'email': request.POST.get("email"),
            'phone_number': request.POST.get("phone_number"),
            'license_number': request.POST.get("license_number")
        }
        return redirect('checkout', car_id=car.id)

    context = {
        "car": car,
        "pickup_datetime": pickup_datetime,
        "dropoff_datetime": dropoff_datetime,
        "location": location,
        "rental_days": rental_days,
        
        # ส่งตัวแปรไปหน้า HTML
        "original_total_price": original_total_price,
        "discount_amount": discount_amount,
        "rental_price_after_discount": rental_price_after_discount,
        "security_deposit": security_deposit,
        "total_price": final_total_price,
        "applied_code": applied_code,
    }
    return render(request, "booking/user_info.html", context)


def checkout(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    
    # 📌 จุดสำคัญ 2: ดึงข้อมูลจาก Session มาแสดง (ไม่ใช่ค่าจำลอง)
    booking_data = request.session.get('booking_context')
    guest_info = request.session.get('guest_info_temp')
    # ถ้าไม่มีข้อมูลใน Session หรือเป็นรถคนละคัน ให้กลับไปหน้า Detail
    if not booking_data or booking_data['car_id'] != car.id:
        return redirect('car_detail', car_id=car.id)

    # =======================================================
    # ✅ ส่วนที่ต้องเพิ่ม: จัดการเมื่อลูกค้ากดปุ่ม "ยืนยันการจอง"
    # =======================================================
    if request.method == "POST":
        
        # 1. ✅ จัดการ User (แยก Member กับ Guest)
        user_instance = None
        if request.user.is_authenticated:
            user_instance = request.user
        
        # 2. ✅ จัดการ Guest Info (สร้างเฉพาะตอนที่ไม่ได้ Login หรือเป็น Guest)
        guest_instance = None
        # ถ้าไม่ได้ Login และมีข้อมูล Guest ส่งมา
        if not user_instance and guest_info and guest_info.get('first_name'):
            guest_instance = GuestCustomer.objects.create(
                first_name=guest_info['first_name'],
                last_name=guest_info['last_name'],
                email=guest_info['email'],
                phone_number=guest_info['phone_number'],
                license_number=guest_info['license_number']
            )
            
        ref_code = 'BK-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        # =========================================================
        #  เตรียมข้อมูลโปรโมชั่นและเช็คสิทธิ์ซ้ำ
        # =========================================================
        applied_code = booking_data.get('applied_promo_code')
        promo_instance = None

        if applied_code:
            try:
                # ดึง Object โปรโมชั่นจาก DB
                promo_instance = Promotion.objects.get(code=applied_code)
                
                # เช็คว่า สมาชิกคนนี้เคยใช้ไปหรือยัง? (Double Check ก่อนบันทึก)
                if request.user.is_authenticated:
                    if PromotionUsage.objects.filter(user=request.user, promotion=promo_instance).exists():
                        messages.error(request, "เกิดข้อผิดพลาด: คุณใช้สิทธิ์โค้ดนี้ไปแล้ว (จำกัด 1 สิทธิ์/คน)")
                        # เด้งกลับไปหน้าเดิม ไม่บันทึก Booking
                        return redirect('user_info', car_id=car.id)

            except Promotion.DoesNotExist:
                # ถ้าหาไม่เจอ ให้ถือว่าไม่มีโปรโมชั่น (แต่ยอมให้จองต่อได้ในราคาเต็ม หรือจะ Error ก็ได้)
                promo_instance = None
        # =========================================================
        # 4. บันทึกการจองลง Database
        booking = Booking.objects.create(
            booking_ref=ref_code,   # ✅ เพิ่ม: บันทึกเลข Ref
            car=car,
            user=user_instance,
            guest=guest_instance,
            pickup_datetime=datetime.fromisoformat(booking_data['pickup_datetime']),
            dropoff_datetime=datetime.fromisoformat(booking_data['dropoff_datetime']),
            location=booking_data['location'],
            total_price=booking_data['total_price'],
            discount_amount=booking_data.get('discount_amount', 0), # ✅ เพิ่ม: บันทึกยอดส่วนลด
            deposit_amount=booking_data['total_price'] * 0.15, # คำนวณมัดจำ 15%
            status='pending' # <--- สำคัญ! ต้องตั้งเป็น "รออนุมัติ"

        )
        # =========================================================
        # 
        # สั่งให้ระบบนับจำนวน +1 ตรงนี้ครับ
        # =========================================================
        if promo_instance:
            # 1. บวกเลขจำนวนคนใช้เพิ่มไป 1
            promo_instance.used_count = promo_instance.used_count + 1
            promo_instance.save()  # <--- สำคัญมาก! ต้อง Save ไม่งั้นตัวเลขไม่เปลี่ยนใน Database

            # 2. (Optional) บันทึกว่า User คนนี้ใช้แล้ว (เพื่อป้องกันการใช้ซ้ำในอนาคต)
            if request.user.is_authenticated:
                 # อย่าลืม import PromotionUsage มาก่อนนะครับ
                 PromotionUsage.objects.get_or_create(user=request.user, promotion=promo_instance)
        # =========================================================

        # 3. ล้างข้อมูลใน Session ทิ้ง (เพราะบันทึกลง DB แล้ว)
        if 'booking_context' in request.session: del request.session['booking_context']
        if 'guest_info_temp' in request.session: del request.session['guest_info_temp']

        # 4. แจ้งเตือนและส่งไปหน้าประวัติการจอง
        if request.user.is_authenticated:
            # 👉 สมาชิก: ให้ไปหน้า "ประวัติการจอง" ได้เลย
            messages.success(request, "ส่งคำขอจองเรียบร้อย! คุณสามารถติดตามสถานะได้ที่หน้านี้")
            return redirect('booking_history')
        else:
            # 👉 ลูกค้าทั่วไป: ต้องไปหน้า "จองสำเร็จ" เพื่อดูเลข Ref Code
            # (ไม่ต้องใช้ messages ก็ได้ เพราะหน้า success จะโชว์รายละเอียดอยู่แล้ว)
            return redirect('booking_success', booking_id=booking.id)
    
    context = {
        'car': car,
        'pickup_datetime': datetime.fromisoformat(booking_data['pickup_datetime']),
        'dropoff_datetime': datetime.fromisoformat(booking_data['dropoff_datetime']),
        'location': booking_data['location'],
        'rental_days': booking_data['rental_days'],
        'total_price': booking_data['total_price'],
        'original_total_price': booking_data.get('original_total_price', booking_data['total_price']), # ราคาเต็ม
        'discount_amount': booking_data.get('discount_amount', 0),       # ยอดที่ลด
        'applied_code': booking_data.get('applied_promo_code', ''),      # โค้ดที่ใช้
        
        'guest_info': guest_info # (ถ้ามี)
    }
    return render(request, 'booking/checkout.html', context)

# 3. หน้าเลือกวิธีชำระเงิน (Payment - มัดจำ)
# booking/views.py

def payment_page(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    
    # 1. ความปลอดภัย
    if request.user.is_authenticated:
        if booking.user != request.user:
            return redirect('booking_history')
    else:
        if booking.user is not None:
             return redirect('car_list')
    
    # 2. เช็คสถานะ
    if booking.status not in ['approved', 'waiting_payment']:
        messages.warning(request, "รายการนี้ไม่ได้อยู่ในสถานะรอชำระเงิน")
        return redirect('car_list')

    # =========================================================
    # 💰 แก้ไขสูตรคำนวณเงิน + ปัดเศษ 2 ตำแหน่ง (Fix Decimal)
    # =========================================================
    
    # 1. ดึงค่ามัดจำ (Security Deposit)
    security_deposit = float(booking.car.deposit) if booking.car.deposit else 0.0
    
    # 2. หา "ค่าเช่าสุทธิ" (Net Rental Price) 
    # booking.total_price คือยอดรวมทั้งหมด ดังนั้นต้องถอดมัดจำออกก่อน
    rental_net = float(booking.total_price) - security_deposit
    
    # กันพลาด: ถ้าติดลบให้เป็น 0 และปัดเศษทันที
    if rental_net < 0: rental_net = 0.0
    rental_net = round(rental_net, 2)

    discount = float(booking.discount_amount)
    rental_gross_price = round(rental_net + discount, 2)  # บวกกลับแล้วปัดเศษให้เป๊ะ
    # 3. คำนวณยอดที่ต้องจ่ายผ่าน QR (Platform Fee 15%)
    # คิดจากค่าเช่าสุทธิ * 0.15 แล้วปัดเศษ 2 ตำแหน่ง
    platform_fee = round(rental_net * 0.15, 2)

    # 4. คำนวณยอดจ่ายหน้างาน (Pay on Arrival)
    # สูตร: (ค่าเช่าสุทธิ - 15%) + มัดจำ
    # ต้องปัดเศษในวงเล็บก่อน แล้วค่อยบวก
    remaining_rent = round(rental_net - platform_fee, 2)
    pay_on_arrival = round(remaining_rent + security_deposit, 2)

    
    PAYMENT_TIMEOUT_MINUTES = 60  # ⏳ กำหนดเวลาให้โอนภายใน 60 นาที
    
    # สร้างหรือดึงข้อมูลการชำระเงิน (get_or_create)
    payment_obj, created = Payment.objects.get_or_create(
        booking=booking,
        defaults={
            'amount': platform_fee, 
            'payment_method': 'QR_PROMPTPAY',
            'payment_status': 'PENDING',
            # ✅ ตั้งเวลาหมดอายุทันทีที่สร้าง record นี้ครั้งแรก
            'expire_at': timezone.now() + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES)
        }
    )
    # ตรวจสอบว่ายอดใน Database ตรงกับที่คำนวณใหม่ไหม (เผื่อเศษสตางค์ไม่ตรง)
    # ใช้ abs() < 0.01 เพื่อเปรียบเทียบค่า float
    if abs(float(payment_obj.amount) - platform_fee) > 0.01:
        payment_obj.amount = platform_fee
        payment_obj.save()

    # 🔴 เพิ่มตรงนี้: เช็คว่าหมดเวลาหรือยัง? (Auto Cancel)
    # ถ้าสถานะยังเป็น PENDING และเวลาปัจจุบัน เลยเวลา expire_at ไปแล้ว
    if payment_obj.payment_status == 'PENDING' and timezone.now() > payment_obj.expire_at:
        
        # เปลี่ยนสถานะ Booking เป็น Cancelled
        booking.status = 'cancelled'
        booking.save()
        
        # เปลี่ยนสถานะ Payment เป็น Expired
        payment_obj.payment_status = 'EXPIRED'
        payment_obj.save()
        
        messages.error(request, "❌ หมดเวลาชำระเงินแล้ว รายการจองถูกยกเลิกอัตโนมัติ")
        if booking.user:
            return redirect('booking_history')
        else:
            return redirect('booking_detail', booking_id=booking.id)
    # =========================================================
    # 📤 ส่วนจัดการอัปโหลดสลิป (POST Request)
    # =========================================================
    if request.method == "POST" and request.FILES.get('slip_image'):
        if payment_obj.is_expired:
             messages.error(request, "หมดเวลาชำระเงิน กรุณารีเฟรชหน้าจอ")
             return redirect('payment_page', booking_id=booking.id)
        
        payment_obj.slip_image = request.FILES['slip_image']
        payment_obj.payment_status = 'WAITING_VERIFY'
        payment_obj.save()
        
        booking.status = 'waiting_verify' 
        booking.save()
        
        messages.success(request, "แจ้งชำระเงินเรียบร้อย รอเจ้าของรถตรวจสอบ")
        if booking.user: 
            # ถ้าใน Booking มีข้อมูล User ใส่ไว้ = "สมาชิก"
            return redirect('booking_history')
        
    
        else:
            # ถ้าไม่มี User (แสดงว่าเป็น Guest) = "ลูกค้าทั่วไป"
            # ให้ส่งกลับไปหน้าเดิม หรือหน้า Detail พร้อม ID
            return redirect('booking_detail', booking_id=booking.id)

    # --- สร้าง QR Code (จากยอด platform_fee ที่ปัดเศษแล้ว) ---
    PROMPTPAY_ID = "0803508433" 
    img_str = ""
    try:
        payload = generate_promptpay_payload(PROMPTPAY_ID, float(payment_obj.amount))
        img = qrcode.make(payload)
        buffer = BytesIO()
        img.save(buffer, format="PNG")
        img_str = base64.b64encode(buffer.getvalue()).decode()
    except Exception as e:
        print(f"QR Error: {e}")

    time_remaining = (payment_obj.expire_at - timezone.now()).total_seconds()
    
    # 6. ส่งตัวแปรไปหน้าเว็บ
    context = {
        'booking': booking,
        'payment': payment_obj, 
        'rental_gross_price': rental_gross_price, # ✅ ใช้ตัวนี้แทนการบวกใน HTML
        # ส่งค่าที่ปัดเศษแล้วไปแสดงผล
        'rental_net_price': rental_net,       
        'platform_fee': platform_fee,         
        'security_deposit': security_deposit, 
        'pay_on_arrival': pay_on_arrival,     
        
        'qr_image': img_str,
        'time_remaining': int(time_remaining) if time_remaining > 0 else 0,
    }
    
    return render(request, 'booking/payment.html', context)



def booking_success(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    # เพิ่มความปลอดภัยนิดหน่อย: 
    # ถ้าเป็น Member แต่ดันหลงมาดู Booking ของคนอื่น -> ห้าม
    if request.user.is_authenticated and booking.user != request.user:
         return redirect('booking_history')
         
    # ถ้าเป็น Guest -> อนุญาตให้ดูได้เลย (เพราะเขารู้ Booking ID จากการ Redirect มา)
    return render(request, 'booking/booking_success.html', {'booking': booking})


# Helper Function ดึงค่าคอมมิชชั่น
def get_commission_rate():
    try:
        setting = PlatformSetting.objects.first()
        if setting:
            return float(setting.commission_rate)
    except:
        pass
    return 0.15 # ค่า Default กรณีลืมตั้งค่าใน Admin (กันระบบพัง)


def manage_booking(request):
    if request.method == 'POST':
        # รับค่าจากฟอร์ม
        ref_code = request.POST.get('booking_ref', '').strip()
        email_or_phone = request.POST.get('email_or_phone', '').strip()

        try:
            from django.db.models import Q
            
            booking = Booking.objects.get(
                Q(guest__email=email_or_phone) | Q(guest__phone_number=email_or_phone),
                booking_ref=ref_code
            )

            # 1. ดึงค่าเช่าตั้งต้น (จาก booking)
            # 1. ดึงค่าเช่า "รายวัน" จากโมเดล Car โดยตรง
            rental_price = float(booking.car.price_per_day)
            
            # 4. คำนวณมัดจำจอง 15% (คิดจากค่าเช่ารายวันตัวนี้)
            deposit_to_pay = rental_price * 0.15
            
            # 5. ค่าเช่าส่วนที่เหลือ (ค่าเช่ารายวัน - มัดจำที่จ่ายไป)
            remaining_rental = rental_price - deposit_to_pay
            
            # 6. ดึงค่ามัดจำรถ (เงินประกันที่จะคืนทีหลัง) จากโมเดล Car
            car_security_deposit = float(booking.car.deposit) if hasattr(booking.car, 'deposit') and booking.car.deposit else 0.0
            
            # 7. ยอดที่ต้องจ่ายหน้างาน = (ค่าเช่าส่วนที่เหลือ) + (ค่ามัดจำรถ)
            pay_on_arrival = remaining_rental + car_security_deposit
            
            # ======== นำค่าที่คำนวณไปยัดใส่ Object ========
            booking.deposit_amount = deposit_to_pay
            booking.remaining_balance = pay_on_arrival
            # ===============================================
            
            # ส่งไปหน้ารายละเอียด
            return render(request, 'booking/booking_detail.html', {'booking': booking})

        except Booking.DoesNotExist:
            # ถ้าไม่เจอ -> แจ้งเตือน
            error_message = "ไม่พบข้อมูลการจอง หรือข้อมูลยืนยันตัวตนไม่ถูกต้อง"
            return render(request, 'booking/manage_booking.html', {'error': error_message})
    # ถ้าเป็น GET (เปิดหน้าเว็บเฉยๆ)
    return render(request, 'booking/manage_booking.html')

# views.py



def booking_detail(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    return render(request, 'booking/booking_detail.html', {'booking': booking})


@login_required
def booking_history(request):
    # ดึงการจองของ user คนนี้ + เรียงจากล่าสุดไปเก่าสุด
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'booking/booking_history.html', {'bookings': bookings})


#(ตอนเจ้าของกดอนุมัติ)

@login_required
def booking_requests(request):
    # ดึงเฉพาะรายการที่รออนุมัติ (Pending)
    pending_bookings = Booking.objects.filter(
        car__owner=request.user, 
        status='pending'
    ).order_by('created_at')

    return render(request, 'booking/booking_requests.html', {
        'pending_bookings': pending_bookings
    })

@login_required
def manage_bookings(request):
    # ดึง Booking ทั้งหมดของรถเรา (ไม่กรองสถานะ) เรียงจากใหม่ไปเก่า
    all_bookings = Booking.objects.filter(car__owner=request.user).order_by('-created_at')
    
    return render(request, 'booking/manage_bookings.html', {
        'bookings': all_bookings
    })


# ฟังก์ชันนี้รองรับการกดปุ่มทุกปุ่ม (อนุมัติ, ปฏิเสธ, รับรถ, คืนรถ)
@login_required
def update_booking_status(request, booking_id, action):
    # ดึง Booking และตรวจสอบว่าเป็นรถของเราจริงไหม
    booking = get_object_or_404(Booking, id=booking_id, car__owner=request.user)

    # 1. กรณีเจ้าของกด "อนุมัติ"
    if action == 'approve':
        booking.status = 'approved'
        messages.success(request, f"อนุมัติการจอง {booking.booking_ref} แล้ว (รอลูกค้าชำระเงิน)")
        #แจ้งเตือนลูกค้าทาง LINE
        if booking.user and hasattr(booking.user, 'profile') and booking.user.profile.line_id:
            msg = (
                f"✅ การจอง {booking.booking_ref} ได้รับการอนุมัติแล้ว!\n"
                f"รถ: {booking.car.brand} {booking.car.model}\n"
                f"กรุณาชำระเงินมัดจำเพื่อยืนยันการจอง"
            )
            send_line_push(booking.user.profile.line_id, msg)

    # 2. กรณีเจ้าของกด "ปฏิเสธ"
    elif action == 'reject':
        booking.status = 'rejected'
        messages.warning(request, f"ปฏิเสธการจอง {booking.booking_ref} แล้ว")
        #  แจ้งเตือนลูกค้าว่าถูกปฏิเสธ
        if booking.user and hasattr(booking.user, 'profile') and booking.user.profile.line_id:
            msg = f"❌ ขออภัย การจอง {booking.booking_ref} ไม่ได้รับการอนุมัติจากเจ้าของรถ"
            send_line_push(booking.user.profile.line_id, msg)

    # 3. กรณีเจ้าของกด "รับรถแล้ว" (ปกติจะผ่านหน้า Inspection มา แต่เผื่อไว้)
    elif action == 'picked_up':
        booking.status = 'picked_up'
        messages.info(request, "บันทึกสถานะ: ลูกค้ารับรถไปแล้ว")

    # 4. ✅ กรณีเจ้าของกด "จบงาน" (คืนรถ) ** จุดที่คุณขาดไป **
    elif action == 'completed':
        booking.status = 'completed'
        messages.success(request, "บันทึกสถานะ: คืนรถเรียบร้อย (จบงาน)")

    booking.save()
    
    # ทำเสร็จแล้วให้เด้งกลับไปหน้าตารางจัดการ
    return redirect('manage_bookings')

# ยืนยันสภาพและส่งมอบรถ
@login_required
def inspection_page(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, car__owner=request.user)
    
    # ถ้ามีการอัปโหลดรูป (POST)
    if request.method == 'POST':
        if 'upload_image' in request.POST:
            form = InspectionForm(request.POST, request.FILES)
            if form.is_valid():
                inspection = form.save(commit=False)
                inspection.booking = booking
                inspection.save()
                messages.success(request, "บันทึกรูปภาพแล้ว")
                return redirect('inspection_page', booking_id=booking.id)
        
        elif 'confirm_delivery' in request.POST:
            # กดปุ่มยืนยัน -> เปลี่ยนสถานะเป็น picked_up
            booking.status = 'picked_up'
            booking.save()
            messages.success(request, "ยืนยันการส่งมอบรถเรียบร้อยแล้ว")
            return redirect('manage_bookings') # กลับไปหน้าจัดการ

    else:
        form = InspectionForm()

    # ดึงรูปที่เคยอัปโหลดไว้แล้วมาโชว์
    existing_inspections = booking.inspections.all()

    return render(request, 'booking/inspection.html', {
        'booking': booking,
        'form': form,
        'existing_inspections': existing_inspections
    })


# 1. ฟังก์ชันลูกค้ารีวิวรถ
@login_required
def submit_car_review(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # 1. เช็คสถานะ
    if booking.status != 'completed':
        messages.error(request, "ต้องจบงานก่อนจึงจะรีวิวได้")
        return redirect('booking_history')

    # 2. ✅ เช็คว่าเคยรีวิวไปแล้วหรือยัง? (กัน Error 500)
    # ใช้ hasattr เช็คว่า booking ก้อนนี้มี review ผูกอยู่ไหม
    if hasattr(booking, 'review'): 
        messages.warning(request, "คุณได้รีวิวรายการนี้ไปแล้ว")
        return redirect('booking_history')
        
    if request.method == "POST":
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        Review.objects.create(
            booking=booking,
            car=booking.car,
            user=request.user,
            rating=rating,
            comment=comment
        )
        messages.success(request, "รีวิวรถเรียบร้อยแล้ว!")
        
    return redirect('car_detail', car_id=booking.car.id)


# 2. ฟังก์ชันเจ้าของรีวิวลูกค้า
@login_required
def submit_renter_review(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, car__owner=request.user)
    
    # 1. เช็คสถานะ
    if booking.status != 'completed':
        messages.error(request, "ต้องจบงานก่อนจึงจะรีวิวลูกค้าได้")
        return redirect('manage_bookings') # ⚠️ เช็คชื่อ URL ให้ตรงกับ urls.py ของคุณ (มี s หรือไม่มี s)

    # 2. ✅ เช็คว่าเคยรีวิวไปแล้วหรือยัง?
    if hasattr(booking, 'renter_review'):
        messages.warning(request, "คุณได้รีวิวลูกค้ารายนี้ไปแล้ว")
        return redirect('manage_bookings')
        
    if request.method == "POST":
        rating = request.POST.get('rating')
        comment = request.POST.get('comment')
        
        RenterReview.objects.create(
            booking=booking,
            renter=booking.user,
            owner=request.user,
            rating=rating,
            comment=comment
        )
        messages.success(request, "รีวิวลูกค้าเรียบร้อยแล้ว!")
        
    return redirect('public_profile', user_id=booking.user.id)

# 1. ฟังก์ชันรับค่าจากปุ่ม "ใช้โค้ด"
def apply_promotion(request, car_id):
    # เตรียม URL เดิม (user_info)
    booking_data = request.session.get('booking_context')
    if not booking_data:
        return redirect('car_detail', car_id=car_id)

    # สร้าง URL Redirect กลับ (พร้อมวันที่)
    query_params = f"?pickup_datetime={booking_data['pickup_datetime']}&dropoff_datetime={booking_data['dropoff_datetime']}&location={booking_data['location']}"
    redirect_url = f"/booking/user-info/{car_id}/{query_params}" # ตรวจสอบ URL path ของคุณให้ตรง

    if request.method == 'POST':
        code = request.POST.get('promo_code', '').strip().upper()
        
        try:
            # 1. ค้นหาคูปอง
            now = timezone.now().date()
            promo = Promotion.objects.get(
                code=code, 
                is_active=True,
                start_date__lte=now, 
                end_date__gte=now
            )
            
            # 2. เช็คสิทธิ์การใช้งาน
            if promo.used_count >= promo.usage_limit:
                messages.error(request, "คูปองนี้สิทธิ์เต็มแล้ว", extra_tags='promo')
                return redirect(redirect_url)

            # 3. ✅ เช็คว่า "คนนี้" เคยใช้ไปหรือยัง (เพิ่มใหม่)
            if request.user.is_authenticated:
                # ถ้าเคยมีประวัติการใช้ -> ห้ามใช้
                if PromotionUsage.objects.filter(user=request.user, promotion=promo).exists():
                    messages.error(request, "คุณใช้สิทธิ์โค้ดนี้ไปแล้ว (จำกัด 1 คน/สิทธิ์)", extra_tags='promo')
                    return redirect(redirect_url)

            # 4. บันทึก
            request.session['booking_promo_code'] = promo.code
            messages.success(request, f"ใช้โค้ด {promo.code} สำเร็จ!", extra_tags='promo')
            
        except Promotion.DoesNotExist:
            messages.error(request, "ไม่พบรหัสโปรโมชั่น หรือหมดอายุแล้ว", extra_tags='promo')
            
    return redirect(redirect_url)

# 2. ฟังก์ชันยกเลิกโค้ด (เผื่อลูกค้าอยากเปลี่ยน)
def remove_promotion(request, car_id):
    # 1. ลบโค้ดออกจาก Session
    if 'booking_promo_code' in request.session:
        del request.session['booking_promo_code']
        messages.info(request, "ยกเลิกการใช้คูปองแล้ว")
    
    # 2. ✅ ดึงข้อมูลการจองเดิม (วันที่/สถานที่) จาก Session เพื่อส่งกลับไป
    booking_data = request.session.get('booking_context')
    
    if booking_data:
        # สร้าง URL พร้อมแนบ Query Parameters เดิมกลับไป
        # (ต้อง import reverse จาก django.urls ก่อนนะครับ ถ้ายังไม่มี)
        from django.urls import reverse
        from django.http import HttpResponseRedirect
        
        base_url = reverse('user_info', kwargs={'car_id': car_id})
        query_params = f"?pickup_datetime={booking_data['pickup_datetime']}&dropoff_datetime={booking_data['dropoff_datetime']}&location={booking_data['location']}"
        
        return HttpResponseRedirect(base_url + query_params)

    # กรณีไม่มี Session (หายาก แต่กันไว้) ให้กลับไปแบบธรรมดา
    return redirect('user_info', car_id=car_id)

# booking/views.py

@login_required
def cancel_booking(request, booking_id):
    # 1. ดึงข้อมูลและเช็คว่าเป็นเจ้าของ Booking จริงไหม
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    # 2. เช็ค: ห้ามยกเลิกถ้ารับรถไปแล้ว หรือจบงานแล้ว หรือยกเลิกไปแล้ว
    if booking.status in ['picked_up', 'completed', 'cancelled', 'rejected']:
        messages.error(request, "ไม่สามารถยกเลิกรายการนี้ได้")
        return redirect('booking_history')

    # 3. Logic การยกเลิก
    # 3.1 กรณี: ยังไม่จ่ายเงิน (Pending, Approved, Waiting Payment)
    if booking.status in ['pending', 'approved', 'waiting_payment']:
        booking.status = 'cancelled'
        booking.save()
        
        # ถ้ามีบิลค้างอยู่ ให้ปรับเป็น Cancelled ด้วย
        if hasattr(booking, 'payment'):
            booking.payment.payment_status = 'CANCELLED' # หรือ FAILED แล้วแต่ Choice ที่คุณมี
            booking.payment.save()
            
        messages.success(request, "ยกเลิกการจองเรียบร้อยแล้ว")

    # 3.2 กรณี: จ่ายเงินแล้ว (Waiting Verify, Confirmed)
    elif booking.status in ['waiting_verify', 'confirmed']:
        booking.status = 'cancelled' 
        booking.save()
        
        # แจ้งเตือนเรื่องเงินคืน
        messages.warning(request, "ยกเลิกการจองสำเร็จ! เนื่องจากคุณได้ชำระเงินแล้ว กรุณาติดต่อเจ้าของรถหรือแอดมินเพื่อดำเนินการเรื่องการคืนเงิน")

    return redirect('booking_history')


def request_refund(request, booking_id):
    if request.user.is_authenticated:
        # กรณีสมาชิก: ต้องเช็คว่าเป็นเจ้าของ booking นี้จริงๆ
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    else:
        # กรณี Guest: ดึงจาก ID อย่างเดียว (และต้องเป็น booking ที่ไม่มี user ผูก)
        booking = get_object_or_404(Booking, id=booking_id, user__isnull=True)
    
    # เช็คสถานะการจ่ายเงิน
    if booking.status not in ['confirmed', 'waiting_verify', 'approved', 'pending']:
        messages.error(request,_("รายการนี้ไม่สามารถขอคืนเงินได้"))
        if request.user.is_authenticated:
            return redirect('booking_history')
        else:
            return redirect('booking_detail', booking_id=booking.id)

    # ==========================================
    # 💰 LOGIC คำนวณเงินคืน (Cancellation Policy)
    # ==========================================
    now = timezone.now()
    pickup_time = booking.pickup_datetime
    
    # หาผลต่างเวลา (Time Difference)
    time_diff = pickup_time - now
    hours_until_pickup = time_diff.total_seconds() / 3600
    
    # ดึงยอดที่ลูกค้าจ่ายมาจริง (จาก Payment)
    paid_amount = 0
    if hasattr(booking, 'payment'):
        paid_amount = float(booking.payment.amount)

    refund_amount = 0
    policy_message = ""
    is_refundable = False

    # --- กฎการคืนเงิน ---
    if hours_until_pickup >= 24:
        # กรณี 1: ยกเลิกก่อน 24 ชม. -> คืน 100%
        refund_amount = paid_amount
        is_refundable = True
        policy_message =_("ยกเลิกก่อนกำหนด 24 ชม. ได้รับเงินคืนเต็มจำนวน")
        
    elif hours_until_pickup > 0:
        # กรณี 2: ยกเลิกกะทันหัน (น้อยกว่า 24 ชม.) -> ไม่คืน หรือคืน 50% แล้วแต่คุณ
        refund_amount = 0 # หรือ paid_amount * 0.5
        is_refundable = False # ถ้า false ปุ่มกดจะเปลี่ยนไป
        policy_message = _("เนื่องจากยกเลิกช้ากว่ากำหนด (น้อยกว่า 24 ชม.) จะไม่ได้รับเงินคืน")
        
    else:
        # กรณี 3: เลยเวลารับรถไปแล้ว
        refund_amount = 0
        is_refundable = False
        policy_message = _("เลยเวลารับรถแล้ว ไม่สามารถขอเงินคืนได้")

    # ==========================================

    if request.method == 'POST':
        # ถ้าลูกค้ากด "ยืนยัน" แม้ว่าจะไม่ได้เงินคืน (เช่น อยากยกเลิกเฉยๆ)
        form = RefundForm(request.POST, instance=booking)
        if form.is_valid():
            if refund_amount > 0:
                # กรณีได้เงินคืน: ส่งเรื่องให้แอดมิน (รอคืนเงิน)
                booking.status = 'refund_requested'
                msg_display = _("ส่งคำร้องขอคืนเงินเรียบร้อย เจ้าหน้าที่จะดำเนินการโอนเงินคืนให้ท่าน")
            else:
                # กรณีไม่ได้เงินคืน: ยกเลิกรายการทันที (ไม่ต้องรอแอดมิน)
                booking.status = 'cancelled'
                msg_display = _("ยกเลิกรายการจองเรียบร้อยแล้ว (รายการนี้ไม่เข้าเงื่อนไขการรับเงินคืน)")

            booking.save()
            
            # บันทึกยอดที่ระบบคำนวณได้ลง log หรือส่งไลน์บอกแอดมินก็ได้
            msg_success = _("ส่งคำร้องเรียบร้อย")
            messages.success(request, f"{msg_success} ({policy_message})")
            if request.user.is_authenticated:
                return redirect('booking_history')
            else:
                return redirect('booking_detail', booking_id=booking.id)
    else:
        form = RefundForm(instance=booking)

    # แปลงตัวเลขเป็น String สวยๆ แบบมีลูกน้ำและทศนิยม 2 ตำแหน่ง
    # เช่น 1500.0 -> "1,500.00"
    refund_amount_str = f"{refund_amount:,.2f}"
    paid_amount_str = f"{paid_amount:,.2f}"

    context = {
        'form': form,
        'booking': booking,
        # ส่งค่าตัวเลขดิบๆ ไปเช็คเงื่อนไข if
        'refund_amount_val': refund_amount, 
        # ส่งค่าข้อความสวยๆ ไปแสดงผล
        'refund_amount_display': refund_amount_str,
        'paid_amount_display': paid_amount_str,
        'policy_message': policy_message,
    }

    return render(request, 'booking/refund_request.html', context)

def cancel_booking_immediately(request, booking_id):
    # 1. ดึงข้อมูลแบบเดียวกับที่คุณทำ
    if request.user.is_authenticated:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    else:
        booking = get_object_or_404(Booking, id=booking_id, user__isnull=True)

    # 2. เช็คว่าสถานะควรจะยกเลิกได้เลยไหม (เช่น ยังไม่จ่าย หรือ โดนปฏิเสธ)
    if booking.status in ['pending', 'approved']:
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, _("ยกเลิกรายการจองเรียบร้อยแล้ว"))
    else:
        messages.error(request, _("ไม่สามารถยกเลิกรายการนี้ได้โดยตรง"))

    # 3. Redirect กลับหน้าเดิม
    if request.user.is_authenticated:
        return redirect('booking_history')
    else:
        return redirect('booking_detail', booking_id=booking.id)
