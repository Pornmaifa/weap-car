from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import UserRegisterForm, ProfileUpdateForm, UserUpdateForm  # เราจะต้องสร้างไฟล์ forms.py ด้วย
from django.contrib.auth.decorators import login_required
from car_rental.models import Profile
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.models import User
from car_rental.models import RenterReview 
from django.db.models import Avg
from django.shortcuts import redirect
from django.contrib.auth import update_session_auth_hash

def custom_login_redirect(request):
    # เช็คบัตร: ถ้าเป็น Staff หรือ Superuser
    if request.user.is_staff or request.user.is_superuser:
        # เชิญไปห้อง Admin Car
        return redirect('admincar_dashboard')
    else:
        # ถ้าเป็นลูกค้าทั่วไป เชิญไปหน้าแรก
        return redirect('car_list')
    
def become_owner(request):
    return render(request, 'users/become_owner.html')

# ฟังก์ชันสมัครสมาชิกที่หายไป
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save()

            phone = request.POST.get('phone')
            license_no = request.POST.get('license_no')
            image = form.cleaned_data.get('image')
            # สร้าง Profile และบันทึกรูปภาพ
            profile, created = Profile.objects.get_or_create(user=user)
            profile.phone = phone
            profile.license_no = license_no
            if image:
                profile.image = image
            profile.save()

            username = form.cleaned_data.get('username')
            messages.success(request, f'สร้างบัญชีสำหรับ {username} สำเร็จแล้ว!')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})

@login_required
def profile(request):
    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'อัปเดตข้อมูลสำเร็จ!')
            return redirect('profile')

    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form
    }
    return render(request, 'users/profile.html', context)

# --- ฟังก์ชันเปลี่ยนรหัสผ่าน  ---
@login_required
def change_password(request):
    if request.method == 'POST':
        old_pass = request.POST.get('old_password')
        new_pass1 = request.POST.get('new_password1')
        new_pass2 = request.POST.get('new_password2')
        
        user = request.user
        
        # 1. เช็ครหัสเดิม
        if not user.check_password(old_pass):
            messages.error(request, "รหัสผ่านเดิมไม่ถูกต้อง")
            return redirect('profile')
            
        # 2. เช็ครหัสใหม่ตรงกัน
        if new_pass1 != new_pass2:
            messages.error(request, "รหัสผ่านใหม่ไม่ตรงกัน")
            return redirect('profile')
            
        # 3. เปลี่ยนรหัสและบันทึก
        user.set_password(new_pass1)
        user.save()
        
        # 4. Login ให้อัตโนมัติ (ไม่ให้เด้งหลุด)
        update_session_auth_hash(request, user)
        
        messages.success(request, "เปลี่ยนรหัสผ่านเรียบร้อยแล้ว")
        return redirect('profile')
        
    return redirect('profile') # ถ้าไม่ใช่ POST ให้กลับไปหน้า Profile

def public_profile(request, user_id):
    # ดึงข้อมูลผู้ใช้คนนั้น
    profile_user = get_object_or_404(User, id=user_id)
    
    # ดึงรีวิวที่คนนี้ "ถูกกระทำ" (received_reviews)
    reviews = RenterReview.objects.filter(renter=profile_user).order_by('-created_at')
    
    # หาคะแนนเฉลี่ย
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0
    
    context = {
        'profile_user': profile_user,
        'reviews': reviews,
        'avg_rating': round(avg_rating, 1),
        'review_count': reviews.count()
    }
    return render(request, 'users/public_profile.html', context)