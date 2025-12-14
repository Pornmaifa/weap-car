# car_rental/views.py

from datetime import timezone
import uuid
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from users import models
from .forms import CarForm
from .models import Car , CarImage, PlatformSetting, ReviewReply
from django.contrib import messages
import os
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect
from .models import Car, CarImage
from django.core.files.base import ContentFile
import base64
from django.db.models import Q # ใช้สำหรับ query ขั้นสูง
from car_rental.utils import build_rental_context 
from .models import GuestCustomer
import uuid
from datetime import datetime # อย่าลืม import ตัวนี้ข้างบนไฟล์
from django.shortcuts import render, get_object_or_404, redirect
from .models import Car, Booking, GuestCustomer
from django.contrib import messages
from .models import Promotion # อย่าลืม import
# (เพิ่มฟังก์ชันนี้เข้าไปใน views.py)
@login_required
def add_car_preview(request):
    draft = request.session.get('car_draft')

    if not draft:
        messages.error(request, "ไม่พบข้อมูลรถ")
        return redirect('add_car_step1')

    return render(request, 'car_rental/add_car_preview.html', {'draft': draft})


@login_required
def dashboard(request):
    
    if request.method == "POST":
        
        # =========== กรณีที่ 1: ลบรถ (Delete) ===========
        if 'delete_car_id' in request.POST:
            car_id = request.POST.get("delete_car_id")
            car = get_object_or_404(Car, id=car_id, owner=request.user)
            car.delete()
            messages.success(request, 'ลบรถเรียบร้อยแล้ว')
            return redirect("dashboard")

        # =========== กรณีที่ 2: แก้ไขรถ (Edit) ===========
        elif 'edit_car_id' in request.POST:
            car_id = request.POST.get("edit_car_id")
            car = get_object_or_404(Car, id=car_id, owner=request.user)
            
            # รับค่าจากฟอร์ม
            car.brand = request.POST.get('brand')
            car.model = request.POST.get('model')
            car.license_plate = request.POST.get('license_plate')
            car.price_per_day = request.POST.get('price')
            car.description = request.POST.get('description')

            # จัดการรูปภาพ (ถ้ามีการอัปโหลดใหม่)
            new_image = request.FILES.get('new_image')
            if new_image:
                # ถ้ามีรูปเดิมอยู่แล้ว ให้แทนที่รูปแรก หรือสร้างใหม่
                if car.images.exists():
                    img_obj = car.images.first()
                    img_obj.image = new_image
                    img_obj.save()
                else:
                    CarImage.objects.create(car=car, image=new_image)
                    
            if car.status != 'PENDING':
                new_status = request.POST.get('status')
                if new_status in ['AVAILABLE', 'MAINTENANCE']: # (ป้องกันการมั่วข้อมูล)
                    car.status = new_status 

            car.save()
            messages.success(request, 'แก้ไขข้อมูลรถเรียบร้อยแล้ว')
            return redirect("dashboard")

    # =========== ส่วนแสดงผล (GET) ===========
    my_cars = Car.objects.filter(owner=request.user).order_by('-id')

    context = {
        'cars': my_cars
    }
    return render(request, 'car_rental/dashboard.html', context)

