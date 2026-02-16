from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.db.models import Sum
from booking.views import send_line_push
from car_rental.models import GuestCustomer, Payment, Booking, Car, User, Promotion
from django.utils import timezone
from datetime import timedelta
from django.conf import settings
from linebot import LineBotApi
from linebot.models import TextSendMessage

@staff_member_required(login_url='login')
def dashboard(request):
    # (ตัวเลข)
    total_revenue = Payment.objects.filter(payment_status='COMPLETED').aggregate(Sum('amount'))['amount__sum'] or 0
    total_bookings_count = Booking.objects.count()
    total_cars_count = Car.objects.count()
    total_users_count = User.objects.count()

    # กราฟรายเดือน (Bookings & Revenue) - ย้อนหลัง 6 เดือน
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
        revenue_data.append(int(r_sum)) # แปลงเป็น int

    # กราฟสัดส่วนผู้ใช้ (Users Pie Chart)
    admin_count = User.objects.filter(is_staff=True).count()
    user_count = User.objects.filter(is_staff=False).count()
    guest_count = GuestCustomer.objects.count()
    user_pie_data = [admin_count, user_count, guest_count]

    # กราฟสถานะรถ (Cars Bar Chart)
    # ว่าง vs ไม่ว่าง (ถูกจอง/ซ่อม)
    car_available = Car.objects.filter(status='available').count()
    car_busy = Car.objects.exclude(status='available').count()
    car_maintenace = Car.objects.filter(status='maintenance').count()
    
    car_status_data = [car_available, car_busy, car_maintenace]
    # (รายชื่อสำหรับตารางข้างล่าง)
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

#สลิปโอนเงินที่ลูกค้าส่งมา
@staff_member_required(login_url='/')
def verify_payment(request, payment_id, action):
    payment = get_object_or_404(Payment, id=payment_id)
    booking = payment.booking

    if action == 'approve':
        # อนุมัติ
        payment.payment_status = 'COMPLETED'
        payment.save()
        
        booking.status = 'confirmed' # จองสำเร็จ
        booking.save()
        messages.success(request, f"อนุมัติ Booking {booking.booking_ref} แล้ว")

    elif action == 'reject':
        # ปฏิเสธ
        payment.payment_status = 'FAILED'
        payment.save()
        
        booking.status = 'approved' # ตีกลับไปสถานะรอจ่ายเงินใหม่
        booking.save()
        messages.error(request, f"ปฏิเสธรายการ {booking.booking_ref}")

    return redirect('admincar_dashboard')

# ฟังก์ชันลบบัญชีผู้ใช้ (Admin)
@staff_member_required(login_url='login')
def delete_user(request, user_id):
    if request.method == "POST":
        user = get_object_or_404(User, id=user_id)
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

#หน้าจอรายการรถรออนุมัติ
#  ฟังก์ชันกดอนุมัติ
@staff_member_required(login_url='login')
def approve_car_action(request, car_id):
    car = get_object_or_404(Car, id=car_id)
    car.status = 'available' # เปลี่ยนสถานะเป็นว่าง พร้อมเช่า
    car.save()
    messages.success(request, f"อนุมัติรถ {car.brand} {car.model} เรียบร้อยแล้ว")
    return redirect('approve_cars_list')

#  ฟังก์ชันกดลบ/ไม่อนุมัติ
@staff_member_required(login_url='login')
def reject_car_action(request, car_id):
    if request.method == "POST":
        car = get_object_or_404(Car, id=car_id)
        #(แทนการลบ car.delete())
        car.status = 'REJECTED'
        car.save()
        
        messages.success(request, f"ดำเนินการไม่อนุมัติรถทะเบียน {car.license_plate} เรียบร้อยแล้ว")
        return redirect('approve_cars_list')

# หน้าแสดงรายการสลิปที่รอตรวจสอบ
@staff_member_required(login_url='login')
def approve_payments_list(request):
    pending_payments = Payment.objects.filter(payment_status='WAITING_VERIFY').order_by('payment_date')
    context = {
        'pending_payments': pending_payments
    }
    return render(request, 'admincar/approve_payments.html', context)

