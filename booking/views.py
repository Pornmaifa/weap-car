import random
import string
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from datetime import datetime, timedelta
from car_rental.forms import InspectionForm
from car_rental.models import BookingInspection

# --- Import ข้าม App (ดึง Model จากแอป car_rental) ---
from car_rental.models import Car, GuestCustomer, Promotion, PlatformSetting, Booking
# users/views.py (หรือ booking/views.py)

from django.shortcuts import get_object_or_404, redirect
from car_rental.models import Booking
# --- Import ใน App ตัวเอง (ดึง Model Booking) ---
from car_rental.models import Booking, Review, RenterReview
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from car_rental.models import Booking, Review, RenterReview # อย่าลืม import ให้ครบ

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
    original_total_price = float(car.price_per_day * rental_days)
    session_context = request.session.get('booking_context', {})

    discount_amount = 0
    applied_code = ''

    # เช็คว่าส่วนลดใน session เป็นของรถคันนี้จริงๆ (กันลูกค้าเปลี่ยนรถแต่ส่วนลดค้าง)
    if session_context.get('car_id') == car.id:
        if session_context.get('car_id') == car.id:
            discount_amount = session_context.get('discount_amount', 0)
            applied_code = session_context.get('applied_promo_code', '')
    else:
        # ถ้าเป็น Guest ให้เคลียร์ส่วนลดทิ้ง (กันลักไก่)
        discount_amount = 0
        applied_code = ''

    final_total_price = original_total_price - discount_amount
    if final_total_price < 0: final_total_price = 0

    # 📌 จุดสำคัญ 1: บันทึก "บริบทการจอง" ลง Session เสมอ
    request.session['booking_context'] = {
        'car_id': car.id,
        'pickup_datetime': pickup_datetime.isoformat(),
        'dropoff_datetime': dropoff_datetime.isoformat(),
        'location': location,
        'original_total_price': original_total_price, # เก็บราคาเต็ม
        'total_price': final_total_price,             # เก็บราคาหลังลด (เอาไปใช้ตอนสร้าง Booking)
        'discount_amount': discount_amount,           # เก็บยอดลด
        'applied_promo_code': applied_code,           # เก็บชื่อโค้ด
        'rental_days': rental_days
    }

    # กรณีลูกค้ากด Submit (POST)
    if request.method == "POST":
        # ถ้าเป็น Guest ให้เก็บข้อมูลลง Session ไว้ก่อน
        # 2. จำ ID ลูกค้าไว้ใน Session
        request.session['guest_info_temp'] = {
            'first_name': request.POST.get("first_name"),
            'last_name': request.POST.get("last_name"),
            'email': request.POST.get("email"),
            'phone_number': request.POST.get("phone_number"),
            'license_number': request.POST.get("license_number")
        }

        # 3. ไปหน้า Checkout (หน้าสรุปก่อนจ่าย)
        return redirect('checkout', car_id=car.id)

    context = {
        "car": car,
        "pickup_datetime": pickup_datetime,
        "dropoff_datetime": dropoff_datetime,
        "location": location,
        "rental_days": rental_days,
        "original_total_price": original_total_price, # ราคาเต็ม
        "total_price": final_total_price,             # ราคาสุทธิ
        "discount_amount": discount_amount,           # ส่วนลด
        "applied_code": applied_code,                 # โค้ดที่ใช้
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
def payment(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    
    
    # 2. (สำคัญ) เช็คความปลอดภัย
    # ต้องเป็นคนจองตัวจริง + สถานะต้องเป็น 'approved' (รอจ่าย) หรือ 'waiting_payment'
    if request.user.is_authenticated:
        # กรณีสมาชิก: ต้องเป็นคนจองตัวจริงเท่านั้น
        if booking.user != request.user:
            return redirect('booking_history')
    else:
        # กรณี Guest: ต้องเป็น Booking ที่ไม่มี User ผูกมัด (booking.user เป็น None)
        # ถ้า Booking นี้มีเจ้าของ (User) แต่คนเข้าไม่ได้ล็อกอิน -> ห้ามเข้า
        if booking.user is not None:
             return redirect('car_list')
    
    # เช็คสถานะ: ต้องเป็นสถานะที่พร้อมจ่ายเท่านั้น
    if booking.status not in ['approved', 'waiting_payment']:
        messages.warning(request, "รายการนี้ไม่ได้อยู่ในสถานะรอชำระเงิน")
        return redirect('car_list')
    
    total_price = booking.total_price
    deposit_amount = booking.deposit_amount
    # คำนวณยอดมัดจำ 30%

    pay_on_arrival = total_price - deposit_amount

    context = {
        'booking': booking,
        'total_price': total_price,
        'deposit_amount': deposit_amount,
        'pay_on_arrival': pay_on_arrival,
        'commission_percent': 15
    }
    return render(request, 'booking/payment.html', context)


def process_payment(request, booking_id): # 1. เปลี่ยนจาก car_id เป็น booking_id
    # 2. ดึงข้อมูลการจองที่มีอยู่แล้วใน Database (ไม่ต้องดึงจาก Session)
    booking = get_object_or_404(Booking, id=booking_id)

    # Security Check: เช็คว่าเป็นคนจองจริงๆ และสถานะต้องเป็น 'approved' (รอจ่าย)
    if request.user.is_authenticated:
        if booking.user != request.user:
            messages.error(request, "คุณไม่มีสิทธิ์ชำระเงินรายการนี้")
            return redirect('booking_history')
    else:
        if booking.user is not None:
            return redirect('car_list')
    
    # อนุญาตให้จ่ายถ้ารอจ่าย (approved) หรือ จ่ายไปแล้ว (confirmed - เผื่อกดซ้ำ)
    if booking.status not in ['approved', 'waiting_payment', 'confirmed']: 
        messages.error(request, "สถานะการจองไม่ถูกต้อง")
        return redirect('booking_history')

    if request.method == 'POST':
        #payment_method = request.POST.get('payment_method') # รับค่าว่าจ่ายผ่านอะไร (Credit/QR)

        # ---------------------------------------------------------
        # (จำลองการตัดเงินสำเร็จ)
        # ถ้ามีระบบตัดบัตรจริง (Omise/Stripe) จะใส่ Logic ตรงนี้
        # ---------------------------------------------------------

        # 3. เปลี่ยนสถานะเป็น "จองสำเร็จ" (Confirmed)
        booking.status = 'confirmed'
        
        # (Optional) ถ้าจะบันทึกว่าจ่ายด้วยวิธีไหน
        # booking.payment_method = payment_method 
        
        booking.save()

        # 4. แจ้งเตือนและกลับไปหน้าประวัติ
        messages.success(request, f"ชำระเงินสำเร็จ! การจองรถ {booking.car.brand} ของคุณได้รับการยืนยันแล้ว")
        if request.user.is_authenticated:
            # สมาชิก -> ไปหน้าประวัติ
            return redirect('booking_history')
        else:
            # Guest -> ไปหน้า Success (เพื่อดู Ref Code / ใบเสร็จ)
            return redirect('booking_success', booking_id=booking.id)

    # ถ้าไม่ใช่ POST ให้กลับไปหน้าเลือกวิธีชำระเงิน
    return redirect('payment_page', booking_id=booking.id)

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
            # 🔍 ค้นหา Booking ที่ตรงกับรหัส AND (อีเมล OR เบอร์โทร)
            # เราใช้ Q object เพื่อช่วยทำเงื่อนไข OR (ต้อง import Q ข้างบนก่อนนะครับ)
            from django.db.models import Q
            
            booking = Booking.objects.get(
                Q(guest__email=email_or_phone) | Q(guest__phone_number=email_or_phone),
                booking_ref=ref_code
            )
            
            # ถ้าเจอ -> ส่งไปหน้ารายละเอียด (หรือจะแสดงหน้านี้เลยก็ได้)
            return render(request, 'booking/booking_detail.html', {'booking': booking})

        except Booking.DoesNotExist:
            # ถ้าไม่เจอ -> แจ้งเตือน
            error_message = "ไม่พบข้อมูลการจอง หรือข้อมูลยืนยันตัวตนไม่ถูกต้อง"
            return render(request, 'booking/manage_booking.html', {'error': error_message})

    # ถ้าเป็น GET (เปิดหน้าเว็บเฉยๆ)
    return render(request, 'booking/manage_booking.html')





def apply_promotion(request, car_id):
    if not request.user.is_authenticated:
        messages.error(request, "โปรโมชั่นสำหรับสมาชิกเท่านั้น กรุณาเข้าสู่ระบบ")
        # ดีดกลับไปหน้าเดิมโดยไม่ทำอะไร
        return redirect(request.META.get('HTTP_REFERER', '/'))
    
    if request.method == 'POST':
        code = request.POST.get('promo_code').strip()
        booking_data = request.session.get('booking_context')
        
        # ถ้าไม่มีข้อมูลการจอง ให้กลับไปเริ่มใหม่
        if not booking_data:
            return redirect('car_detail', car_id=car_id)

        # 📌 ส่วนสำคัญที่เพิ่มมา: สร้าง Link เพื่อดีดกลับไปหน้าเดิม (user_info) 
        # ต้องแนบวันที่/เวลาไปด้วย ไม่งั้นหน้าเว็บจะรีเซ็ตค่าเป็นวันปัจจุบัน
        query_params = f"?pickup_datetime={booking_data['pickup_datetime']}&dropoff_datetime={booking_data['dropoff_datetime']}&location={booking_data['location']}"
        # ต้องใช้ path ให้ตรงกับ urls.py ของคุณ (ถ้าใช้ name='user_info' อาจต้องใช้ reverse แต่แบบนี้ง่ายกว่าสำหรับตอนนี้)
        redirect_url = f"/booking/user-info/{car_id}/{query_params}"

        try:
            # 1. ค้นหาโปรโมชั่นจาก Code และต้องยังไม่หมดอายุ
            from django.utils import timezone
            now = timezone.now().date()
            
            promo = Promotion.objects.get(
                code=code, 
                start_date__lte=now, 
                end_date__gte=now
            )
            
            # 2. ตรวจสอบว่าเจ้าของรถคนนี้ร่วมโปรนี้ไหม (ถ้าโปรเป็นของเจ้าของรถ)
            # ถ้าโปรเป็นของระบบกลาง (Platform) ให้ข้ามเช็ค owner ไปได้เลย
            car = Car.objects.get(id=car_id)
            if promo.owner != car.owner:
                messages.error(request, "รหัสส่วนลดนี้ใช้ไม่ได้กับรถคันนี้")
                return redirect(redirect_url)

            # 3. คำนวณส่วนลด
            # สมมติ discount_rate คือเปอร์เซ็นต์ (เช่น 10.00 คือ 10%)
            original_price = float(booking_data.get('original_total_price', booking_data['total_price'])) # ใช้ราคาเต็มตั้งต้น
            discount_value = original_price * (float(promo.discount_rate) / 100)
            
            new_total = original_price - discount_value
            if new_total < 0: new_total = 0
            # 4. อัปเดตลง Session
            booking_data['discount_amount'] = discount_value
            booking_data['total_price'] = new_total # ราคาสุทธิหลังลด
            booking_data['applied_promo_code'] = code
            
            # เก็บ original_price ไว้กันเหนียว เผื่อลูกค้ากรอก code ผิดแล้วอยาก reset
            if 'original_total_price' not in booking_data:
                booking_data['original_total_price'] = original_price
                
            request.session['booking_context'] = booking_data
            messages.success(request, f"ใช้รหัส {code} ลดราคา {discount_value:,.2f} บาท!")

        except Promotion.DoesNotExist:
            messages.error(request, "รหัสโปรโมชั่นไม่ถูกต้อง หรือหมดอายุแล้ว")
        
        return redirect(redirect_url)
        
    return redirect('car_detail', car_id=car_id)


@login_required
def booking_history(request):
    # ดึงการจองของ user คนนี้ + เรียงจากล่าสุดไปเก่าสุด
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'booking/booking_history.html', {'bookings': bookings})


#(ตอนเจ้าของกดอนุมัติ)
@login_required
def update_booking_status(request, booking_id, action):
    # ดึงข้อมูลการจองมา
    booking = get_object_or_404(Booking, id=booking_id)
    
    # Security Check: เช็คว่าคนกด เป็นเจ้าของรถคันนี้จริงๆ มั้ย (ห้ามคนอื่นมั่วมากด)
    if booking.car.owner != request.user:
        return redirect('dashboard') # หรือแสดง error page

    # อัปเดตสถานะ
    if action == 'approve':
        booking.status = 'approved'  # <--- แก้ตรงนี้ (จาก waiting_payment เป็น approved)
        booking.save()
        messages.success(request, f"อนุมัติการจองแล้ว ผู้เช่าสามารถชำระเงินได้ทันที")
        
    elif action == 'reject':
        booking.status = 'rejected'
        booking.save()
        messages.warning(request, "ปฏิเสธคำขอจองแล้ว")        # ปฏิเสธ
    
    booking.save()
    
    # กลับไปหน้า Dashboard
    return redirect('dashboard')   

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

    # 2. กรณีเจ้าของกด "ปฏิเสธ"
    elif action == 'reject':
        booking.status = 'rejected'
        messages.warning(request, f"ปฏิเสธการจอง {booking.booking_ref} แล้ว")

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
        
    return redirect('booking_history')


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
        
    return redirect('manage_bookings')