from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt

# Import Models ของคุณ
from car_rental.models import Booking, Profile

# 👇 จุดสำคัญ! ต้อง import จาก 'linebot' (Library) เท่านั้น ห้ามใช้ line_app
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

line_bot_api = LineBotApi(settings.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(settings.LINE_CHANNEL_SECRET)

@csrf_exempt
def callback(request):
    """ ฟังก์ชันรับข้อมูลจาก LINE (Webhook) """
    signature = request.headers.get('X-Line-Signature', '')
    body = request.body.decode('utf-8')

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        return HttpResponseForbidden()
    except LineBotApiError:
        return HttpResponseBadRequest()

    return HttpResponse('OK')

# --- Logic ตอบกลับข้อความ ---
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    msg_text = event.message.text.strip() # ข้อความที่ลูกค้าพิมพ์ (Booking Ref)
    user_line_id = event.source.user_id   # LINE ID ของลูกค้า
    
    reply_msg = ""
    
    # พิมพ์ TEST เพื่อเช็คสถานะ
    if msg_text.upper() == 'TEST':
        reply_msg = f"บอท car_rental ทำงานปกติครับ!\nLINE ID: {user_line_id}"
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_msg))
        return

    # Logic เชื่อมต่อบัญชี
    try:
        # ค้นหาด้วย 'booking_ref'
        booking = Booking.objects.get(booking_ref=msg_text) 
        
        # เช็คว่าเป็นสมาชิกที่มี Profile หรือไม่
        if booking.user:
            profile = booking.user.profile 

            # เช็คและบันทึก
            if profile.line_id:
                if profile.line_id == user_line_id:
                    reply_msg = "บัญชีนี้เชื่อมต่อเรียบร้อยแล้วครับ ✅"
                else:
                    reply_msg = "เลขจองนี้ถูกเชื่อมต่อกับ LINE อื่นไปแล้วครับ ❌"
            else:
                profile.line_id = user_line_id
                profile.save()
                
                name_show = profile.user.first_name if profile.user.first_name else profile.user.username
                reply_msg = f"ยินดีด้วยครับ คุณ{name_show}! 🎉\nเชื่อมต่อสำเร็จ! ระบบจะแจ้งเตือนเมื่อรถอนุมัติครับ"
        
        elif booking.guest:
            reply_msg = "ขออภัยครับ ระบบแจ้งเตือนรองรับเฉพาะสมาชิกที่ลงทะเบียนเท่านั้นครับ 🙏"
        else:
            reply_msg = "ไม่พบข้อมูลผู้จองในรายการนี้ครับ"

    except Booking.DoesNotExist:
        reply_msg = f"ไม่พบรหัสการจอง '{msg_text}' ในระบบครับ 😅\nกรุณาตรวจสอบความถูกต้อง (เช่น BK-xxxx)"
    except AttributeError:
        reply_msg = "Error: ไม่พบข้อมูล Profile ของผู้ใช้นี้"
    except Exception as e:
        print(f"Error: {e}")
        reply_msg = "เกิดข้อผิดพลาดทางเทคนิค กรุณาลองใหม่"

    # ส่งข้อความกลับ
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_msg)
    )