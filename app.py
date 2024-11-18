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

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

app = Flask(__name__)

# ตั้งค่า LINE Messaging API
line_bot_api = LineBotApi('k8q+YGJzhKtfjyUpAEpsB25zEwLU7C3ILLZDBYzKMBHZwata/mFJAMXdr1j0EUh0NoTwdbVIDrUlaSVACZYesbSxGr+eeJ4POZWAA3ABY+jGxDy3G6bXtWeBATTRW4/kFVQfT9F5KUq74IACEG5k+gdB04t89/1O/w1cDnyilFU=')  # ใส่ Channel Access Token
handler = WebhookHandler('6a3e888914f7412382481ea1d6c324d5')  # ใส่ Channel Secret


@app.route('/test', methods=['GET'])
def test():
    return "Hello, World!"

@app.route('/callback', methods=['POST'])
def callback():
    # รับ Webhook Request จาก LINE
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    # ตอบกลับข้อความที่ได้รับ
    reply_message = "ได้รับข้อความแล้ว"
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=reply_message)
    )

if __name__ == "__main__":
    app.run(port=8000)
