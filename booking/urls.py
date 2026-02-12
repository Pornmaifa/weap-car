from django.urls import path
from . import views  # views นี้จะอ้างอิงถึง booking/views.py

urlpatterns = [
    # Flow การจอง (ผู้เช่า)
    path('user-info/<int:car_id>/', views.user_info, name='user_info'),
    path('checkout/<int:car_id>/', views.checkout, name='checkout'),
    
    # Flow การจ่ายเงิน
    path('payment/<int:booking_id>/', views.payment_page, name='payment_page'), # แก้ชื่อ view ให้ตรงกับที่ย้ายมา
   
    
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
    path('booking/update/<int:booking_id>/<str:action>/', views.update_booking_status, name='update_booking_status'),

    path('booking/inspection/<int:booking_id>/', views.inspection_page, name='inspection_page'),
    
    # Path สำหรับลูกค้ารีวิว
    path('review/car/<int:booking_id>/', views.submit_car_review, name='submit_car_review'),
    
    # Path สำหรับเจ้าของรีวิว
    path('review/renter/<int:booking_id>/', views.submit_renter_review, name='submit_renter_review'),
    
    # Path สำหรับกดใช้โค้ด
    path('apply-promotion/<int:car_id>/', views.apply_promotion, name='apply_promotion'),
    
    # Path สำหรับกดยกเลิกโค้ด (ถ้าต้องการ)
    path('remove-promotion/<int:car_id>/', views.remove_promotion, name='remove_promotion'),

    path('cancel/<int:booking_id>/', views.cancel_booking, name='cancel_booking'),
    path('refund/<int:booking_id>/', views.request_refund, name='request_refund'),

    path('booking/detail/<int:booking_id>/', views.booking_detail, name='booking_detail'),

    path('booking/cancel-now/<int:booking_id>/', views.cancel_booking_immediately, name='cancel_now'),
]