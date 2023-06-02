# python3 barcode_scanner_video.py

# import the necessary packages
from imutils.video import VideoStream
from pyzbar import pyzbar
import argparse
import datetime
import imutils
import time
import cv2
from firebase import firebase
from datetime import datetime
import base64
import sys
from Crypto.Cipher import AES
import re

# 1. qr에서 데이터를 읽어온 후 복호화한다
# 2. 복호화한 데이터에서 유저 아이디만 가져온다
# 3. 유저 아이디 - qr_code - lock_user가 본 파일에 저장된 door_user와 일치하는지 판별
# 4. 일치하면 도어록 문 열라고 db에 값 전송

the_key = "1234567890123456"
the_iv = "1234567890123456"

b_size = AES.block_size
pad = lambda s: s + (b_size - len(s.encode()) % b_size) * chr(b_size - len(s.encode()) % b_size)
unpad = lambda s: s[:-ord(s[len(s)-1:])]


# QR 코드 데이터 복호화 함수
def decrypt(content):
    cipher = AES.new(the_key.encode("utf-8"), AES.MODE_CBC, the_iv.encode("utf-8"))
    dec_data = base64.b64decode(content) 
    return unpad(cipher.decrypt(dec_data))

count = 2 # 출입 로그 카운트
door_user = "bae0000" # 현재 도어록 소유자 아이디 (카메라 주인)

# 데이터베이스 연동
firebase = firebase.FirebaseApplication("https://wintercapstonedesign-default-rtdb.firebaseio.com/", None)
firebase_address = "https://wintercapstonedesign-default-rtdb.firebaseio.com/"

ap = argparse.ArgumentParser()
ap.add_argument("-o", "--output", type=str, default="barcodes.csv",
	help="path to output CSV file containing barcodes")
args = vars(ap.parse_args())

print("[INFO] starting video stream...")
vs = VideoStream(src=cv2.CAP_V4L).start()   
time.sleep(2.0)

csv = open(args["output"], "w")
found = []

while True:
	frame = vs.read()
	frame = imutils.resize(frame, width=400)
	barcodes = pyzbar.decode(frame)

	for barcode in barcodes:
		(x, y, w, h) = barcode.rect
		cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 0, 255), 2)

		barcodeData = barcode.data.decode("utf-8")
		barcodeType = barcode.type

		text = "{} ({})".format(barcodeData, barcodeType)
		cv2.putText(frame, text, (x, y - 10),
			cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2) # text == qr에서 읽어온 데이터

		# 데이터 복호화해서 qr_data 변수에 저장
		result = decrypt(text[:-9])
		qr_data = result.decode("utf-8")

		# string으로 읽어온 qr에 저장된 데이터를 key-value 형태로 변형
		qr_data = qr_data[17:]
		qr_data = qr_data[:-1]
		
		keys = []
		values = []
		data_list = qr_data.split(", ")
		
		for data in data_list:
			pair = data.split("=")
			keys.append(pair[0])
			values.append(pair[1])
			
		qr_dict = dict(zip(keys,values))
		qr_camera_user = qr_dict["id"]
		
		# qr 생성자 가져오기 == 현재 인식하고 있는 카메라(도어록)의 사용자인가(집주인)
		create_qr = firebase.get("user/" + qr_camera_user + "/qr_code/lock_user", None) 
		route = "door_open/" + door_user + "/qr_lock/" + str(count) # 로그 저장 위치 (공통)
		
		if(create_qr == door_user) :
			firebase.put(firebase_address,route + "/date",datetime.now())
			firebase.put(firebase_address,route + "/success","true")
			firebase.put(firebase_address,route + "/user_id",qr_camera_user)
			firebase.put(firebase_address,"/check_qr","true")
			count = count + 1
			print("open door!")
		else :
			firebase.put(firebase_address,route + "/date",datetime.now())
			firebase.put(firebase_address,route + "/success","false")
			firebase.put(firebase_address,route + "/user_id",qr_camera_user)
			count = count + 1
			print("The QR code is not valid.")


	cv2.imshow("Barcode Scanner", frame)
	key = cv2.waitKey(1) & 0xFF
 
	# if the `q` key was pressed, break from the loop
	if key == ord("q"):
		break

# close the output CSV file do a bit of cleanup
print("[INFO] cleaning up...")
csv.close()
cv2.destroyAllWindows()
vs.stop()
