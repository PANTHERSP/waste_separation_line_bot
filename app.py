import os
import cv2
import base64
import numpy as np
from io import BytesIO
from PIL import Image
from flask import Flask, request, abort, send_from_directory
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, ImageMessage, TextSendMessage, ImageSendMessage
from ultralytics import YOLO
import torch

app = Flask(__name__)

# LINE Messaging API credentials
line_bot_api = LineBotApi('k8q+YGJzhKtfjyUpAEpsB25zEwLU7C3ILLZDBYzKMBHZwata/mFJAMXdr1j0EUh0NoTwdbVIDrUlaSVACZYesbSxGr+eeJ4POZWAA3ABY+jGxDy3G6bXtWeBATTRW4/kFVQfT9F5KUq74IACEG5k+gdB04t89/1O/w1cDnyilFU=')  # ใส่ Channel Access Token
handler = WebhookHandler('6a3e888914f7412382481ea1d6c324d5')

print("Loading YOLO model...")
model = YOLO('best.pt')

device = 'cuda:0' if torch.cuda.is_available() else 'cpu'
model.to(device)

redBin = ['battery', 'mobile-phone', 'mouse', 'light-bulb', 'fluorescent-lamp', 'earphone', 'cable', 'spray']
yellowBin = ['PET-plastic-bottle', 'PE-plastic-bag', 'broken-glass', 'metal-can', 'paper', 'taobin', 'transparent-plastic-bottle']
greenBin = ['animal-waste', 'banana-peel', 'orange-peel']
blueBin = ['snack-package', 'tissue-paper', 'foam']

# กำหนดโฟลเดอร์สำหรับเก็บภาพ
UPLOAD_FOLDER = 'static/images/'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

@app.route('/test', methods=['GET'])
def test():
    return "Hello, think-keng!"

@app.route('/callback', methods=['POST'])
def callback():
    # Get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        # Handle the webhook body and signature
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    # Handle text message
    reply_message = "ควย"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_message)
    )

