# car_rental/models.py

from django.db import models
from django.contrib.auth.models import User # ดึงโมเดล User ของ Django มาใช้

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
    image = models.ImageField(default='default.png', upload_to='profile_pics')
    
    def __str__(self):
        return f'{self.user.username} Profile'

# ตาราง Car
from django.db import models
from django.contrib.auth.models import User

class Car(models.Model):
    CAR_TYPE_CHOICES = [
        ('SEDAN', 'รถเก๋งขนาดเล็ก'),
        ('TRUCK', 'รถกระบะ'),
        ('VAN', 'รถตู้'),
        ('EV', 'รถไฟฟ้า'),
    ]

    STATUS_CHOICES = [
        ('AVAILABLE', 'พร้อมใช้งาน'),
        ('BOOKED', 'ถูกจองแล้ว'),
        ('MAINTENANCE', 'ซ่อมบำรุง'),
    ]

    SERVICE_TYPE_CHOICES = [
        ('SELF_DRIVE', 'ขับเอง'),
        ('WITH_DRIVER', 'พร้อมคนขับ'),
    ]

    DISCOUNT_CHOICES = [
        ('NONE', 'ไม่มีส่วนลด'),
        ('FIRST_TIMER_20', 'ส่วนลด 20% สำหรับผู้เช่าครั้งแรก'),
    ]

    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    brand = models.CharField(max_length=50)
    model = models.CharField(max_length=50)
    year = models.IntegerField(null=True, blank=True)
    description = models.TextField(max_length=200, null=True, blank=True)

    price_per_day = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    car_type = models.CharField(max_length=10, choices=CAR_TYPE_CHOICES, default='SEDAN')
    license_plate = models.CharField(max_length=100, default='')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='AVAILABLE')
    service_type = models.CharField(max_length=20, choices=SERVICE_TYPE_CHOICES, default='SELF_DRIVE')

    # --- Step 3: Address ---
    country = models.CharField(max_length=100, default='ประเทศไทย')  # ✅ กำหนด default ป้องกัน null error
    street_address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, default="Bangkok")
    state = models.CharField(max_length=100, default="Unknown")  # จังหวัด
    zip_code = models.CharField(max_length=10, null=True, blank=True)

    # --- Step 7: Additional Info ---
    num_doors = models.PositiveIntegerField(default=4)
    num_luggage = models.PositiveIntegerField(default=2)
    fuel_system = models.CharField(max_length=20, default='GASOLINE')
    has_child_seat = models.BooleanField(default=False)
    accessory_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    min_rental_days = models.PositiveIntegerField(default=1)
    max_rental_days = models.PositiveIntegerField(default=30)
    discount_option = models.CharField(max_length=50, choices=DISCOUNT_CHOICES, default='NONE')

    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f'{self.brand} {self.model} ({self.year})'


class CarImage(models.Model):
    car = models.ForeignKey(Car, on_delete=models.CASCADE, related_name='images')
    image = models.ImageField(upload_to='car_images/')

    def __str__(self):
        return f"Image for {self.car.brand} {self.car.model}"

# ตาราง Promotion
class Promotion(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2) # เช่น 15.00 สำหรับ 15%
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return self.title

# ตาราง Booking
class Booking(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('CANCELLED', 'Cancelled'),
        ('COMPLETED', 'Completed'),
    )
    member = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    car = models.ForeignKey(Car, on_delete=models.CASCADE)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    booking_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_bookings')

    def __str__(self):
        return f'Booking #{self.id} for {self.car.license_plate}'

# ตาราง Payment (เชื่อมกับ Booking แบบ One-to-One)
class Payment(models.Model):
    STATUS_CHOICES = (
        ('PENDING', 'Pending'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
    )
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    payment_date = models.DateTimeField(auto_now_add=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50)
    payment_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    transaction_ref = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f'Payment for Booking #{self.booking.id}'

# ตาราง Review
class Review(models.Model):
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE)
    member = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField() # เช่น 1-5
    comment = models.TextField(blank=True, null=True)
    review_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'Review by {self.member.username} for Booking #{self.booking.id}'