# users/views.py

from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import UserRegisterForm, ProfileUpdateForm, UserUpdateForm  # เราจะต้องสร้างไฟล์ forms.py ด้วย
from django.contrib.auth.decorators import login_required
from car_rental.models import Profile


def become_owner(request):
    # นี่คือหน้าเปล่าๆ สำหรับให้ลิงก์ทำงานได้ก่อน
    return render(request, 'users/become_owner.html')

# ฟังก์ชันสมัครสมาชิกที่หายไป
def register(request):
    if request.method == 'POST':
        # **สำคัญ** ต้องรับ request.FILES ด้วย
        form = UserRegisterForm(request.POST, request.FILES)
        if form.is_valid():
            user = form.save() # บันทึก User ก่อน
            
            # สร้าง Profile และบันทึกรูปภาพ
            profile = Profile.objects.create(user=user) # สร้าง profile ที่ผูกกับ user
            if request.FILES.get('image'):
                profile.image = request.FILES['image']
                profile.save()

            username = form.cleaned_data.get('username')
            messages.success(request, f'สร้างบัญชีสำหรับ {username} สำเร็จแล้ว!')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'users/register.html', {'form': form})

# ฟังก์ชันแสดงโปรไฟล์
# users/views.py
# ... (import เหมือนเดิม)

@login_required
def profile(request):
    if request.method == 'POST':
        # นี่คือตอนที่ผู้ใช้กด "บันทึก"
        # (เราควรจะเช็ก request.POST.get('form_type')
        # แต่ตอนนี้เรารู้ว่ามีแค่ฟอร์มเดียว)

        u_form = UserUpdateForm(request.POST, instance=request.user)
        # เราต้องส่ง request.FILES ให้ ProfileForm เพื่อรับรูปภาพ
        p_form = ProfileUpdateForm(request.POST,
                                   request.FILES,
                                   instance=request.user.profile)

        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'อัปเดตโปรไฟล์ของคุณเรียบร้อยแล้ว!')
            return redirect('profile') # กลับมาหน้าโปรไฟล์ (ซึ่งจะกลับไปเป็นโหมดแสดงผล)
        else:
            # (ถ้าฟอร์มไม่ผ่าน, เราควรจะแสดง Error
            # แต่ตอนนี้เราจะแค่โหลดหน้าใหม่ก่อน)
            messages.error(request, 'เกิดข้อผิดพลาด! กรุณาลองอีกครั้ง')

    # นี่คือตอนที่ผู้ใช้เปิดหน้า (GET)
    # เราส่งฟอร์มเปล่าๆ ไปให้ (แม้ว่า HTML จะไม่ได้ใช้โดยตรง)
    u_form = UserUpdateForm(instance=request.user)
    p_form = ProfileUpdateForm(instance=request.user.profile)

    context = {
        'u_form': u_form,
        'p_form': p_form
        # เราไม่ต้องการ 'edit_mode' อีกต่อไป 
        # เพราะ JavaScript เป็นตัวจัดการ
    }
    return render(request, 'users/profile.html', context)

# (คุณต้องสร้าง View นี้เพิ่ม สำหรับ Modal เปลี่ยนรหัสผ่าน)
# @login_required
# def change_password(request):
#    ... (Logic การเปลี่ยนรหัสผ่าน) ...