# car_rental/views.py

from datetime import timezone
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib.auth.decorators import login_required
from .forms import CarForm
from .models import Car , CarImage
from django.contrib import messages

@login_required
def add_car_step1(request):
    car_id = request.session.get('car_id')

    # ถ้ามี car_id อยู่แล้ว ให้ใช้รถคันเดิม
    if car_id:
        car = get_object_or_404(Car, id=car_id, owner=request.user)
    else:
        # ถ้ายังไม่มี ให้สร้างใหม่
        car = Car.objects.create(owner=request.user)
        request.session['car_id'] = car.id

    if request.method == 'POST':
        car.car_type = request.POST.get('car_type')
        car.save()
        return redirect('add_car_step2')

    context = {'car': car}
    return render(request, 'car_rental/add_car_step1.html', context)


@login_required
def add_car_step2(request):
    car_id = request.session.get('car_id')
    if not car_id:
        return redirect('add_car_step1')

    car = get_object_or_404(Car, id=car_id, owner=request.user)

    if request.method == 'POST':
        car.service_type = request.POST.get('service_type')
        car.save()
        return redirect('add_car_step3')

    context = {'car': car}
    return render(request, 'car_rental/add_car_step2.html', context)


@login_required
def add_car_step3(request):
    car_id = request.session.get('car_id')
    if not car_id:
        return redirect('add_car_step1')

    car = get_object_or_404(Car, id=car_id, owner=request.user)

    if request.method == 'POST':
        country = request.POST.get('country')
        car.country = country if country else "ประเทศไทย"  
        car.street_address = request.POST.get('street_address')
        car.city = request.POST.get('city')
        car.state = request.POST.get('state')
        car.zip_code = request.POST.get('zip_code')
        car.save()
        return redirect('add_car_step4')

    context = {'car': car}
    return render(request, 'car_rental/add_car_step3.html', context)


@login_required
def add_car_step4(request):
    car_id = request.session.get('car_id')
    if not car_id:
        car = Car.objects.create(owner=request.user)
        request.session['car_id'] = car.id
    else:
        car = get_object_or_404(Car, id=car_id, owner=request.user)

    if request.method == 'POST':
        # ✅ ลบรูปเก่าที่เลือกให้ลบ
        delete_ids = request.POST.get('delete_existing_ids', '').split(',')
        if delete_ids and delete_ids[0] != '':
            CarImage.objects.filter(car=car, id__in=delete_ids).delete()

        # ✅ เพิ่มรูปใหม่
        images = request.FILES.getlist('images')
        for img in images:
            CarImage.objects.create(car=car, image=img)

        # ✅ ตรวจสอบว่ารูปรวม >= 5
        if car.images.count() < 5:
            messages.warning(request, "กรุณาเลือกรูปอย่างน้อย 5 รูป")
            return redirect('add_car_step4')

        messages.success(request, f"อัปโหลดรูปภาพสำเร็จ ({car.images.count()} รูป)")
        return redirect('add_car_step5')

    return render(request, 'car_rental/add_car_step4.html', {'car': car})



@login_required
def add_car_step5(request):
    car_id = request.session.get('car_id')
    if not car_id:
        messages.error(request, "ไม่พบข้อมูลรถ")
        return redirect('add_car_step1')

    car = get_object_or_404(Car, id=car_id, owner=request.user)

    if request.method == 'POST':
        car_name = request.POST.get('name')
        description = request.POST.get('description')

        try:
            brand, model = car_name.split(' ', 1)
        except ValueError:
            brand = car_name
            model = ''

        car.brand = brand
        car.model = model
        car.description = description
        car.save()

        return redirect('add_car_step6')

    # ✅ ตอน render กลับมา ให้ preload ค่าที่เคยกรอกไว้
    context = {
        'car': car
    }
    return render(request, 'car_rental/add_car_step5.html', context)

@login_required
def add_car_step6(request):
    car_id = request.session.get('car_id')
    if not car_id:
        messages.error(request, "ไม่พบข้อมูลรถที่คุณกำลังเพิ่ม")
        return redirect('add_car_step1')

    car = get_object_or_404(Car, id=car_id, owner=request.user)

    if request.method == 'POST':
        car.license_plate = request.POST.get('license_plate')
        car.num_doors = request.POST.get('num_doors')
        car.num_luggage = request.POST.get('num_luggage')
        car.fuel_system = request.POST.get('fuel_system')
        car.has_child_seat = 'has_child_seat' in request.POST
        car.accessory_price = request.POST.get('accessory_price') or 0
        car.min_rental_days = request.POST.get('min_rental_days')
        car.max_rental_days = request.POST.get('max_rental_days')
        car.save()

        messages.success(request, "บันทึกข้อมูลรถเรียบร้อยแล้ว!")
        return redirect('add_car_step7')  # ไปหน้าแสดงรถของฉัน
    context = {'car': car}
    return render(request, 'car_rental/add_car_step6.html', context)

