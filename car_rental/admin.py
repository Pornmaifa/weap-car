# car_rental/admin.py
from django.contrib import admin
from .models import Profile, Car, Promotion, Booking, Payment, Review, GuestCustomer, PlatformSetting

admin.site.register(Profile)
admin.site.register(Car)
admin.site.register(Promotion)
admin.site.register(Booking)
admin.site.register(Payment)
admin.site.register(Review)
admin.site.register(GuestCustomer)
@admin.register(PlatformSetting)
class PlatformSettingAdmin(admin.ModelAdmin):
    # ลบปุ่ม add ทิ้ง ถ้ามี setting อยู่แล้ว 1 อัน (เพื่อบังคับให้มีแค่อันเดียว)
    def has_add_permission(self, request):
        if PlatformSetting.objects.exists():
            return False
        return True

    list_display = ('commission_rate', 'updated_at')