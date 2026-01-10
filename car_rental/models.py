# car_rental/models.py

from django.db import models
from django.contrib.auth.models import User # ดึงโมเดล User ของ Django มาใช้
from django.conf import settings
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import datetime
# ตาราง Profile ที่รวม Owner และ Member เข้าด้วยกัน
class Profile(models.Model):
    ROLE_CHOICES = (
        ('MEMBER', 'Member'),
        ('OWNER', 'Owner'),
    )
    user = models.OneToOneField(User, on_delete=models.CASCADE, primary_key=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='MEMBER')
    status = models.CharField(max_length=50, default='active')
    # Fields for Member
    address = models.TextField(blank=True, null=True)
    license_no = models.CharField(max_length=100, blank=True, null=True)
    join_date = models.DateField(auto_now_add=True)
    # Fields for Owner
    approved_status = models.CharField(max_length=20, default='pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_owners')
    approved_date = models.DateField(null=True, blank=True)
    # เพิ่ม field ใหม่สำหรับรูปโปรไฟล์
    image = models.ImageField(upload_to='profile_pics', null=True, blank=True)
    #  (เอาไว้เก็บ LINE ID ของลูกค้า)
    line_id = models.CharField(max_length=100, blank=True, null=True)
    def __str__(self):
        return f'{self.user.username} Profile'

# ตาราง Car
from django.db import models
from django.contrib.auth.models import User

from django.db import models
from django.contrib.auth.models import User # หรือ get_user_model() ถ้าใช้ Custom User

class Car(models.Model):
    # ==========================
    # 1. CHOICES CONSTANTS
    # ==========================
    CAR_TYPE_CHOICES = [
        ('SEDAN', 'รถเก๋งขนาดเล็ก'),
        ('TRUCK', 'รถกระบะ'),
        ('VAN', 'รถตู้'),
        ('EV', 'รถไฟฟ้า'),
    ]

    STATUS_CHOICES = [
        ('PENDING', 'รอดำเนินการตรวจสอบ'), # Default ควรเป็นอันนี้
        ('AVAILABLE', 'พร้อมใช้งาน'),
        ('BOOKED', 'ถูกจองแล้ว'),
        ('MAINTENANCE', 'ซ่อมบำรุง'),
        ('REJECTED', 'ไม่อนุมัติ'), # เผื่อ Admin ปฏิเสธ
    ]

    SERVICE_TYPE_CHOICES = [
        ('SELF_DRIVE', 'ขับเอง'),
        ('WITH_DRIVER', 'พร้อมคนขับ'),
    ]

    DISCOUNT_CHOICES = [
        ('NONE', 'ไม่มีส่วนลด'),
        ('FIRST_TIMER_20', 'ส่วนลด 20% สำหรับผู้เช่าครั้งแรก'),
        ('WEEKLY_10', 'เช่า 7 วัน ลด 10%'),
    ]

    FUEL_CHOICES = [
        ('GASOLINE', 'เบนซิน'),
        ('DIESEL', 'ดีเซล'),
        ('LPG', 'LPG'),
        ('NGV', 'NGV'),
        ('ELECTRIC', 'ไฟฟ้า (EV)'),
        ('HYBRID', 'ไฮบริด'),
    ]

    # ✅ เพิ่มใหม่: ระบบเกียร์
    TRANSMISSION_CHOICES = [
        ('AUTO', 'เกียร์อัตโนมัติ'),
        ('MANUAL', 'เกียร์ธรรมดา'),
    ]

    # ==========================
    # 2. CORE FIELDS (เจ้าของ & สถานะ)
    # ==========================
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cars')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    is_published = models.BooleanField(default=False) # True = แสดงหน้าร้าน, False = ซ่อน/Draft
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True) # ✅ เพิ่ม: วันที่สร้าง
    updated_at = models.DateTimeField(auto_now=True)     # ✅ เพิ่ม: วันที่แก้ไขล่าสุด

    # ==========================
    # 3. CAR DETAILS (ข้อมูลรถ)
    # ==========================
    brand = models.CharField(max_length=50, verbose_name="ยี่ห้อ") # เช่น Toyota
    model = models.CharField(max_length=50, verbose_name="รุ่น")   # เช่น Yaris Ativ
    year = models.PositiveIntegerField(null=True, blank=True, verbose_name="ปีจดทะเบียน")
    description = models.TextField(max_length=500, null=True, blank=True, verbose_name="คำอธิบายรถ")
    
    car_type = models.CharField(max_length=10, choices=CAR_TYPE_CHOICES, default='SEDAN')
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, default='SELF_DRIVE')
    license_plate = models.CharField(max_length=100, default='', help_text="ทะเบียนรถ (Admin only)")

    # ==========================
    # 4. SPECS & FEATURES (สเปค)
    # ==========================
    transmission = models.CharField(max_length=10, choices=TRANSMISSION_CHOICES, default='AUTO', verbose_name="ระบบเกียร์") # ✅ เพิ่ม
    fuel_system = models.CharField(max_length=20, choices=FUEL_CHOICES, default='GASOLINE')
    num_doors = models.PositiveIntegerField(default=4, verbose_name="จำนวนประตู")
    num_luggage = models.PositiveIntegerField(default=2, verbose_name="จำนวนสัมภาระ")
    doc_id_card = models.ImageField(upload_to='car_documents/', null=True, blank=True, verbose_name="สำเนาบัตรประชาชน")
    # Accessories
    has_child_seat = models.BooleanField(default=False)
    accessory_price = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="ราคาอุปกรณ์เสริมต่อวัน")

    # ==========================
    # 5. LOCATION (สถานที่รับรถ)
    # ==========================
    country = models.CharField(max_length=100, default='ประเทศไทย')
    street_address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True) # เขต/อำเภอ
    state = models.CharField(max_length=100, null=True, blank=True) # จังหวัด
    zip_code = models.CharField(max_length=10, null=True, blank=True)
    
    # (Optional) ถ้าอนาคตจะทำ Map แนะนำให้เพิ่ม lat/long
    # latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    # longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)

    # ==========================
    # 6. PRICING & RULES (ราคา & กฎ)
    # ==========================
    price_per_day = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    discount_option = models.CharField(max_length=50, choices=DISCOUNT_CHOICES, default='NONE')
    min_rental_days = models.PositiveIntegerField(default=1)
    max_rental_days = models.PositiveIntegerField(default=30)

    # ==========================
    # 7. DOCUMENTS (เอกสารยืนยัน - Admin Only)
    # ==========================
    #  เอกสารสำคัญ (ใช้ FileField เผื่อเป็น PDF)
    doc_registration = models.FileField(upload_to='car_docs/registration/', null=True, blank=True, verbose_name="เล่มทะเบียน")
    doc_insurance = models.FileField(upload_to='car_docs/insurance/', null=True, blank=True, verbose_name="กรมธรรม์")
    
    num_seats = models.PositiveIntegerField(default=5) 
    rules = models.TextField(blank=True, null=True)   

   
   
    def __str__(self):
        return f'{self.brand} {self.model} ({self.license_plate})'

    class Meta:
        ordering = ['-created_at'] # เรียงจากรถที่เพิ่มล่าสุดก่อน


