# car_rental/admin.py
from django.contrib import admin
from .models import Profile, Car, Promotion, Booking, Payment, Review

admin.site.register(Profile)
admin.site.register(Car)
admin.site.register(Promotion)
admin.site.register(Booking)
admin.site.register(Payment)
admin.site.register(Review)