# ฟังก์ชันกด "ยืนยันยอดเงิน" (อนุมัติ)
line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
@staff_member_required(login_url='login')
def confirm_payment_action(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    payment.payment_status = 'COMPLETED'
    payment.save()
    
    # อัปเดตสถานะการจองเป็น "สำเร็จ" (Confirmed)
    booking = payment.booking
    booking.status = 'confirmed'
    booking.save()  
    try:
        if booking.user:
            user_profile = booking.user.profile
            # ตรวจสอบว่าลูกค้าคนนี้ "เคยเชื่อม LINE" ไว้หรือยัง
            if user_profile.line_id:
                msg_text = f"✅ อนุมัติการจองเรียบร้อย!\n\nBooking Ref: {booking.booking_ref}\nรถ: {booking.car.brand} {booking.car.model}\nวันที่รับรถ: {booking.pickup_date.strftime('%d/%m/%Y')}\n\nขอบคุณที่ใช้บริการครับ 🙏"               
                # ส่งหา user_profile.line_id (คนเดียว)
                line_bot_api.push_message(
                    user_profile.line_id, 
                    TextSendMessage(text=msg_text)
                )
                print(f"Sent LINE to {booking.user.username}")
            else:
                print("User has not linked LINE account yet.")
        else:
            print("This is a Guest booking (No LINE notification).")
            
    except Exception as e:
        print(f"LINE Notify Error: {e}")

    messages.success(request, f"ยืนยันยอดเงิน Booking {booking.booking_ref} เรียบร้อยแล้ว")
    return redirect('approve_payments_list')

# ฟังก์ชันกด "ปฏิเสธ/สลิปไม่ผ่าน"
@staff_member_required(login_url='login')
def reject_payment_action(request, payment_id):
    payment = get_object_or_404(Payment, id=payment_id)
    booking = payment.booking # ดึง booking ที่เกี่ยวข้องมาด้วย
    reason = request.POST.get('reject_reason', 'สลิปไม่ถูกต้อง')
    payment.payment_status = 'PENDING'
    payment.save()
    
    # สถานะ Booking กลับเป็น 'approved' (รอจ่ายเงิน)
    booking.status = 'approved'
    booking.save()
    
    try:
        if booking.user:
            user_profile = booking.user.profile
            if user_profile.line_id:
                msg_text = f"❌ ปฏิเสธการจอง\n\nBooking Ref: {booking.booking_ref}\nเหตุผล: {reason}\n\nกรุณาตรวจสอบและอัปโหลดสลิปใหม่ครับ 🙏"
                line_bot_api.push_message(
                    user_profile.line_id, 
                    TextSendMessage(text=msg_text)
                )
    except Exception as e:
        print(f"LINE Notify Error: {e}")

    messages.warning(request, f"ปฏิเสธรายการ {booking.booking_ref} เรียบร้อย: {reason}")
    return redirect('approve_payments_list')


#หน้าจัดการโปรโมชั่น
@staff_member_required(login_url='login')
def promotion_list(request):
    if request.method == "POST":
        # รับค่าจากฟอร์ม
        code = request.POST.get('code', '').strip().upper()
        title = request.POST.get('title')
        description = request.POST.get('description')
        discount_rate = request.POST.get('discount_rate')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        usage_limit = request.POST.get('usage_limit')

        try:
            # เช็คว่าโค้ดซ้ำไหม
            if Promotion.objects.filter(code=code).exists():
                messages.error(request, f"โค้ด '{code}' มีอยู่ในระบบแล้ว กรุณาตั้งชื่ออื่น")
                return redirect('promotion_list')

            # สร้าง Promotion (เพิ่ม int() และ default fields)
            Promotion.objects.create(
                owner=request.user,
                code=code,
                title=title,
                description=description,
                discount_rate=int(discount_rate), # แปลงเป็นตัวเลข
                start_date=start_date,
                end_date=end_date,
                usage_limit=int(usage_limit),     # แปลงเป็นตัวเลข
                
                used_count=0,    # เริ่มต้นที่ 0 เสมอ
                is_active=True   # สร้างแล้วให้ใช้งานได้ทันที
            )
            messages.success(request, f"สร้างโปรโมชั่น {code} สำเร็จ!")
            
        except ValueError:
            messages.error(request, "กรุณากรอกตัวเลขในช่อง 'ส่วนลด' หรือ 'จำกัดสิทธิ์' ให้ถูกต้อง")
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


#  หน้า Dashboard ดูรายการขอคืนเงิน
@staff_member_required(login_url='login')
def admin_refund_dashboard(request):
                                                # ลูกค้ายกเลิกและขอคืนเงินแล้ว
    refunds_qs = Booking.objects.filter(status='refund_requested').order_by('created_at')
    
    #วนลูปเพื่อจัดรูปแบบตัวเลขใน Python (ตัดปัญหา Template Error)
    refunds = []
    for booking in refunds_qs:
        amount = 0
        if hasattr(booking, 'payment'):
            amount = booking.payment.amount
            
        # สร้างตัวแปรใหม่
        booking.amount_display = f"{amount:,.2f}" 
        refunds.append(booking)
    
    return render(request, 'admincar/refund_dashboard.html', {'refunds': refunds})

# ฟังก์ชันกด "ยืนยันการคืนเงิน"
@staff_member_required(login_url='login')
def admin_approve_refund(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id)
    
    if request.method == 'POST':
        # 1. เปลี่ยนสถานะ
        booking.status = 'cancelled'
        if hasattr(booking, 'payment'):
            booking.payment.payment_status = 'REFUNDED'
            booking.payment.save()
        booking.save()

        # 2. แจ้งเตือน LINE ลูกค้า
        if hasattr(booking.user, 'profile') and booking.user.profile.line_id:
            refund_val = booking.payment.amount if hasattr(booking, 'payment') else 0
            msg = (
                f"💰 แจ้งโอนเงินคืนเรียบร้อย (โดย Admin)\n"
                f"Ref: #{booking.booking_ref}\n"
                f"ยอดเงิน: {refund_val:,.2f} บาท\n"
                f"โอนเข้า: {booking.refund_bank_name} - {booking.refund_account_no}"
            )
            send_line_push(booking.user.profile.line_id, msg)
            
        messages.success(request, "บันทึกสถานะการคืนเงินเรียบร้อย")

    return redirect('admin_refund_dashboard')