class CarImage(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='car_images/')
    is_cover = models.BooleanField(default=False) # ✅ (Optional) เพิ่มเพื่อให้เจ้าของเลือกรูปปกได้
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Image for {self.car.brand} {self.car.model}"


# ตาราง Booking
class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'รออนุมัติจากเจ้าของรถ'),    # 1. จองมา
        ('approved', 'อนุมัติแล้ว (รอชำระเงิน)'), # 2. เจ้าของกดรับ
        ('waiting_verify', 'แจ้งโอนแล้ว (รอตรวจสอบ)'),
        ('confirmed', 'จองสำเร็จ'),             # 3. จ่ายเงินแล้ว
        ('rejected', 'ปฏิเสธ'),                 # เจ้าของไม่รับ
        ('cancelled', 'ยกเลิก'),                # ลูกค้ายกเลิกเอง
        ('completed', 'จบการเช่า'),              # คืนรถแล้ว
    ]

    car = models.ForeignKey('Car', on_delete=models.CASCADE)
    # ถ้าเป็นสมาชิกใช้ user ถ้าเป็นลูกค้าทั่วไปใช้ guest
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    guest = models.ForeignKey('GuestCustomer', on_delete=models.CASCADE, null=True, blank=True)
    
    pickup_datetime = models.DateTimeField()
    dropoff_datetime = models.DateTimeField()
    location = models.CharField(max_length=200)
    
    # เรื่องเงิน
    total_price = models.DecimalField(max_digits=10, decimal_places=2) # ราคาทั้งหมด
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2) # ยอดที่จ่ายออนไลน์ (มัดจำ)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    booking_ref = models.CharField(max_length=20, unique=True, null=True, blank=True) # เลขที่ใบจอง เช่น BK-20251214-XXXX
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    def __str__(self):
        return f"Booking {self.booking_ref} - {self.car.brand}"
    
    @property
    def remaining_balance(self):
        return self.total_price - self.deposit_amount