@login_required
def add_car_step7(request):
    car_id = request.session.get('car_id')
    if not car_id:
        messages.error(request, "ไม่พบข้อมูลรถที่คุณกำลังเพิ่ม")
        return redirect('add_car_step1')

    car = get_object_or_404(Car, id=car_id, owner=request.user)

    if request.method == 'POST':
        price = request.POST.get('price')
        discount_option = request.POST.get('discount_option')

        if not price:
            messages.error(request, "กรุณากรอกราคาต่อวัน")
            return redirect('add_car_step7')

        car.price_per_day = price
        car.discount_option = discount_option
        car.status = 'PENDING'  # ✅ ยังไม่ลงประกาศ
        car.save()

        messages.success(request, "บันทึกราคาและส่วนลดเรียบร้อยแล้ว!")
        return redirect('add_car_preview', car_id=car.id)  # ไปหน้า Preview
    context = {'car': car}
    return render(request, 'car_rental/add_car_step7.html', context)


# (เพิ่มฟังก์ชันนี้เข้าไปใน views.py)
@login_required
def add_car_preview(request, car_id):
    # ดึงรถของผู้ใช้พร้อมรูปภาพทั้งหมด ไม่ต้องกรอง status
    car = get_object_or_404(Car.objects.prefetch_related('images'), id=car_id, owner=request.user)
    
    context = {
        'car': car,
        'images': car.images.all(),  # เพิ่มตัวแปรนี้เพื่อให้มั่นใจว่าภาพโหลดแน่
    }
    return render(request, 'car_rental/add_car_preview.html', context)


@login_required
def dashboard(request):

    # ----------- ลบรถจากปุ่มในหน้า Dashboard ----------- #
    if request.method == "POST":
        car_id = request.POST.get("delete_car_id")
        if car_id:
            car = get_object_or_404(Car, id=car_id, owner=request.user)
            car.delete()
            return redirect("dashboard")  # กลับสู่หน้าดashboardหลังลบเสร็จ

    # ----------- แสดงรายการรถของผู้ใช้ ----------- #
    my_cars = Car.objects.filter(owner=request.user).order_by('-id')

    context = {
        'cars': my_cars
    }
    return render(request, 'car_rental/dashboard.html', context)

# (เพิ่มฟังก์ชันนี้เข้าไปใน views.py)
@login_required
def publish_car(request, car_id):
    if request.method == 'POST':
        try:
            car_to_publish = Car.objects.get(id=car_id, owner=request.user, status='PENDING')
        except Car.DoesNotExist:
            messages.error(request, 'ไม่พบรถที่ต้องการลงประกาศ')
            return redirect('add_car_preview')

        # (เปลี่ยนสถานะเป็น "พร้อมใช้งาน")
        car_to_publish.status = 'AVAILABLE'
        car_to_publish.save()

        # (ล้าง Session - จบกระบวนการ)
        try:
            del request.session['add_car_data']
        except KeyError:
            pass
        
        messages.success(request, 'ลงประกาศรถของคุณสำเร็จแล้ว!')
        return redirect('dashboard') # (กลับหน้าหลัก)
    else:
        # ถ้าเข้าหน้านี้ตรงๆ (ไม่ใช่ POST) ให้กลับไปหน้า Preview
        return redirect('car_preview', car_id=car_id)
    
    
# View สำหรับแสดงรถทั้งหมด
def car_list(request):
    cars = Car.objects.filter(status='AVAILABLE') # แสดงเฉพาะรถที่พร้อมใช้งาน
    context = {
        'cars': cars
    }
    return render(request, 'car_rental/car_list.html', context)

# View สำหรับเพิ่มรถ (ต้อง Login ก่อน)
@login_required
def add_car(request):
    # อาจจะเพิ่มเงื่อนไขเช็คว่าเป็น Owner หรือไม่
    # if request.user.profile.role != 'OWNER':
    #     return redirect('car-list') 

    if request.method == 'POST':
        form = CarForm(request.POST)
        if form.is_valid():
            car = form.save(commit=False) # สร้าง object รถ แต่ยังไม่บันทึกลง DB
            car.owner = request.user      # กำหนดให้เจ้าของคือ user ที่ login อยู่
            car.save()                    # บันทึกลง DB
            messages.success(request, 'เพิ่มรถของคุณสำเร็จแล้ว!')
            return redirect('car_list') # กลับไปที่หน้ารายการรถ
    else:
        form = CarForm()

    context = {
        'form': form
    }
    return render(request, 'car_rental/add_car.html', context)