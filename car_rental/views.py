# car_rental/views.py

from datetime import timezone
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from .forms import CarForm
from .models import Car , CarImage
from django.contrib import messages
import os
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect
from .models import Car, CarImage
from django.core.files.base import ContentFile
import base64
from django.db.models import Q # ใช้สำหรับ query ขั้นสูง


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
    cars = Car.objects.filter(status='AVAILABLE') # แสดงเฉพาะรถที่พร้อมใช้งาน
    context = {
        'cars': cars
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



@login_required
def car_search(request):

    service_type = request.GET.get("service_type", "SELF_DRIVE").strip()

    pickup = request.GET.get("pickup", "").strip()
    dropoff = request.GET.get("dropoff", "").strip()
    
    filter_car_type = request.GET.get("car_type", "").strip()

    start_date = request.GET.get("start_date")
    start_time = request.GET.get("start_time")
    end_date = request.GET.get("end_date")
    end_time = request.GET.get("end_time")

    # Base Query
    cars = Car.objects.filter(
        is_published=True,
        service_type=service_type,
    )

    # -------------------------------
    # 1) ค้นหาจุดรับรถ
    # -------------------------------
    if pickup:
        cars = cars.filter(
            Q(state__icontains=pickup) |
            Q(city__icontains=pickup) |
            Q(street_address__icontains=pickup)
        )

    # -------------------------------
    # 2) ค้นหาจุดคืนรถ
    # -------------------------------
    if dropoff:
        cars = cars.filter(
            Q(state__icontains=dropoff) |
            Q(city__icontains=dropoff) |
            Q(street_address__icontains=dropoff)
        )

    # -------------------------------
    # 3) ฟิลเตอร์ประเภทรถ
    # -------------------------------
    if filter_car_type:
        cars = cars.filter(car_type=filter_car_type)

    return render(request, "car_rental/car_search.html", {
        "cars": cars,
        "service_type": service_type,
        "pickup": pickup,
        "dropoff": dropoff,
        "car_type": filter_car_type,
    })

# car_rental/views.py





@login_required
def search_cars(request):

    # ------------------------------
    # ค่าที่ส่งมาจาก Search Form
    # ------------------------------
    search_location = request.GET.get("location", "")
    search_category = request.GET.get("category", "")
    search_date_from = request.GET.get("date_from", "")
    search_date_to = request.GET.get("date_to", "")

    # ------------------------------
    # เริ่มสร้าง Query
    # ------------------------------
    cars = Car.objects.filter(
        is_published=True,
        status="AVAILABLE"
    )

    # ------------------------------
    # Filter: ประเภทรถ
    # ------------------------------
    if search_category:
        category_map = {
            "sedan": "SEDAN",
            "pickup": "TRUCK",
            "van": "VAN",
            "ev": "EV",
        }
        if search_category in category_map:
            cars = cars.filter(car_type=category_map[search_category])

    # ------------------------------
    # Filter: สถานที่ (Match ได้ทั้ง จังหวัด / อำเภอ / ถนน)
    # ------------------------------
    if search_location:
        cars = cars.filter(
            Q(street_address__icontains=search_location) |
            Q(city__icontains=search_location) |
            Q(state__icontains=search_location)
        )

    # (ถ้าต้องการตรวจ availability วัน–เวลา ต้องทำเพิ่มภายหลัง)

    # ------------------------------
    # ส่งค่าไปหน้า Template
    # ------------------------------
    return render(request, "car_rental/search_cars.html", {
        "cars": cars,
        "search_location": search_location,
        "search_category": search_category,
        "search_date_from": search_date_from,
        "search_date_to": search_date_to,
    })