# (เพิ่มฟังก์ชันนี้เข้าไปใน views.py)
@login_required
def publish_car(request):
    draft = request.session.get('car_draft')

    if not draft:
        messages.error(request, "ไม่พบข้อมูลรถใน Session")
        return redirect('add_car_step1')

    if request.method == 'POST':

        # 1) สร้าง Car จริงในฐานข้อมูล
        car = Car.objects.create(
            owner=request.user,
            brand=draft.get('brand', ''),
            model=draft.get('model', ''),
            year=draft.get('year'),
            description=draft.get('description', ''),

            price_per_day=draft.get('price'),
            car_type=draft.get('car_type'),
            license_plate=draft.get('license_plate', ''),
            status='AVAILABLE',
            service_type=draft.get('service_type'),

            country=draft.get('country'),
            street_address=draft.get('street_address'),
            city=draft.get('city'),
            state=draft.get('state'),
            zip_code=draft.get('zip_code'),

            num_doors=draft.get('num_doors', 4),
            num_luggage=draft.get('num_luggage', 2),
            fuel_system=draft.get('fuel_system', 'GASOLINE'),
            has_child_seat=draft.get('has_child_seat', False),
            accessory_price=draft.get('accessory_price', 0),

            min_rental_days=draft.get('min_rental_days', 1),
            max_rental_days=draft.get('max_rental_days', 30),
            discount_option=draft.get('discount_option', 'NONE'),

            is_published=True,
        )

        # 2) บันทึกรูปภาพ (base64 → ไฟล์)
        import base64
        from django.core.files.base import ContentFile

        for idx, img_data in enumerate(draft.get('images', [])):
            img_binary = base64.b64decode(img_data.split(',')[1])
            file_name = f"car_{car.id}_{idx}.jpg"

            CarImage.objects.create(
                car=car,
                image=ContentFile(img_binary, name=file_name)
            )

        # 3) ลบ draft ใน session
        del request.session['car_draft']

        messages.success(request, "ลงประกาศรถของคุณสำเร็จแล้ว!")
        return redirect('dashboard')

    return redirect('add_car_preview')





@login_required
def cancel_add_car(request):
    if 'car_id' in request.session:
        Car.objects.filter(id=request.session['car_id'], owner=request.user).delete()
        del request.session['car_id']
    return redirect('dashboard')


    
# View สำหรับแสดงรถทั้งหมด
def car_list(request):
    province = request.GET.get('province', '').strip()
    service_type = request.GET.get('service_type', 'SELF_DRIVE')
    car_type = request.GET.get('car_type', '')

    cars = Car.objects.filter(status='AVAILABLE', is_published=True)

    if service_type:
        cars = cars.filter(service_type=service_type)

    if province:
        cars = cars.filter(state__exact=province)

    if car_type:
        cars = cars.filter(car_type=car_type)

    context = {
        'cars': cars,
        'province': province,
        'search_service': service_type,
        'search_category': car_type,
    }
    return render(request, 'car_rental/car_list.html', context)

# car_rental/views.py



@login_required
def add_car(request):
    if request.method == "POST":
        data = request.POST

        # 1) สร้าง Car จริงในฐานข้อมูล
        car = Car.objects.create(
            owner=request.user,
            brand=data.get("brand", ""),
            model=data.get("model", ""),
            car_type=data.get("car_type", "SEDAN"),
            service_type=data.get("service_type", "SELF_DRIVE"),

            # Address
            country=data.get("country") or "ประเทศไทย",
            street_address=data.get("street_address") or "",
            city=data.get("city") or "",
            state=data.get("state") or "",
            zip_code=data.get("zip_code") or "",
            num_seats=data.get("num_seats", 5), # ✅ เพิ่ม
            rules=data.get("rules", ""),        # ✅ เพิ่ม

            # รายละเอียดรถ
            description=data.get("description", ""),
            license_plate=data.get("license_plate", ""),
            num_doors=data.get("num_doors") or 4,
            num_luggage=data.get("num_luggage") or 2,
            fuel_system=data.get("fuel_system") or "GASOLINE",
            has_child_seat=(data.get("has_child_seat") == "true"),
            accessory_price=data.get("accessory_price") or 0,

            min_rental_days=data.get("min_rental_days") or 1,
            max_rental_days=data.get("max_rental_days") or 30,

            price_per_day=data.get("price") or 0,
            discount_option=data.get("discount_option") or "NONE",

            status="PENDING",
            is_published=True,
        )

        # 2) รูปภาพ (รับเป็น data URL base64 จากฟอร์ม)
        images = request.POST.getlist("images_base64[]")

        for index, img64 in enumerate(images):
            if not img64:
                continue
            if ";base64," in img64:
                try:
                    format, imgstr = img64.split(';base64,') 
                    ext = format.split('/')[-1]  # ดึงนามสกุลไฟล์ เช่น png, jpeg
                
                    img_binary = base64.b64decode(imgstr)
                    CarImage.objects.create(
                        car=car,
                        image=ContentFile(img_binary, name=f"car_{car.id}_{index}.{ext}")
                    )
                except Exception as e:
                    print(f"Error saving image {index}: {e}")
                    continue

        messages.success(request, "ลงประกาศรถของคุณสำเร็จแล้ว! กรุณารอการตรวจสอบจากแอดมิน")
        return redirect("dashboard")

    # GET: แสดงหน้า multi-step form
    return render(request, "car_rental/add_car.html")




