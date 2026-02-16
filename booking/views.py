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

# สร้างฟังก์ชันช่วยส่ง LINE (จะได้เรียกใช้ง่ายๆ)
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
    
    # รับค่าจาก URL 
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
    
    # คำนวณส่วนลด (ถ้ามี) โดยดึงโค้ดจาก Session
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

    # คำนวณค่าเช่าหลังหักส่วนลด
    rental_price_after_discount = original_total_price - discount_amount
    if rental_price_after_discount < 0: rental_price_after_discount = 0

    # ดึงค่ามัดจำ (Security Deposit)
    security_deposit = float(car.deposit) if car.deposit else 0

    #  ราคาสุทธิ = (ค่าเช่าหลังลด) + ค่ามัดจำ
    final_total_price = rental_price_after_discount + security_deposit

    #  บันทึก "บริบทการจอง" ลง Session เสมอ
    request.session['booking_context'] = {
        'car_id': car.id,
        'pickup_datetime': pickup_datetime.isoformat(),
        'dropoff_datetime': dropoff_datetime.isoformat(),
        'location': location,
        
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
    
    # ดึงข้อมูลจาก Session มาแสดง 
    booking_data = request.session.get('booking_context')
    guest_info = request.session.get('guest_info_temp')
    if not booking_data or booking_data['car_id'] != car.id:
        return redirect('car_detail', car_id=car.id)

    if request.method == "POST":
        
        # กรณีเป็นสมาชิก (Member)
        user_instance = None
        if request.user.is_authenticated:
            user_instance = request.user
        
        #  จัดการ Guest 
        guest_instance = None
        if not user_instance and guest_info and guest_info.get('first_name'):
            guest_instance = GuestCustomer.objects.create(
                first_name=guest_info['first_name'],
                last_name=guest_info['last_name'],
                email=guest_info['email'],
                phone_number=guest_info['phone_number'],
                license_number=guest_info['license_number']
            )
            
        ref_code = 'BK-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

        #  เตรียมข้อมูลโปรโมชั่นและเช็คสิทธิ์ซ้ำ
        applied_code = booking_data.get('applied_promo_code')
        promo_instance = None

        if applied_code:
            try:
                promo_instance = Promotion.objects.get(code=applied_code)
                # เช็คว่า สมาชิกคนนี้เคยใช้ไปหรือยัง? (Double Check ก่อนบันทึก)
                if request.user.is_authenticated:
                    if PromotionUsage.objects.filter(user=request.user, promotion=promo_instance).exists():
                        messages.error(request, "เกิดข้อผิดพลาด: คุณใช้สิทธิ์โค้ดนี้ไปแล้ว (จำกัด 1 สิทธิ์/คน)")
                        # เด้งกลับไปหน้าเดิม ไม่บันทึก Booking
                        return redirect('user_info', car_id=car.id)

            except Promotion.DoesNotExist:
                promo_instance = None
        #  บันทึกการจองลง Database
        booking = Booking.objects.create(
            booking_ref=ref_code,   #บันทึกเลข Ref
            car=car,
            user=user_instance,
            guest=guest_instance,
            pickup_datetime=datetime.fromisoformat(booking_data['pickup_datetime']),
            dropoff_datetime=datetime.fromisoformat(booking_data['dropoff_datetime']),
            location=booking_data['location'],
            total_price=booking_data['total_price'],
            discount_amount=booking_data.get('discount_amount', 0), 
            deposit_amount=booking_data['total_price'] * 0.15, 
            status='pending' #ตั้งเป็น "รออนุมัติ"

        )
        if promo_instance:
            # บวกเลขจำนวนคนใช้เพิ่มไป 1
            promo_instance.used_count = promo_instance.used_count + 1
            promo_instance.save() 

            #บันทึกว่า User คนนี้ใช้แล้ว 
            if request.user.is_authenticated:
                 PromotionUsage.objects.get_or_create(user=request.user, promotion=promo_instance)

        # ล้างข้อมูลใน Session 
        if 'booking_context' in request.session: del request.session['booking_context']
        if 'guest_info_temp' in request.session: del request.session['guest_info_temp']

        if request.user.is_authenticated:
            messages.success(request, "ส่งคำขอจองเรียบร้อย! คุณสามารถติดตามสถานะได้ที่หน้านี้")
            return redirect('booking_history')
        else:
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
        'guest_info': guest_info 
    }
    return render(request, 'booking/checkout.html', context)

