from django.urls import path
from . import views  # views นี้จะอ้างอิงถึง booking/views.py

urlpatterns = [
    # Flow การจอง (ผู้เช่า)
    path('user-info/<int:car_id>/', views.user_info, name='user_info'),
    path('checkout/<int:car_id>/', views.checkout, name='checkout'),
    
    # Flow การจ่ายเงิน
    path('payment/<int:booking_id>/', views.payment, name='payment'), # แก้ชื่อ view ให้ตรงกับที่ย้ายมา
    path('payment/process/<int:booking_id>/', views.process_payment, name='process_payment'),
    
    # หลังจองเสร็จ / ประวัติ / จัดการ
    path('success/<int:booking_id>/', views.booking_success, name='booking_success'),
    path('my-bookings/', views.booking_history, name='booking_history'),
    path('manage-booking/', views.manage_booking, name='manage_booking'),
    
    # โปรโมชั่น (ใช้ตอนจอง)
    path('user-info/<int:car_id>/apply-promo/', views.apply_promotion, name='apply_promotion'),

    # ส่วนของเจ้าของรถ (Host) จัดการคำขอเช่า
    path('booking-requests/', views.booking_requests, name='booking_requests'),
    path('update/<int:booking_id>/<str:action>/', views.update_booking_status, name='update_booking_status'),

    # urls.py
    path('manage-bookings/', views.manage_bookings, name='manage_bookings'),
]