def search_cars(request):
    # 1. รับค่าจากหน้าแรก (ชื่อฟิลด์ตรงตามฟอร์ม)
    pickup = request.GET.get('pickup', '').strip()
    dropoff = request.GET.get('dropoff', '').strip()
    province = request.GET.get('province', '').strip()

    start_date = request.GET.get('start_date', '')
    start_time = request.GET.get('start_time', '')
    end_date = request.GET.get('end_date', '')
    end_time = request.GET.get('end_time', '')

    service_type = request.GET.get('service_type', 'SELF_DRIVE')
    car_type_filter = request.GET.get('car_type', '')

    if not pickup:
            province = ""
    # 2. ดึงรายการรถ
    cars = Car.objects.filter(status='AVAILABLE', is_published=True)

    
    # 3. กรองตามประเภทบริการ
    if service_type:
        cars = cars.filter(service_type=service_type)

    # 4. กรองตามสถานที่ pickup
    
    if province:
        cars = cars.filter(state__exact=province.strip())



    # 5. กรองตามประเภทรถ
    if car_type_filter:
        cars = cars.filter(car_type=car_type_filter)

    # 6. ส่งค่ากลับไปหน้า search_cars.html เพื่อใส่ค่ากลับลง input
    context = {
        'cars': cars,
        "province": province,
        # คืนค่าเดิมกลับไปให้ form จำค่าได้
        'search_location': pickup,
        'pickup': pickup,
        'dropoff': dropoff,
        'start_date': start_date,
        'start_time': start_time,
        'end_date': end_date,
        'end_time': end_time,

        'search_service': service_type,
        'search_category': car_type_filter,
    }
    return render(request, 'car_rental/search_cars.html', context)

from datetime import datetime, timedelta

def car_detail(request, car_id):
    car = get_object_or_404(Car, id=car_id)

    # ⭐ ดึงรีวิวทั้งหมดของรถคันนี้
    reviews = car.reviews.prefetch_related("replies").all()

    # รับค่าจาก Query Params
    location = request.GET.get("location", "-")
    date_from = (request.GET.get("date_from") or "").strip()
    time_from = (request.GET.get("time_from") or "10:00").strip()
    date_to = (request.GET.get("date_to") or "").strip()
    time_to = (request.GET.get("time_to") or "10:00").strip()

    if not date_from:
        date_from = datetime.now().strftime("%d/%m/%Y")

    if not date_to:
        date_to = datetime.now().strftime("%d/%m/%Y")

    try:    
    # รวมเป็น datetime
        pickup_datetime = datetime.strptime(f"{date_from} {time_from}", "%d/%m/%Y %H:%M")
        dropoff_datetime = datetime.strptime(f"{date_to} {time_to}", "%d/%m/%Y %H:%M")
    except Exception as e:
        # ป้องกันเว็บพัง ถ้า format เพี้ยน
        print("DATE PARSE ERROR:", e)
        pickup_datetime = datetime.now()
        dropoff_datetime = datetime.now()
    # คำนวณจำนวนวัน
    rental_days = (dropoff_datetime - pickup_datetime).days
    if rental_days <= 0:
        rental_days = 1

    rental_ctx = build_rental_context(car, pickup_datetime, dropoff_datetime)

    return render(request, "car_rental/car_detail.html", {
        "reviews": reviews, 
        "car": car,
        "location": location,
        "pickup_datetime": pickup_datetime,
        "dropoff_datetime": dropoff_datetime,
        **rental_ctx,
        
    })


