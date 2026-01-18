# car_rental/views.py

from datetime import timezone
import uuid
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from .models import Booking, Car , CarImage, Promotion, RenterReply, RenterReview, Review,  ReviewReply
from django.contrib import messages
import os
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect
from .models import Car, CarImage
from django.core.files.base import ContentFile
import base64
from django.db.models import Q # ใช้สำหรับ query ขั้นสูง
from car_rental.utils import build_rental_context 
from datetime import datetime # อย่าลืม import ตัวนี้ข้างบนไฟล์
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.db.models import Count, Sum, Q            # ✅ Import เพิ่ม
from django.db.models.functions import Coalesce       # ✅ Import เพิ่ม
from django.utils import timezone
from car_rental.models import Car, CarImage
from django.db.models import Count, Sum, Q, DecimalField  # ✅ เพิ่ม DecimalField

from django.db.models import Value
from django.db.models.functions import Coalesce, TruncMonth
from django.db.models import Count, Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce
from django.utils import timezone
import json
@login_required
def add_car_preview(request):
    draft = request.session.get('car_draft')

    if not draft:
        messages.error(request, "ไม่พบข้อมูลรถ")
        return redirect('add_car_step1')

    return render(request, 'car_rental/add_car_preview.html', {'draft': draft})


@login_required
def dashboard(request):
    
    # ----------------------------------------------------
    # ส่วนที่ 1: จัดการ POST (ลบ/แก้ไข รถ)
    # ----------------------------------------------------
    if request.method == "POST":
        if 'delete_car_id' in request.POST:
            car_id = request.POST.get("delete_car_id")
            car = get_object_or_404(Car, id=car_id, owner=request.user)
            car.delete()
            messages.success(request, 'ลบรถเรียบร้อยแล้ว')
            return redirect("dashboard")

        elif 'edit_car_id' in request.POST:
            car_id = request.POST.get("edit_car_id")
            car = get_object_or_404(Car, id=car_id, owner=request.user)
            
            # รับค่าจากฟอร์ม
            car.brand = request.POST.get('brand')
            car.model = request.POST.get('model')
            car.license_plate = request.POST.get('license_plate')
            car.price_per_day = request.POST.get('price')
            car.description = request.POST.get('description')

            # จัดการรูปภาพ
            new_image = request.FILES.get('new_image')
            if new_image:
                if car.images.exists():
                    img_obj = car.images.first()
                    img_obj.image = new_image
                    img_obj.save()
                else:
                    CarImage.objects.create(car=car, image=new_image)
                    
            if car.status != 'PENDING':
                new_status = request.POST.get('status')
                if new_status in ['AVAILABLE', 'MAINTENANCE']:
                    car.status = new_status 

            car.save()
            messages.success(request, 'แก้ไขข้อมูลรถเรียบร้อยแล้ว')
            return redirect("dashboard")
        
    # ----------------------------------------------------
    # ส่วนที่ 2: ดึงข้อมูลเพื่อแสดงผล (GET)
    # ----------------------------------------------------
    user = request.user    
    now = timezone.now()

    # 1. ข้อมูลรถ (My Cars)
    my_cars = Car.objects.filter(owner=user).annotate(
        booking_count=Count('booking', filter=Q(booking__status__in=['confirmed', 'picked_up', 'completed'])),
        total_income=Coalesce(
            Sum('booking__total_price', filter=Q(booking__status__in=['confirmed', 'picked_up', 'completed'])), 
            Value(0), 
            output_field=DecimalField()
        ),
        active_booking_count=Count('booking', filter=
            Q(booking__status='picked_up') | 
            Q(booking__status='confirmed', booking__pickup_datetime__lte=now, booking__dropoff_datetime__gte=now)
        )
    ).order_by('-id')

    # 2. ข้อมูล Card สรุปยอด
    total_cars = my_cars.count()
    total_bookings = Booking.objects.filter(car__owner=user).count()
    total_revenue = sum(c.total_income for c in my_cars)
    
    # 3. ข้อมูลกราฟรายเดือน (Multi-Line Chart & Total Days)
    raw_bookings = Booking.objects.filter(
        car__owner=user, 
        status__in=['confirmed', 'picked_up', 'completed']
    ).select_related('car').order_by('pickup_datetime')
    
    # ตัวแปรสำหรับคำนวณ
    type_monthly_data = {}  # เก็บยอดแยกตามประเภทรถ { 'Sedan': {(2024,1): 5}, ... }
    monthly_revenue = {}    # เก็บรายได้รวมรายเดือน
    total_days_booked = 0   # เก็บจำนวนวันเช่ารวมทั้งหมด
    all_months = set()      # เก็บเดือนที่มีการจองทั้งหมด

    for b in raw_bookings:
        local_date = timezone.localtime(b.pickup_datetime)
        month_key = (local_date.year, local_date.month)
        all_months.add(month_key)
        
        # 3.1 คำนวณวันเช่า
        duration = (b.dropoff_datetime - b.pickup_datetime).days
        if duration < 1: duration = 1
        total_days_booked += duration

        # 3.2 เก็บรายได้รวมรายเดือน
        monthly_revenue[month_key] = monthly_revenue.get(month_key, 0) + float(b.total_price)

        # 3.3 แยกประเภทรถ (สำหรับกราฟเส้นหลายสี)
        # เช็คว่า field ใน model ชื่อ car_type หรือไม่ (ถ้าชื่ออื่นให้แก้ตรงนี้)
        c_type = getattr(b.car, 'car_type', 'ไม่ระบุ') 
        if not c_type: c_type = "ไม่ระบุ"

        if c_type not in type_monthly_data:
            type_monthly_data[c_type] = {}
        
        type_monthly_data[c_type][month_key] = type_monthly_data[c_type].get(month_key, 0) + 1

    # เตรียมข้อมูลส่งให้ Chart.js
    thai_months = ["", "ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    sorted_months = sorted(list(all_months))
    
    # แกน X (เดือน)
    chart_labels = [f"{thai_months[m]} {y+543}" for y, m in sorted_months]
    
    # ข้อมูลกราฟรายได้ (Bar Chart)
    chart_revenue_data = [monthly_revenue.get(k, 0) for k in sorted_months]

    # ข้อมูลกราฟเส้นหลายสี (Multi-Line Chart)
    multi_line_datasets = []
    colors = ['#47B3C4', '#FF6384', '#FFCE56', '#4BC0C0', '#9966FF', '#FF9F40'] # สีวนลูป
    
    for i, (c_type, months_data) in enumerate(type_monthly_data.items()):
        data_points = []
        for m_key in sorted_months:
            data_points.append(months_data.get(m_key, 0))
            
        dataset = {
            'label': c_type,
            'data': data_points,
            'borderColor': colors[i % len(colors)],
            'backgroundColor': colors[i % len(colors)],
            'fill': False,
            'tension': 0.4
        }
        multi_line_datasets.append(dataset)

    # 4. ข้อมูลกราฟประเภทรถ (Pie Chart) - ดึงจาก Booking โดยตรง
    car_types_qs = Booking.objects.filter(
        car__owner=user,
        status__in=['confirmed', 'picked_up', 'completed']
    ).values('car__car_type').annotate(
        income=Sum('total_price')
    ).order_by('-income')

    type_labels = []
    type_data = []
    for item in car_types_qs:
        t_name = item['car__car_type'] if item['car__car_type'] else 'ไม่ระบุ'
        type_labels.append(t_name)
        type_data.append(float(item['income'] or 0))

    # 5. ระบบแนะนำ (Recommendations)
    recommendations = []
    if total_revenue < 5000:
        recommendations.append("💡 เริ่มต้นได้ดี! ลองแชร์รูปรถสวยๆ ลง Social Media เพื่อเพิ่มยอดจองแรก")
    
    if any(c.booking_count == 0 for c in my_cars):
        recommendations.append("⚠️ มีรถบางคันยังไม่มียอดจอง ลองตรวจสอบราคาหรือเปลี่ยนรูปปกให้น่าสนใจขึ้น")
    
    # แนะนำรถที่ขายดีในเดือนล่าสุด
    if sorted_months:
        last_month_key = sorted_months[-1]
        best_type_now = None
        max_val = 0
        for c_type, m_data in type_monthly_data.items():
            count = m_data.get(last_month_key, 0)
            if count > max_val:
                max_val = count
                best_type_now = c_type
        
        if best_type_now:
            m_name = thai_months[last_month_key[1]]
            recommendations.append(f"📈 เดือน {m_name} รถประเภท '{best_type_now}' มาแรงที่สุด! เตรียมรถให้พร้อม")

    context = {
        'cars': my_cars,
        'total_cars': total_cars,
        'total_bookings': total_bookings,
        'total_days_booked': total_days_booked,
        'total_revenue': total_revenue,
        'recommendations': recommendations,
        
        # JSON Data
        'month_labels': chart_labels,
        'multi_line_data': multi_line_datasets, # ส่งข้อมูลเส้นหลายสี
        'revenue_data': chart_revenue_data,
        'type_labels': type_labels,
        'type_data': type_data,
    }
    return render(request, 'car_rental/dashboard.html', context)

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
    # 1. รับค่าเดิม
    province = request.GET.get('province', '').strip()
    service_type = request.GET.get('service_type', 'SELF_DRIVE')
    car_type = request.GET.get('car_type', '')

    # 2. ✅ (เพิ่ม) รับค่าวันที่จากช่องค้นหา
    pickup_str = request.GET.get('pickup_date')   # ชื่อ name ใน input html ต้องตรงกัน
    dropoff_str = request.GET.get('dropoff_date') 

    start_date = request.GET.get('start_date', '').strip()
    start_time = request.GET.get('start_time', '').strip()
    end_date = request.GET.get('end_date', '').strip()
    end_time = request.GET.get('end_time', '').strip()

    # 3. Query รถพื้นฐาน (เอารถที่สถานะว่าง และเปิดเผยแพร่)
    cars = Car.objects.filter(status='AVAILABLE', is_published=True)

    if service_type:
        cars = cars.filter(service_type=service_type)

    if province:
        cars = cars.filter(state__exact=province)

    if car_type:
        cars = cars.filter(car_type=car_type)

    # 4. ✅ (เพิ่ม) Logic ตัดรถที่มีคนจองแล้วออก
    if pickup_str and dropoff_str and start_date and start_time and end_date and end_time:
        try:
            # แปลง String เป็น Datetime (ปรับ format ตาม input ของคุณ)
            # ถ้า input เป็น date (2024-01-01) ให้ระวังเรื่องเวลา
            pickup_date = datetime.fromisoformat(pickup_str)
            dropoff_date = datetime.fromisoformat(dropoff_str)

            # ค้นหา Booking ที่ "ชน" กับช่วงเวลาที่ลูกค้าเลือก
            # สถานะเหล่านี้ถือว่ารถไม่ว่าง
            busy_statuses = ['approved', 'waiting_verify', 'confirmed', 'picked_up']
            
            # Logic: (Booking เริ่ม < วันคืนที่เลือก) AND (Booking จบ > วันรับที่เลือก)
            unavailable_car_ids = Booking.objects.filter(
                status__in=busy_statuses,
                pickup_datetime__lt=dropoff_date,
                dropoff_datetime__gt=pickup_date
            ).values_list('car_id', flat=True)

            # สั่ง Exclude (เอาออก) จากรายการรถ
            cars = cars.exclude(id__in=unavailable_car_ids)

        except ValueError:
            pass # กรณีลูกค้ากรอกวันที่ผิด format ก็ปล่อยผ่านไป (โชว์รถทั้งหมด)

    now = timezone.now().date()
    active_promotions = Promotion.objects.filter(
        is_active=True,
        start_date__lte=now,  # เริ่มแล้ว
        end_date__gte=now     # ยังไม่หมดอายุ
    ).order_by('-id')

    # หาตัวล่าสุดมา 1 อัน (สำหรับแสดงใน Banner ถ้ามี)
    latest_promo = active_promotions.first() if active_promotions.exists() else None
    context = {
        'cars': cars,
        'province': province,
        'search_service': service_type,
        'search_category': car_type,
        # ส่งค่ากลับไปเติมในฟอร์ม (เพื่อให้ User เห็นค่าเดิมที่เลือกไว้)
        'start_date': start_date,
        'start_time': start_time,
        'end_date': end_date,
        'end_time': end_time,
        # ส่งค่าวันที่กลับไปเติมในฟอร์มด้วย ลูกค้าจะได้ไม่ต้องกรอกใหม่
        'pickup_date': pickup_str,
        'dropoff_date': dropoff_str,
        # ✅ ส่งตัวแปรโปรโมชั่นไปให้หน้าเว็บ
        'promotions': active_promotions, 
        'latest_promo': latest_promo,
    }
    return render(request, 'car_rental/car_list.html', context)

# car_rental/views.py



@login_required
def add_car(request):
    if request.method == "POST":
        data = request.POST
        files = request.FILES  # ✅ รับไฟล์เอกสารจากตรงนี้

        # 1) สร้าง Car Object
        try:
            car = Car.objects.create(
                owner=request.user,
                brand=data.get("brand", ""),
                model=data.get("model", ""),
                year=data.get("year"), # ✅ เพิ่มปีรถ
                car_type=data.get("car_type", "SEDAN"),
                service_type=data.get("service_type", "SELF_DRIVE"),

                # Address
                country=data.get("country") or "ประเทศไทย",
                street_address=data.get("street_address") or "",
                city=data.get("city") or "",
                state=data.get("state") or "", # หรือ province=data.get("state") เช็คชื่อ field ใน model ดีๆ
                zip_code=data.get("zip_code") or "",
                
                # รายละเอียด
                num_seats=data.get("num_seats") or 5,
                num_doors=data.get("num_doors") or 4,
                num_luggage=data.get("num_luggage") or 2,
                fuel_system=data.get("fuel_system") or "GASOLINE",
                transmission=data.get("transmission") or "AUTO", # ✅ เพิ่มเกียร์ (ถ้ามีใน model)
                
                description=data.get("description", ""),
                rules=data.get("rules", ""),
                license_plate=data.get("license_plate", ""),
                
                # Options & Price
                has_child_seat=(data.get("has_child_seat") == "true"),
                accessory_price=data.get("accessory_price") or 0,
                min_rental_days=data.get("min_rental_days") or 1,
                max_rental_days=data.get("max_rental_days") or 30,
                price_per_day=data.get("price") or 0,
                discount_option=data.get("discount_option") or "NONE",

                # ✅ ส่วนสำคัญ: รับไฟล์เอกสาร (ไม่ใช่ Base64)
                doc_registration=files.get("doc_registration"),
                doc_insurance=files.get("doc_insurance"),
                doc_id_card=files.get("doc_id_card"),           # บัตรประชาชน
                
                status="PENDING",
                is_published=True,
            )

            # 2) รูปภาพรถ (Images) - อันนี้รับเป็น Base64 ถูกแล้ว
            images = request.POST.getlist("images_base64[]")

            for index, img64 in enumerate(images):
                if not img64:
                    continue
                if ";base64," in img64:
                    try:
                        format, imgstr = img64.split(';base64,') 
                        ext = format.split('/')[-1] 
                        
                        img_binary = base64.b64decode(imgstr)
                        CarImage.objects.create(
                            car=car,
                            image=ContentFile(img_binary, name=f"car_{car.id}_{index}.{ext}")
                        )
                    except Exception as e:
                        print(f"Error saving image {index}: {e}")
                        continue
            
            messages.success(request, "ลงประกาศรถของคุณสำเร็จแล้ว! กรุณารอการตรวจสอบจากแอดมิน")
            return redirect("dashboard") # หรือหน้าอื่นที่ต้องการ

        except Exception as e:
            # กรณีบันทึกไม่สำเร็จ ให้แจ้งเตือนและ print error ดูใน terminal
            print(f"Error creating car: {e}")
            messages.error(request, "เกิดข้อผิดพลาดในการบันทึกข้อมูล กรุณาลองใหม่อีกครั้ง")
            return redirect("add_car") # กลับมาหน้าเดิม

    # GET Request
    return render(request, "car_rental/add_car.html")




def search_cars(request):
    # 1. รับค่าจากหน้าแรก (ชื่อฟิลด์ตรงตามฟอร์ม)
    pickup = request.GET.get('pickup', '').strip()
    dropoff = request.GET.get('dropoff', '').strip()
    province = request.GET.get('province', '').strip()

    s_date = request.GET.get('start_date', '').strip()
    s_time = request.GET.get('start_time', '').strip()
    e_date = request.GET.get('end_date', '').strip()
    e_time = request.GET.get('end_time', '').strip()

    service_type = request.GET.get('service_type', 'SELF_DRIVE')
    car_type_filter = request.GET.get('car_type', '')

    # 2. เริ่มต้น Query (เอารถที่สถานะว่าง และเปิดเผยแพร่)
    cars = Car.objects.filter(status='AVAILABLE', is_published=True)

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
    if s_date and s_time and e_date and e_time:
        try:
            # แปลง format จาก d/m/Y H:i (เช่น 25/12/2025 10:00)
            pickup_dt = datetime.strptime(f"{s_date} {s_time}", "%d/%m/%Y %H:%M")
            dropoff_dt = datetime.strptime(f"{e_date} {e_time}", "%d/%m/%Y %H:%M")

            # สถานะที่ถือว่ารถไม่ว่าง
            busy_statuses = ['approved', 'waiting_verify', 'confirmed', 'picked_up']
            
            # ค้นหารถที่ชนช่วงเวลานี้
            unavailable_ids = Booking.objects.filter(
                status__in=busy_statuses,
                pickup_datetime__lt=dropoff_dt,  # จองใหม่เริ่มก่อนจองเก่าจบ
                dropoff_datetime__gt=pickup_dt   # จองใหม่จบหลังจองเก่าเริ่ม
            ).values_list('car_id', flat=True)

            # เอา ID รถที่ไม่ว่างออก
            cars = cars.exclude(id__in=unavailable_ids)

        except ValueError as e:
            print(f"Date Error: {e}")
            pass
    # 6. ส่งค่ากลับไปหน้า search_cars.html เพื่อใส่ค่ากลับลง input
    context = {
        'cars': cars,
        "province": province,
        # คืนค่าเดิมกลับไปให้ form จำค่าได้
        'search_location': pickup,
        'pickup': pickup,
        'dropoff': dropoff,
        'start_date': s_date,
        'start_time': s_time,
        'end_date': e_date,
        'end_time': e_time,
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

@login_required
def reply_to_car_review(request, review_id):
    review = get_object_or_404(Review, id=review_id)
    
    # ✅ Security Check: คนตอบต้องเป็น "เจ้าของรถ" เท่านั้น
    if request.user != review.car.owner:
        messages.error(request, "คุณไม่มีสิทธิ์ตอบกลับรีวิวนี้")
        return redirect('car_detail', car_id=review.car.id)

    if request.method == "POST":
        comment = request.POST.get('comment')
        ReviewReply.objects.create(
            review=review,
            user=request.user,
            comment=comment
        )
        messages.success(request, "ตอบกลับรีวิวเรียบร้อย")

    return redirect('car_detail', car_id=review.car.id)

# car_rental/views.py หรือ users/views.py

@login_required
def reply_to_owner_review(request, review_id):
    # ดึงรีวิวที่เจ้าของเขียนด่าเรา
    review = get_object_or_404(RenterReview, id=review_id)
    
    # ✅ Security Check: คนตอบต้องเป็น "ผู้เช่า (คนถูกรีวิว)" เท่านั้น
    if request.user != review.renter:
        messages.error(request, "คุณไม่มีสิทธิ์ตอบกลับ")
        return redirect('public_profile', user_id=review.renter.id)

    if request.method == "POST":
        comment = request.POST.get('comment')
        RenterReply.objects.create(
            renter_review=review,
            user=request.user,
            comment=comment
        )
        messages.success(request, "บันทึกคำตอบกลับแล้ว")

    return redirect('public_profile', user_id=review.renter.id)




