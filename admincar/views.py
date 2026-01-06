from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Sum
# ⚠️ Import Models ข้าม App (ต้องดึงมาจาก car_rental หรือที่ที่คุณเก็บ Model ไว้)
from car_rental.models import GuestCustomer, Payment, Booking, Car, User, Promotion
from django.utils import timezone
from datetime import timedelta


@staff_member_required(login_url='login')
def dashboard(request):
    # 1. Summary Cards (ตัวเลข)
    total_revenue = Payment.objects.filter(payment_status='COMPLETED').aggregate(Sum('amount'))['amount__sum'] or 0
    total_bookings_count = Booking.objects.count()
    total_cars_count = Car.objects.count()
    total_users_count = User.objects.count()

    # 2.1 กราฟรายเดือน (Bookings & Revenue) - ย้อนหลัง 6 เดือน
    today = timezone.now()
    month_labels = []
    booking_data = []
    revenue_data = []

    for i in range(5, -1, -1): # วนลูป 6 รอบ (0-5)
        # หาวันที่ของเดือนนั้นๆ
        date_cursor = today - timedelta(days=i*30) 
        month_name = date_cursor.strftime('%b') # เช่น Jan, Feb
        year = date_cursor.year
        month = date_cursor.month

        # เก็บชื่อเดือนไว้ในแกน X
        month_labels.append(month_name)

        # นับยอดจองในเดือนนั้น
        b_count = Booking.objects.filter(created_at__year=year, created_at__month=month).count()
        booking_data.append(b_count)

        # รวมรายได้ในเดือนนั้น (เฉพาะที่จ่ายสำเร็จ)
        r_sum = Payment.objects.filter(
            payment_status='COMPLETED', 
            payment_date__year=year, 
            payment_date__month=month
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        revenue_data.append(int(r_sum)) # แปลงเป็น int ให้กราฟอ่านง่าย

    # 2.2 กราฟสัดส่วนผู้ใช้ (Users Pie Chart)
    # Admin (Staff) vs Users vs Guest
    admin_count = User.objects.filter(is_staff=True).count()
    user_count = User.objects.filter(is_staff=False).count()
    guest_count = GuestCustomer.objects.count()
    user_pie_data = [admin_count, user_count, guest_count]

    # 2.3 กราฟสถานะรถ (Cars Bar Chart)
    # ว่าง vs ไม่ว่าง (ถูกจอง/ซ่อม)
    # สมมติสถานะคุณคือ 'available' กับอื่นๆ
    car_available = Car.objects.filter(status='available').count()
    car_busy = Car.objects.exclude(status='available').count()
    # หรือถ้ามีสถานะ 'maintenance'
    car_maintenace = Car.objects.filter(status='maintenance').count()
    
    car_status_data = [car_available, car_busy, car_maintenace]
    # 2. Data Lists (รายชื่อสำหรับตารางข้างล่าง)
    # ส่งไปทั้งหมดเลยครับ เดี๋ยวไปซ่อน/แสดงเอาใน HTML
    all_bookings = Booking.objects.select_related('user', 'car').order_by('-created_at')
    all_users = User.objects.all().order_by('-date_joined')
    all_cars = Car.objects.all().order_by('status')
    all_payments = Payment.objects.filter(payment_status='COMPLETED').order_by('-payment_date')

    # รายการรอตรวจสอบ (สำหรับ Sidebar)
    pending_payments = Payment.objects.filter(payment_status='WAITING_VERIFY')

    context = {
        # Counts
        'total_revenue': total_revenue,
        'total_bookings': total_bookings_count,
        'total_cars': total_cars_count,
        'total_users': total_users_count,
        
        # Lists
        'all_bookings': all_bookings,
        'all_users': all_users,
        'all_cars': all_cars,
        'all_payments': all_payments,
        
        # Charts Data (ส่งไปเป็น List)
        'month_labels': month_labels,   # แกน X (ชื่อเดือน)
        'booking_data': booking_data,   # แกน Y (ยอดจอง)
        'revenue_data': revenue_data,   # แกน Y (รายได้)
        'user_pie_data': user_pie_data, # [Admin, User, Guest]
        'car_status_data': car_status_data, # [ว่าง, ไม่ว่าง, ซ่อม]

        'pending_payments': pending_payments, # เอาไว้โชว์ตัวเลขแดงๆ ที่ sidebar
    }
    return render(request, 'admincar/dashboard.html', context)

@staff_member_required(login_url='/')
def verify_payment(request, payment_id, action):
    payment = get_object_or_404(Payment, id=payment_id)
    booking = payment.booking

    if action == 'approve':
        # ✅ อนุมัติ
        payment.payment_status = 'COMPLETED'
        payment.save()
        
        booking.status = 'confirmed' # จองสำเร็จ
        booking.save()
        messages.success(request, f"อนุมัติ Booking {booking.booking_ref} แล้ว")

    elif action == 'reject':
        # ❌ ปฏิเสธ
        payment.payment_status = 'FAILED'
        payment.save()
        
        booking.status = 'approved' # ตีกลับไปสถานะรอจ่ายเงินใหม่
        booking.save()
        messages.error(request, f"ปฏิเสธรายการ {booking.booking_ref}")

    # ทำเสร็จแล้วกลับมาหน้า Dashboard ของแอปนี้
    return redirect('admincar_dashboard')

@staff_member_required(login_url='login')
def delete_user(request, user_id):
    if request.method == "POST":
        user = get_object_or_404(User, id=user_id)
        
        # ป้องกันไม่ให้ลบ Superuser หรือตัวเอง
        if user.is_superuser or user == request.user:
            messages.error(request, "ไม่สามารถลบบัญชีผู้ดูแลระบบหลักหรือบัญชีของคุณเองได้")
        else:
            username = user.username
            user.delete()
            messages.success(request, f"ลบบัญชี {username} เรียบร้อยแล้ว")
            
    return redirect('admincar_dashboard')

# 1. หน้าแสดงรายการรถรออนุมัติ
@staff_member_required(login_url='login')
def approve_cars_list(request):
    # ดึงรถที่มีสถานะ 'pending' (รอตรวจสอบ)
    pending_cars = Car.objects.filter(status='pending').order_by('-created_at')
    
    context = {
        'pending_cars': pending_cars
    }
    return render(request, 'admincar/approve_cars.html', context)

# 2. ฟังก์ชันกดอนุมัติ
@staff_member_required(login_url='login')
def approve_car_action(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    car.status = 'available' # เปลี่ยนสถานะเป็นว่าง พร้อมเช่า
    car.save()
    messages.success(request, f"อนุมัติรถ {car.brand} {car.model} เรียบร้อยแล้ว")
    return redirect('approve_cars_list')

# 3. ฟังก์ชันกดลบ/ไม่อนุมัติ
@staff_member_required(login_url='login')
def reject_car_action(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    # ลบรถออกจากระบบ หรือจะเปลี่ยน status เป็น 'rejected' ก็ได้
    car.delete() 
    messages.warning(request, f"ลบรายการรถเรียบร้อยแล้ว")
    return redirect('approve_cars_list')

# 1. หน้าแสดงรายการสลิปที่รอตรวจสอบ
@staff_member_required(login_url='login')
def approve_payments_list(request):
    # ดึงรายการที่สถานะเป็น 'WAITING_VERIFY' (รอตรวจสอบสลิป)
    pending_payments = Payment.objects.filter(payment_status='WAITING_VERIFY').order_by('payment_date')
    
    context = {
        'pending_payments': pending_payments
    }
    return render(request, 'admincar/approve_payments.html', context)

# 2. ฟังก์ชันกด "ยืนยันยอดเงิน" (อนุมัติ)
@staff_member_required(login_url='login')
def confirm_payment_action(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    
    # อัปเดตสถานะการเงิน
    payment.payment_status = 'COMPLETED'
    payment.save()
    
    # อัปเดตสถานะการจองเป็น "สำเร็จ" (Confirmed)
    booking = payment.booking
    booking.status = 'confirmed'
    booking.save()
    
    messages.success(request, f"ยืนยันยอดเงิน Booking {booking.booking_ref} เรียบร้อยแล้ว")
    return redirect('approve_payments_list')

# 3. ฟังก์ชันกด "ปฏิเสธ/สลิปไม่ผ่าน"
@staff_member_required(login_url='login')
def reject_payment_action(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    
    # เปลี่ยนสถานะเป็น Failed หรือจะลบก็ได้ แล้วแต่ Flow งาน
    payment.payment_status = 'FAILED'
    payment.save()
    
    # แจ้งเตือน
    messages.warning(request, f"ปฏิเสธรายการแจ้งโอนของ {payment.booking.booking_ref}")
    return redirect('approve_payments_list')

@staff_member_required(login_url='login')
def promotion_list(request):
    if request.method == "POST":
        # รับค่าจากฟอร์ม
        code = request.POST.get('code').strip().upper()
        title = request.POST.get('title')
        description = request.POST.get('description')
        discount_rate = request.POST.get('discount_rate')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        usage_limit = request.POST.get('usage_limit')

        try:
            Promotion.objects.create(
                owner=request.user, # เจ้าของคือแอดมินคนปัจจุบัน
                code=code,
                title=title,
                description=description,
                discount_rate=discount_rate,
                start_date=start_date,
                end_date=end_date,
                usage_limit=usage_limit
            )
            messages.success(request, f"สร้างโปรโมชั่น {code} สำเร็จ!")
        except Exception as e:
            messages.error(request, f"เกิดข้อผิดพลาด: {e}")
        
        return redirect('promotion_list')

    promotions = Promotion.objects.all().order_by('-id')
    return render(request, 'admincar/promotion_list.html', {'promotions': promotions})

@staff_member_required(login_url='login')
def delete_promotion(request, promo_id):
    promo = get_object_or_404(Promotion, id=promo_id)
    promo.delete()
    messages.success(request, "ลบโปรโมชั่นเรียบร้อย")
    return redirect('promotion_list')