def submit_reply(request, review_id):
    if request.method == "POST":
        ReviewReply.objects.create(
            review_id=review_id,
            user=request.user,
            comment=request.POST["comment"]
        )
    return redirect(request.META.get("HTTP_REFERER"))

# car_rental/views.py

def user_info(request, car_id):
    car = get_object_or_404(Car, id=car_id)

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
    total_price = car.price_per_day * rental_days

    # 📌 จุดสำคัญ 1: บันทึก "บริบทการจอง" ลง Session เสมอ
    request.session['booking_context'] = {
        'car_id': car.id,
        'pickup_datetime': pickup_datetime.isoformat(),
        'dropoff_datetime': dropoff_datetime.isoformat(),
        'location': location,
        'total_price': float(total_price),
        'rental_days': rental_days
    }

    # กรณีลูกค้ากด Submit (POST)
    if request.method == "POST":
        
        
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
        "total_price": total_price,
    }
    return render(request, "car_rental/user_info.html", context)


# 2. หน้าสรุปรายการ (Checkout)
def checkout(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    
    # 📌 จุดสำคัญ 2: ดึงข้อมูลจาก Session มาแสดง (ไม่ใช่ค่าจำลอง)
    booking_data = request.session.get('booking_context')

    # ถ้าไม่มีข้อมูลใน Session หรือเป็นรถคนละคัน ให้กลับไปหน้า Detail
    if not booking_data or booking_data['car_id'] != car.id:
        return redirect('car_detail', car_id=car.id)

    context = {
        'car': car,
        'pickup_datetime': datetime.fromisoformat(booking_data['pickup_datetime']),
        'dropoff_datetime': datetime.fromisoformat(booking_data['dropoff_datetime']),
        'location': booking_data['location'],
        'rental_days': booking_data['rental_days'],
        'total_price': booking_data['total_price'],
    }
    return render(request, 'car_rental/checkout.html', context)


# 3. หน้าเลือกวิธีชำระเงิน (Payment - มัดจำ)
def payment(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    booking_data = request.session.get('booking_context')
    
    # ถ้าไม่มีข้อมูล ดีดกลับหน้า Detail (นี่คือสาเหตุที่คุณเด้งกลับ เพราะ session หาย)
    if not booking_data or booking_data['car_id'] != car.id:
        return redirect('car_detail', car_id=car.id)

    total_price = float(booking_data['total_price'])
    
    # คำนวณยอดมัดจำ 30%
    commission_rate = get_commission_rate()
    deposit_amount = total_price * commission_rate

    pay_on_arrival = total_price - deposit_amount

    context = {
        'car': car,
        'total_price': total_price,
        'deposit_amount': deposit_amount,
        'pay_on_arrival': pay_on_arrival,
        'commission_percent': int(commission_rate * 100)
    }
    return render(request, 'car_rental/payment.html', context)



def process_payment(request, car_id):
    if request.method == 'POST':
        car = get_object_or_404(Car, id=car_id)
        
        # 1. ดึงข้อมูลจาก Session
        booking_data = request.session.get('booking_context')
        guest_data = request.session.get('guest_info_temp')
        discount_val = booking_data.get('discount_amount', 0)

        # ถ้า Session หาย ให้เริ่มใหม่
        if not booking_data:
            return redirect('car_detail', car_id=car_id)

        # 2. คำนวณยอดเงิน
        total_price = float(booking_data['total_price'])
        commission_rate = get_commission_rate()
        deposit_amount = total_price * commission_rate

        # 3. สร้างเลข Booking Ref
        ref_code = f"BK-{uuid.uuid4().hex[:8].upper()}"

        # 4. บันทึกข้อมูลการจองลง Database
        guest_instance = None
        if not request.user.is_authenticated and guest_data:
            # ✅ แก้จุดที่ 3: ต้อง Create ใหม่ ไม่ใช่ Get
            # (เพราะเราเพิ่งหอบข้อมูลมาจากหน้าแรก ยังไม่ได้บันทึก)
            guest_instance = GuestCustomer.objects.create(
                first_name=guest_data['first_name'],
                last_name=guest_data['last_name'],
                email=guest_data['email'],
                phone_number=guest_data['phone_number'],
                license_number=guest_data['license_number']
            )

        # ✅ แก้ไข: แปลง String กลับเป็น Datetime เพื่อความชัวร์
        try:
            pickup_dt = datetime.fromisoformat(booking_data['pickup_datetime'])
            dropoff_dt = datetime.fromisoformat(booking_data['dropoff_datetime'])
        except ValueError:
            # กันเหนียวเผื่อ format ผิด
            return redirect('car_detail', car_id=car_id)

        booking = Booking.objects.create(
            car=car,
            user=request.user if request.user.is_authenticated else None,
            guest=guest_instance,
            
            # ✅ แก้ไข: เอา # ออก และใช้ตัวแปรที่แปลงเป็น datetime แล้ว
            pickup_datetime=pickup_dt,
            dropoff_datetime=dropoff_dt,
            
            location=booking_data['location'],
            total_price=total_price,
            deposit_amount=deposit_amount,
            status='confirmed', 
            booking_ref=ref_code,
            discount_amount=discount_val,
        )

        # 5. ล้าง Session ทิ้ง
        if 'booking_context' in request.session:del request.session['booking_context']
        if 'guest_customer_id' in request.session:del request.session['guest_customer_id']

        # 6. ส่งไปหน้าสำเร็จ
        return redirect('booking_success', booking_id=booking.id)

    # ถ้าไม่ใช่ POST ให้กลับไปหน้า Payment
    return redirect('payment', car_id=car_id)

def booking_success(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    return render(request, 'car_rental/booking_success.html', {'booking': booking})


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
            return render(request, 'car_rental/booking_detail.html', {'booking': booking})

        except Booking.DoesNotExist:
            # ถ้าไม่เจอ -> แจ้งเตือน
            error_message = "ไม่พบข้อมูลการจอง หรือข้อมูลยืนยันตัวตนไม่ถูกต้อง"
            return render(request, 'car_rental/manage_booking.html', {'error': error_message})

    # ถ้าเป็น GET (เปิดหน้าเว็บเฉยๆ)
    return render(request, 'car_rental/manage_booking.html')

# car_rental/views.py



def apply_promotion(request, car_id):
    if request.method == 'POST':
        code = request.POST.get('promo_code').strip()
        booking_data = request.session.get('booking_context')
        
        # ถ้าไม่มีข้อมูลการจอง ให้กลับไปเริ่มใหม่
        if not booking_data:
            return redirect('car_detail', car_id=car_id)

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
                return redirect('payment', car_id=car_id)

            # 3. คำนวณส่วนลด
            # สมมติ discount_rate คือเปอร์เซ็นต์ (เช่น 10.00 คือ 10%)
            original_price = float(booking_data.get('original_total_price', booking_data['total_price'])) # ใช้ราคาเต็มตั้งต้น
            discount_value = original_price * (float(promo.discount_rate) / 100)
            
            new_total = original_price - discount_value
            
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
        
        return redirect('payment', car_id=car_id)
        
    return redirect('payment', car_id=car_id)


@login_required
def booking_history(request):
    # ดึงการจองของ user คนนี้ + เรียงจากล่าสุดไปเก่าสุด
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'car_rental/booking_history.html', {'bookings': bookings})