# ตาราง Promotion
class Promotion(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2) # เช่น 15.00 สำหรับ 15%
    start_date = models.DateField()
    end_date = models.DateField()
    code = models.CharField(max_length=20, unique=True, null=True, blank=True)
    usage_limit = models.IntegerField(default=100, verbose_name="จำกัดสิทธิ์") 
    used_count = models.IntegerField(default=0, verbose_name="ใช้ไปแล้ว")
    is_active = models.BooleanField(default=True, verbose_name="สถานะ")
    def __str__(self):
        return self.title



# ตาราง Payment (เชื่อมกับ Booking แบบ One-to-One)
class Payment(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'รอชำระเงิน'),
        ('WAITING_VERIFY', 'รอตรวจสอบสลิป'),
        ('COMPLETED', 'ชำระเงินสำเร็จ'),
        ('EXPIRED', 'หมดเวลา'),
        ('FAILED', 'ล้มเหลว'),
    )
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    payment_date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_ref = models.CharField(max_length=255, blank=True, null=True)
    slip_image = models.ImageField(upload_to='payment_slips/', blank=True, null=True)
    expire_at = models.DateTimeField(blank=True, null=True)

    def save(self, *args, **kwargs):
        # ตั้งเวลาหมดอายุ 15 นาที ถ้ายังไม่มี
        if not self.id and not self.expire_at:
            self.expire_at = timezone.now() + datetime.timedelta(minutes=15)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return timezone.now() > self.expire_at
    
    def __str__(self):
        return f'Payment for Booking #{self.booking.id}'

# ส่วนที่ 1: ผู้เช่า รีวิว รถ (และเจ้าของตอบกลับ)
class Review(models.Model):
    booking = models.OneToOneField('Booking', on_delete=models.CASCADE, related_name='review', null=True)
    car = models.ForeignKey(Car, related_name="reviews", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at'] # เรียงใหม่ไปเก่า

    def __str__(self):
        return f"Review for {self.car.brand} by {self.user.username}"

class ReviewReply(models.Model):
    review = models.ForeignKey(Review, related_name="replies", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Reply by {self.user.username}"
    
# 2.  RenterReview (สำหรับเจ้าของรีวิวลูกค้า)
class RenterReview(models.Model):
    booking = models.OneToOneField('Booking', on_delete=models.CASCADE, related_name='renter_review')
    renter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_reviews') # ผู้เช่า
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_reviews')   # เจ้าของรถ
    
    rating = models.IntegerField(default=5, validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
    def __str__(self):
        return f"Owner {self.owner.username} reviewed {self.renter.username}"
    
class RenterReply(models.Model):
    # ลูกค้ามาเขียนแก้ต่าง/ตอบกลับรีวิวข้างบน
    renter_review = models.ForeignKey(RenterReview, related_name="replies", on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE) # ผู้ตอบ (Renter)
    comment = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Renter Reply by {self.user.username}"
#ลูกค้าทั่วไป
class GuestCustomer(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    license_number = models.CharField(max_length=50)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    

# car_rental/models.py

class PlatformSetting(models.Model):
    # เราจะเก็บเป็นทศนิยม เช่น 0.15, 0.20, 0.30
    commission_rate = models.DecimalField(
        max_digits=4, 
        decimal_places=2, 
        default=0.15, 
        help_text="ใส่เป็นทศนิยม เช่น 0.15 คือ 15%, 0.30 คือ 30%"
    )
    
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"การตั้งค่าระบบ (ค่าคอม {self.commission_rate * 100}%)"

    def save(self, *args, **kwargs):
        # ป้องกันไม่ให้สร้างหลายอัน (Singleton Pattern แบบบ้านๆ)
        # ถ้ามีอยู่แล้ว ให้แก้ของเดิมแทนการสร้างใหม่
        if not self.pk and PlatformSetting.objects.exists():
            # ถ้าพยายาม create ใหม่ แต่มีของเก่าอยู่แล้ว ให้ไปแก้ตัวแรกสุดแทน
            self.pk = PlatformSetting.objects.first().pk
        super().save(*args, **kwargs)


# car_rental/models.py

class BookingInspection(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='inspections')
    image = models.ImageField(upload_to='inspection_photos/')
    description = models.CharField(max_length=200, blank=True, null=True, help_text="ระบุตำแหน่ง เช่น กันชนหน้าขวาบุบ")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Inspection for {self.booking.booking_ref}"
    

