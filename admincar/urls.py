from django.urls import path
from . import views

urlpatterns = [
    path('dashboard/', views.dashboard, name='admincar_dashboard'),
    path('verify/<int:payment_id>/<str:action>/', views.verify_payment, name='admincar_verify'),
    path('delete-user/<int:user_id>/', views.delete_user, name='delete_user'),
    path('approve-cars/', views.approve_cars_list, name='approve_cars_list'), # หน้าลิสต์
    path('approve-car/confirm/<int:car_id>/', views.approve_car_action, name='approve_car_action'), # กดอนุมัติ
    path('approve-car/reject/<int:car_id>/', views.reject_car_action, name='reject_car_action'), # กดลบ
    path('approve-payments/', views.approve_payments_list, name='approve_payments_list'),
    path('approve-payment/confirm/<int:payment_id>/', views.confirm_payment_action, name='confirm_payment_action'),
    path('approve-payment/reject/<int:payment_id>/', views.reject_payment_action, name='reject_payment_action'),
    path('promotions/', views.promotion_list, name='promotion_list'),
    path('promotions/delete/<int:promo_id>/', views.delete_promotion, name='delete_promotion'),
    # urls.py
    path('refunds/', views.admin_refund_dashboard, name='admin_refund_dashboard'),
    path('refunds/approve/<int:booking_id>/', views.admin_approve_refund, name='admin_approve_refund'),
]