# หน้าเลือกวิธีชำระเงิน 
def payment_page(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    #ความปลอดภัย
    if request.user.is_authenticated:
        if booking.user != request.user:
            return redirect('booking_history')
    else:
        if booking.user is not None:
             return redirect('car_list')
    
    # เช็คสถานะ
    if booking.status not in ['approved', 'waiting_payment']:
        messages.warning(request, "รายการนี้ไม่ได้อยู่ในสถานะรอชำระเงิน")
        return redirect('car_list')    
    #ดึงค่ามัดจำ 
    security_deposit = float(booking.car.deposit) if booking.car.deposit else 0.0
    
    #หา "ค่าเช่าสุทธิ" 
    rental_net = float(booking.total_price) - security_deposit
    # กันพลาด: ถ้าติดลบให้เป็น 0 และปัดเศษทันที
    if rental_net < 0: rental_net = 0.0
    rental_net = round(rental_net, 2) # ปัดเศษ

    discount = float(booking.discount_amount)
    rental_gross_price = round(rental_net + discount, 2)  # คำนวนค่าตั้งต้นออกมาใหม่ 
    platform_fee = round(rental_net * 0.15, 2)

    #คำนวณยอดจ่ายหน้างาน 
    remaining_rent = round(rental_net - platform_fee, 2) #ค่าเช่า-15%
    pay_on_arrival = round(remaining_rent + security_deposit, 2) #ค่ามัดจำ

    PAYMENT_TIMEOUT_MINUTES = 60 
    
    # สร้างหรือดึงข้อมูลการชำระเงิน
    payment_obj, created = Payment.objects.get_or_create(
        booking=booking,
        defaults={
            'amount': platform_fee, # ยอดที่จะให้โอน
            'payment_method': 'QR_PROMPTPAY',
            'payment_status': 'PENDING',
            'expire_at': timezone.now() + timedelta(minutes=PAYMENT_TIMEOUT_MINUTES)
        }
    )
    # ตรวจสอบว่ายอดใน Database ตรงกับที่คำนวณใหม่
    if abs(float(payment_obj.amount) - platform_fee) > 0.01:
        payment_obj.amount = platform_fee
        payment_obj.save()
        #เลยเวลามาแล้ว
    if payment_obj.payment_status == 'PENDING' and timezone.now() > payment_obj.expire_at:
        booking.status = 'cancelled'
        booking.save()
        
        # หมดอายุบิล 
        payment_obj.payment_status = 'EXPIRED'
        payment_obj.save()
        
        messages.error(request, "❌ หมดเวลาชำระเงินแล้ว รายการจองถูกยกเลิกอัตโนมัติ")
        if booking.user:
            return redirect('booking_history')
        else:
            return redirect('booking_detail', booking_id=booking.id)

    # ส่วนจัดการอัปโหลดสลิป 
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
            return redirect('booking_history')
        else:
            #  "ลูกค้าทั่วไป"
            return redirect('booking_detail', booking_id=booking.id)

    # สร้าง QR Code จากยอด platform_fee
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
    # คำนวณเวลาที่เหลือเป็นวินาที
    time_remaining = (payment_obj.expire_at - timezone.now()).total_seconds()

    context = {
        'booking': booking,
        'payment': payment_obj, 
        'rental_gross_price': rental_gross_price,
        'rental_net_price': rental_net,       
        'platform_fee': platform_fee,         
        'security_deposit': security_deposit, 
        'pay_on_arrival': pay_on_arrival,     
        'qr_image': img_str,
        'time_remaining': int(time_remaining) if time_remaining > 0 else 0,
    }
    
    return render(request, 'booking/payment.html', context)


# หน้ารายละเอียดหลังจองสำเร็จ (สำหรับ Guest ที่ไม่มีบัญชี)
def booking_success(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    if request.user.is_authenticated and booking.user != request.user:
         return redirect('booking_history')
         
    return render(request, 'booking/booking_success.html', {'booking': booking})


# ฟังก์ชันนี้จะดึงค่าคอมมิชชั่นจากฐานข้อมูล
def get_commission_rate():
    try:
        setting = PlatformSetting.objects.first()
        if setting:
            return float(setting.commission_rate)
    except:
        pass
    return 0.15 

# ฟังก์ชันนี้สำหรับให้ลูกค้าใส่เลข Ref และ Email/Phone เพื่อดูรายละเอียดการจอง 
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
            #ดึงค่าเช่า "รายวัน"
            rental_price = float(booking.car.price_per_day)
            
            # คำนวณมัดจำจอง 15% 
            deposit_to_pay = rental_price * 0.15
            
            #ค่าเช่าส่วนที่เหลือ 
            remaining_rental = rental_price - deposit_to_pay
            
            car_security_deposit = float(booking.car.deposit) if hasattr(booking.car, 'deposit') and booking.car.deposit else 0.0
            
            # ยอดที่ต้องจ่ายหน้างาน = (ค่าเช่าส่วนที่เหลือ) + (ค่ามัดจำรถ)
            pay_on_arrival = remaining_rental + car_security_deposit
            
            booking.deposit_amount = deposit_to_pay
            booking.remaining_balance = pay_on_arrival
            return render(request, 'booking/booking_detail.html', {'booking': booking})

        except Booking.DoesNotExist:
            error_message = "ไม่พบข้อมูลการจอง หรือข้อมูลยืนยันตัวตนไม่ถูกต้อง"
            return render(request, 'booking/manage_booking.html', {'error': error_message})
    return render(request, 'booking/manage_booking.html')


def booking_detail(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    return render(request, 'booking/booking_detail.html', {'booking': booking})

# หน้าประวัติการจองของลูกค้า (สำหรับสมาชิกที่ล็อกอินแล้ว)
@login_required
def booking_history(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')   
    return render(request, 'booking/booking_history.html', {'bookings': bookings})

#คำขอเช่าใหม่" ที่ยังไม่ได้กดรับหรือปฏิเสธ (สำหรับเจ้าของรถ)
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

# หน้าประวัติการปล่อยเช่าทั้งหมด (สำหรับเจ้าของรถ)
@login_required
def manage_bookings(request):
                                                                          #เรียงจากใหม่ไปเก่า
    all_bookings = Booking.objects.filter(car__owner=request.user).order_by('-created_at')
    return render(request, 'booking/manage_bookings.html', {
        'bookings': all_bookings
    })


# ฟังก์ชันนี้รองรับการกดปุ่มทุกปุ่ม (อนุมัติ, ปฏิเสธ, รับรถ, คืนรถ)
@login_required
def update_booking_status(request, booking_id, action):
    booking = get_object_or_404(Booking, id=booking_id, car__owner=request.user)
    #  กรณีเจ้าของกด "อนุมัติ"
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

    #  กรณีเจ้าของกด "ปฏิเสธ"
    elif action == 'reject':
        booking.status = 'rejected'
        messages.warning(request, f"ปฏิเสธการจอง {booking.booking_ref} แล้ว")
        
        if booking.user and hasattr(booking.user, 'profile') and booking.user.profile.line_id:
            msg = f"❌ ขออภัย การจอง {booking.booking_ref} ไม่ได้รับการอนุมัติจากเจ้าของรถ"
            send_line_push(booking.user.profile.line_id, msg)

    # กรณีเจ้าของกด "รับรถแล้ว" 
    elif action == 'picked_up':
        booking.status = 'picked_up'
        messages.info(request, "บันทึกสถานะ: ลูกค้ารับรถไปแล้ว")

    # กรณีเจ้าของกด "จบงาน" (คืนรถ)
    elif action == 'completed':
        booking.status = 'completed'
        messages.success(request, "บันทึกสถานะ: คืนรถเรียบร้อย (จบงาน)")

    booking.save()
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
            # กดปุ่มยืนยัน 
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


# ฟังก์ชันลูกค้ารีวิวรถ
@login_required
def submit_car_review(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    # เช็คสถานะ
    if booking.status != 'completed':
        messages.error(request, "ต้องจบงานก่อนจึงจะรีวิวได้")
        return redirect('booking_history')

    # เช็คว่า booking ก้อนนี้มี review ผูกอยู่ไหม
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


# ฟังก์ชันเจ้าของรีวิวลูกค้า
@login_required
def submit_renter_review(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, car__owner=request.user)
    
    # เช็คสถานะ
    if booking.status != 'completed':
        messages.error(request, "ต้องจบงานก่อนจึงจะรีวิวลูกค้าได้")
        return redirect('manage_bookings') 

    # เช็คว่าเคยรีวิวไปแล้วหรือยัง?
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

# ฟังก์ชันรับค่าจากปุ่ม "ใช้โค้ด"
def apply_promotion(request, car_id):
    # เตรียม URL เดิม (user_info)
    booking_data = request.session.get('booking_context')
    if not booking_data:
        return redirect('car_detail', car_id=car_id)

    # จำค่าวันที่
    query_params = f"?pickup_datetime={booking_data['pickup_datetime']}&dropoff_datetime={booking_data['dropoff_datetime']}&location={booking_data['location']}"
    redirect_url = f"/booking/user-info/{car_id}/{query_params}" 

    if request.method == 'POST':
        code = request.POST.get('promo_code', '').strip().upper()
        try:
            #ค้นหาคูปอง
            now = timezone.now().date()
            promo = Promotion.objects.get(
                code=code, 
                is_active=True,
                start_date__lte=now, 
                end_date__gte=now
            )
            
            #เช็คสิทธิ์การใช้งาน
            if promo.used_count >= promo.usage_limit:
                messages.error(request, "คูปองนี้สิทธิ์เต็มแล้ว", extra_tags='promo')
                return redirect(redirect_url)

            # คนนี้ เคยใช้ไปหรือยัง 
            if request.user.is_authenticated:

                if PromotionUsage.objects.filter(user=request.user, promotion=promo).exists():
                    messages.error(request, "คุณใช้สิทธิ์โค้ดนี้ไปแล้ว (จำกัด 1 คน/สิทธิ์)", extra_tags='promo')
                    return redirect(redirect_url)

            #บันทึก
            request.session['booking_promo_code'] = promo.code
            messages.success(request, f"ใช้โค้ด {promo.code} สำเร็จ!", extra_tags='promo')
            
        except Promotion.DoesNotExist:
            messages.error(request, "ไม่พบรหัสโปรโมชั่น หรือหมดอายุแล้ว", extra_tags='promo')
            
    return redirect(redirect_url)

# ฟังก์ชันยกเลิกโค้ด (เผื่อลูกค้าอยากเปลี่ยน)
def remove_promotion(request, car_id):
    #ลบโค้ดออกจาก Session
    if 'booking_promo_code' in request.session:
        del request.session['booking_promo_code']
        messages.info(request, "ยกเลิกการใช้คูปองแล้ว")
    
    # ดึงข้อมูลการจองเดิม (วันที่/สถานที่)
    booking_data = request.session.get('booking_context')
    if booking_data:
        from django.urls import reverse
        from django.http import HttpResponseRedirect
        # สร้าง URL
        base_url = reverse('user_info', kwargs={'car_id': car_id})
        query_params = f"?pickup_datetime={booking_data['pickup_datetime']}&dropoff_datetime={booking_data['dropoff_datetime']}&location={booking_data['location']}"
        
        return HttpResponseRedirect(base_url + query_params)
    return redirect('user_info', car_id=car_id)

#ระบบยกเลิกการจองฝั่งลูกค้า
@login_required
def cancel_booking(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)

    # ห้ามยกเลิก
    if booking.status in ['picked_up', 'completed', 'cancelled', 'rejected']:
        messages.error(request, "ไม่สามารถยกเลิกรายการนี้ได้")
        return redirect('booking_history')

    # ยังไม่จ่ายเงิน
    if booking.status in ['pending', 'approved', 'waiting_payment']:
        booking.status = 'cancelled'
        booking.save()
        
        # ถ้ามีบิลค้างอยู่ (Payment) ให้ยกเลิกบิลด้วย
        if hasattr(booking, 'payment'):
            booking.payment.payment_status = 'CANCELLED' 
            booking.payment.save()
        messages.success(request, "ยกเลิกการจองเรียบร้อยแล้ว")

    # จ่ายเงินแล้ว 
    elif booking.status in ['waiting_verify', 'confirmed']:
        booking.status = 'cancelled' 
        booking.save()
        messages.warning(request, "ยกเลิกการจองสำเร็จ! เนื่องจากคุณได้ชำระเงินแล้ว กรุณาติดต่อเจ้าของรถหรือแอดมินเพื่อดำเนินการเรื่องการคืนเงิน")

    return redirect('booking_history')

# ระบบขอคืนเงิน ฝั่งลูกค้า
def request_refund(request, booking_id):
    if request.user.is_authenticated:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    else:
        # กรณี ลูกค้าทั่วไปที่ไม่มีบัญชี 
        booking = get_object_or_404(Booking, id=booking_id, user__isnull=True)
    
    # เช็คสถานะการจ่ายเงิน
    if booking.status not in ['confirmed', 'waiting_verify', 'approved', 'pending']:
        messages.error(request,_("รายการนี้ไม่สามารถขอคืนเงินได้"))
        if request.user.is_authenticated:
            return redirect('booking_history')
        else:
            return redirect('booking_detail', booking_id=booking.id)
        
    #คำนวณเงินคืน 
    now = timezone.now()
    pickup_time = booking.pickup_datetime
    
    #                         เวลาปัจจุบัน
    time_diff = pickup_time - now
    hours_until_pickup = time_diff.total_seconds() / 3600
    
    # ดึงยอดที่ลูกค้าจ่ายมาจริง (จาก Payment)
    paid_amount = 0
    if hasattr(booking, 'payment'):
        paid_amount = float(booking.payment.amount)

    refund_amount = 0
    policy_message = ""
    is_refundable = False

    # การคืนเงิน 
    if hours_until_pickup >= 24:
        # ยกเลิกก่อน 24 ชม.คืน 100%
        refund_amount = paid_amount
        is_refundable = True
        policy_message =_("ยกเลิกก่อนกำหนด 24 ชม. ได้รับเงินคืนเต็มจำนวน")
        
    elif hours_until_pickup > 0:
        # ยกเลิก(น้อยกว่า 24 ชม.) ไม่คืน 
        refund_amount = 0 
        is_refundable = False
        policy_message = _("เนื่องจากยกเลิกช้ากว่ากำหนด (น้อยกว่า 24 ชม.) จะไม่ได้รับเงินคืน")
        
    else:
        # เลยเวลารับรถไปแล้ว
        refund_amount = 0
        is_refundable = False
        policy_message = _("เลยเวลารับรถแล้ว ไม่สามารถขอเงินคืนได้")

    if request.method == 'POST':
        # ถ้าลูกค้ากด "ยืนยัน" แม้ว่าจะไม่ได้เงินคืน 
        form = RefundForm(request.POST, instance=booking)
        if form.is_valid():
            if refund_amount > 0:
                booking.status = 'refund_requested'
                msg_display = _("ส่งคำร้องขอคืนเงินเรียบร้อย เจ้าหน้าที่จะดำเนินการโอนเงินคืนให้ท่าน")
            else:
                booking.status = 'cancelled'
                msg_display = _("ยกเลิกรายการจองเรียบร้อยแล้ว (รายการนี้ไม่เข้าเงื่อนไขการรับเงินคืน)")
            booking.save()

            msg_success = _("ส่งคำร้องเรียบร้อย")
            messages.success(request, f"{msg_success} ({policy_message})")
            if request.user.is_authenticated:
                return redirect('booking_history')
            else:
                return redirect('booking_detail', booking_id=booking.id)
    else:
        form = RefundForm(instance=booking)

    refund_amount_str = f"{refund_amount:,.2f}"
    paid_amount_str = f"{paid_amount:,.2f}"

    context = {
        'form': form,
        'booking': booking,
        'refund_amount_val': refund_amount, 
        'refund_amount_display': refund_amount_str,
        'paid_amount_display': paid_amount_str,
        'policy_message': policy_message,
    }
    return render(request, 'booking/refund_request.html', context)

# สำหรับให้ลูกค้ากดปุ่ม "ยกเลิกทันที" ในกรณีที่ยังไม่ได้จ่ายเงิน 
def cancel_booking_immediately(request, booking_id):
    if request.user.is_authenticated:
        booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    else:
        booking = get_object_or_404(Booking, id=booking_id, user__isnull=True)

    # เช็คว่าสถานะควรจะยกเลิกได้
    if booking.status in ['pending', 'approved']:
        booking.status = 'cancelled'
        booking.save()
        messages.success(request, _("ยกเลิกรายการจองเรียบร้อยแล้ว"))
    else:
        messages.error(request, _("ไม่สามารถยกเลิกรายการนี้ได้โดยตรง"))

    # Redirect กลับหน้าเดิม
    if request.user.is_authenticated:
        return redirect('booking_history')
    else:
        return redirect('booking_detail', booking_id=booking.id)