@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    # Get the image content from LINE
    message_content = line_bot_api.get_message_content(event.message.id)
    
    # Convert the image content into Base64 (as done previously)
    image_data = BytesIO()
    for chunk in message_content.iter_content():
        image_data.write(chunk)
    
    # Move the pointer to the beginning of the image_data buffer
    image_data.seek(0)
    
    # Decode the image_data as Base64
    base64_image = base64.b64encode(image_data.read()).decode('utf-8')

    frame = np.frombuffer(base64.b64decode(base64_image), np.uint8)
    frame = cv2.imdecode(frame, cv2.IMREAD_COLOR) 
    original_image_width, original_image_height, _ = frame.shape 
    frame = cv2.resize(frame, (640, 480))    

    try:
        height, width, channels = frame.shape
        print(f"before => width: {width}, height: {height}, channels: {channels}")
        # รัน YOLO inference
        results = model(frame, batch=1)
        if results is None or not results:
            print("ไม่มีผลลัพธ์จาก YOLO.")
            return
    except Exception as e:
        print(f"เกิดข้อผิดพลาดระหว่างการประมวลผล YOLO: {e}")
        return

    annotated_frame = frame.copy()
    all_labels = []

    if results[0].masks is not None:
        for i, mask in enumerate(results[0].masks.data):
            binary_mask = mask.cpu().numpy().astype('uint8') * 255
            contours, _ = cv2.findContours(binary_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            if not contours:
                continue

            label = results[0].names[results[0].boxes.cls[i].item()]
            if label in redBin:
                label_color = (0, 0, 255)
            elif label in greenBin:
                label_color = (0, 255, 0)
            elif label in blueBin:
                label_color = (255, 0, 0)
            elif label in yellowBin:
                label_color = (0, 255, 255)
            else:
                label_color = (255, 255, 255)

            if label in yellowBin:
                label_text_color = (0, 0, 0)
            else:
                label_text_color = (255, 255, 255)

            print('label: ', label)
            all_labels.append(label)

            cv2.drawContours(annotated_frame, contours, -1, label_color, 4)

            score = results[0].boxes.conf[i].item() * 100
            label_text = f'{label} {score:.2f}%'
            (text_width, text_height), baseline = cv2.getTextSize(label_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)
            x, y = int(results[0].boxes.xyxy[i][0]), int(results[0].boxes.xyxy[i][1])

            cv2.rectangle(annotated_frame, (x, y - text_height - baseline), (x + text_width, y), label_color, -1)
            cv2.putText(annotated_frame, label_text, (x, y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, label_text_color, 2)
    
    
    annotated_frame = cv2.resize(annotated_frame, (original_image_height, original_image_width))
    height, width, channels = annotated_frame.shape
    print(f"after => width: {width}, height: {height}, channels: {channels}")

    # Encode the annotated image as JPEG
    _, encoded_image = cv2.imencode('.jpg', annotated_frame)
    image_bytes = encoded_image.tobytes()

    # Send the annotated image back to the user
    try:
        # Use the message ID as the filename
        image_url = upload_image(image_bytes, event.message.id)  # Upload the image to the server
        image_message = ImageSendMessage(
            original_content_url=image_url,
            preview_image_url=image_url
        )
        line_bot_api.reply_message(event.reply_token, image_message)
        # หลังจากส่งข้อความเสร็จ ลบไฟล์ที่อัปโหลด
        image_path = os.path.join(UPLOAD_FOLDER, f"{event.message.id}.jpg")
        if os.path.exists(image_path):
            os.remove(image_path)  # ลบไฟล์
            print(f"ลบไฟล์สำเร็จ: {image_path}")
        else:
            print(f"ไม่พบไฟล์: {image_path}")
            
    except Exception as e:
        print(f"Failed to send image: {e}")


def upload_image(image_bytes, message_id):
    # ใช้ message id เป็นชื่อไฟล์
    image_filename = f"{message_id}.jpg"
    image_path = os.path.join(UPLOAD_FOLDER, image_filename)

    # Save the image to the server
    with open(image_path, 'wb') as f:
        f.write(image_bytes)

    # Return the URL for accessing the image
    return f"https://waste-separation-line-bot.onrender.com/static/images/{image_filename}"
    

@app.route('/static/<path:filename>')
def serve_static_file(filename):
    return send_from_directory(UPLOAD_FOLDER, filename)

if __name__ == "__main__":
    app.run(port=8000)


# from pymongo.mongo_client import MongoClient
# from pymongo.server_api import ServerApi

# uri = "mongodb+srv://Panther:Pansterz231564@dev-cluster.tttw3.mongodb.net/?retryWrites=true&w=majority&appName=dev-cluster"

# # Create a new client and connect to the server
# client = MongoClient(uri, server_api=ServerApi('1'))

# # # Send a ping to confirm a successful connection
# # try:
# #     client.admin.command('ping')
# #     print("Pinged your deployment. You successfully connected to MongoDB!")
# # except Exception as e:
# #     print(e)

# # เลือกหรือสร้างฐานข้อมูล (หากยังไม่มี)
# db = client['line_bot_waste_separation']  # ชื่อฐานข้อมูล

# # เลือกหรือสร้าง collection (หากยังไม่มี)
# collection = db['users']  # ชื่อ collection

# # ข้อมูลที่จะเพิ่ม
# user_data = {
#     'name': 'John Doe',
#     'age': 30,
#     'email': 'john.doe@example.com'
# }

# # อัปเดตหรือเพิ่มข้อมูลใหม่ด้วย upsert
# collection.update_one(
#     {'key': 'test'},  # เงื่อนไขค้นหา
#     {'$set': {'image_id': '54321', 'user_id': '12345', 'username': 'johndoe'}},  # ข้อมูลที่จะอัปเดต
#     upsert=True  # ถ้าไม่มีเอกสารตรงเงื่อนไข จะเพิ่มใหม่
# )

# # เพิ่มข้อมูลใน collection
# # collection.insert_one(user_data)
# print("User added successfully!")





# from flask import Flask, request, abort
# from linebot import LineBotApi, WebhookHandler
# from linebot.exceptions import InvalidSignatureError
# from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage

# app = Flask(__name__)

# # ตั้งค่า LINE Messaging API
# line_bot_api = LineBotApi('k8q+YGJzhKtfjyUpAEpsB25zEwLU7C3ILLZDBYzKMBHZwata/mFJAMXdr1j0EUh0NoTwdbVIDrUlaSVACZYesbSxGr+eeJ4POZWAA3ABY+jGxDy3G6bXtWeBATTRW4/kFVQfT9F5KUq74IACEG5k+gdB04t89/1O/w1cDnyilFU=')  # ใส่ Channel Access Token
# handler = WebhookHandler('6a3e888914f7412382481ea1d6c324d5')  # ใส่ Channel Secret


# @app.route('/test', methods=['GET'])
# def test():
#     return "Hello, World!"

# @app.route('/callback', methods=['POST'])
# def callback():
#     # รับ Webhook Request จาก LINE
#     signature = request.headers['X-Line-Signature']
#     body = request.get_data(as_text=True)

#     try:
#         handler.handle(body, signature)
#     except InvalidSignatureError:
#         abort(400)

#     return 'OK'

# @handler.add(MessageEvent, message=TextMessage)
# def handle_text_message(event):
#     # ตอบกลับข้อความที่ได้รับ
#     reply_message = "ได้รับข้อความแล้ว"
#     line_bot_api.reply_message(
#         event.reply_token,
#         TextSendMessage(text=reply_message)
#     )

# if __name__ == "__main__":
#     app.run(port=8000)









# from flask import Flask, request, abort, send_file
# from linebot import LineBotApi, WebhookHandler
# from linebot.exceptions import InvalidSignatureError
# from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage
# from io import BytesIO  # BytesIO สำหรับจัดการไฟล์ใน memory
# import threading  # สำหรับตั้งเวลาลบภาพ
# from PIL import Image  # ใช้สำหรับประมวลผลภาพ (Pillow library)
# import time  # สำหรับการจัดการเวลาถ้าต้องการ

# app = Flask(__name__)

# # Temporary storage for images
# image_storage = {}

# # ตั้งค่า LINE Messaging API
# line_bot_api = LineBotApi('k8q+YGJzhKtfjyUpAEpsB25zEwLU7C3ILLZDBYzKMBHZwata/mFJAMXdr1j0EUh0NoTwdbVIDrUlaSVACZYesbSxGr+eeJ4POZWAA3ABY+jGxDy3G6bXtWeBATTRW4/kFVQfT9F5KUq74IACEG5k+gdB04t89/1O/w1cDnyilFU=')  # ใส่ Channel Access Token
# handler = WebhookHandler('6a3e888914f7412382481ea1d6c324d5')  # ใส่ Channel Secret


# @app.route('/test', methods=['GET'])
# def test():
#     return "Hello, World!"

# @app.route('/callback', methods=['POST'])
# def callback():
#     # รับ Webhook Request จาก LINE
#     signature = request.headers['X-Line-Signature']
#     body = request.get_data(as_text=True)

#     try:
#         handler.handle(body, signature)
#     except InvalidSignatureError:
#         abort(400)

#     return 'OK'


# @app.route('/images/<image_id>', methods=['GET'])
# def serve_temp_image(image_id):
#     image_stream = image_storage.get(image_id)
#     if image_stream is None:
#         abort(404)

#     # ตั้งเวลาลบภาพอัตโนมัติหลังจากส่งกลับ
#     threading.Timer(10, lambda: image_storage.pop(image_id, None)).start()
#     return send_file(image_stream, mimetype='image/jpeg')


# @handler.add(MessageEvent, message=ImageMessage)
# def handle_image_message(event):
#     # ดาวน์โหลดภาพจาก LINE Messaging API
#     message_content = line_bot_api.get_message_content(event.message.id)
#     input_stream = BytesIO(message_content.content)

#     # อ่านภาพและประมวลผล
#     image = Image.open(input_stream)
#     processed_image = image.convert("L")  # ตัวอย่าง: แปลงภาพเป็น grayscale

#     # เก็บผลลัพธ์ใน memory
#     output_stream = BytesIO()
#     processed_image.save(output_stream, format="JPEG")
#     output_stream.seek(0)

#     # เก็บภาพใน memory ชั่วคราว
#     image_id = event.message.id
#     image_storage[image_id] = output_stream

#     # ส่ง URL กลับ LINE
#     reply_url = f"https://waste-separation-line-bot.onrender.com/images/{image_id}"  # URL เซิร์ฟเวอร์ของคุณ
#     line_bot_api.reply_message(
#         event.reply_token,
#         {
#             "type": "image",
#             "originalContentUrl": reply_url,
#             "previewImageUrl": reply_url,
#         }
#     )

# if __name__ == "__main__":
#     app.run(port=8000)
