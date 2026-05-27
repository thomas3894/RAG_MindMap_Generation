import os
import tempfile
import traceback
from datetime import datetime
import pytz
from flask import Flask, request, jsonify
from werkzeug.utils import secure_filename
import firebase_admin
from firebase_admin import credentials, firestore, storage
import json
import requests
from flask_cors import CORS
from oncClickV9 import generate
from googleapiclient.discovery import build
import re

app = Flask(__name__)
CORS(app)

# 初始化 Firebase Admin SDK
cred = credentials.Certificate(r'...')
firebase_admin.initialize_app(cred, {
    'storageBucket': '...'
})

bucket = storage.bucket()
db = firestore.client()

# 本地文件上傳設置
ALLOWED_EXTENSIONS = {'pdf', 'md', 'mp3', 'json', 'jpg', 'png'}

yt_Url = None
# 全域拿yt的連結
def getYtUrl(yt_url):
    global yt_Url 
    yt_Url = yt_url


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/verify-token', methods=['POST'])
def google_verify_token():
    token = request.json.get('token')
    try:
        response = requests.get(
            '...',
            headers={'Authorization': f'Bearer {token}'}
        )
        user_info = response.json()
        
        users_ref = db.collection('users')
        query = users_ref.where('sub', '==', user_info['sub']).stream()
        user = next(query, None)

        if not user:
            new_user = {
                'sub': user_info['sub'],
                'email': user_info['email'],
                'username': user_info['name'],
            }
            custom_user_id = f"{user_info['sub']}"  # 使用 sub 作為自定義 ID 
            user_ref = users_ref.document(custom_user_id)
            user_ref.set(new_user)
            user_id = custom_user_id
        else:
            user_id = user.id

        return jsonify({"message": "Google sign-in success", "user": {"id": user_id, "email": user_info['email'], "username": user_info['name']}}), 200

    except Exception as e:
        return jsonify({"message": "Token verification failed", "error": str(e)}), 401

# 做 mp3 音檔解析
@app.route('/uploadMp3', methods=['POST'])
def uploadMp3():
    try:
        file = request.files['file']
        user_id = request.form['user_id']
        
        if file and allowed_file(file.filename):
            # filename = secure_filename(file.filename)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
                temp_file.write(file.read())
                temp_file_path = temp_file.name
                
            markdown_content = generate(temp_file_path, file.filename)
            
            os.remove(temp_file_path)

            if markdown_content is None:
                return jsonify(success=False, message='Failed to generate markdown content'), 500

            blob = bucket.blob(file.filename)
            file.seek(0)
            blob.upload_from_file(file)
            file_url = blob.public_url
            file.filename = sanitize_filename(file.filename)
            
            user_ref = db.collection('users').document(user_id)
            files_ref = user_ref.collection('files').document(file.filename)
            files_ref.set({
                'file_name': file.filename,
                'file_url': file_url,
                'content': markdown_content,
                'timestamp': datetime.now(pytz.UTC)
            })

            return jsonify(success=True, file_url=file_url, markdown_content=markdown_content)
        else:
            return jsonify(success=False, message='不允許的文件類型')
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})
    
# 做 ocr 圖片解析
@app.route('/uploadImg', methods=['POST'])
def uploadImg():
    try:
        file = request.files['file']
        user_id = request.form['user_id']
        
        if file and allowed_file(file.filename):
            # filename = secure_filename(file.filename)
            
            if file.filename.split('.')[1] == "jpg":
                with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                    temp_file.write(file.read())
                    temp_file_path = temp_file.name
            elif file.filename.split('.')[1] == "png":
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
                    temp_file.write(file.read())
                    temp_file_path = temp_file.name
            elif file.filename.split('.')[1] == "pdf":
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                    temp_file.write(file.read())
                    temp_file_path = temp_file.name
            if file.filename.split('.')[1] == "pdf":
                print(temp_file_path)
                markdown_content = generate('OCR.' +temp_file_path, file.filename)
            else:
                markdown_content = generate(temp_file_path, file.filename)
            
            os.remove(temp_file_path)

            if markdown_content is None:
                return jsonify(success=False, message='Failed to generate markdown content'), 500

            blob = bucket.blob(file.filename)
            file.seek(0)
            blob.upload_from_file(file)
            file_url = blob.public_url
            file.filename = sanitize_filename(file.filename)
            
            user_ref = db.collection('users').document(user_id)
            files_ref = user_ref.collection('files').document(file.filename)
            files_ref.set({
                'file_name': file.filename,
                'file_url': file_url,
                'content': markdown_content,
                'timestamp': datetime.now(pytz.UTC)
            })

            return jsonify(success=True, file_url=file_url, markdown_content=markdown_content)
        else:
            return jsonify(success=False, message='不允許的文件類型')
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})

def get_youtube_title(api_key, url):
    match = re.search(r'v=([^&]+)', url)
    if not match:
        raise ValueError("Invalid YouTube URL")
    video_id = match.group(1)

    youtube = build('youtube', 'v3', developerKey=api_key)

    request = youtube.videos().list(part='snippet', id=video_id)
    response = request.execute()

    if 'items' in response and len(response['items']) > 0:
        title = response['items'][0]['snippet']['title']
        return title
    else:
        raise ValueError("Video not found") 

# 上傳 YouTube 影片連結
@app.route('/uploadLink', methods=['POST'])
def uploadLink():
    try:
        yt_url = request.form['file']
        getYtUrl(yt_url)
        user_id = request.form['user_id']
        # f"在uploadLink時的youtube連結 {yt_url}"
        if yt_url and yt_url.startswith("https://www.youtube.com/watch?v="):
            video_title = get_youtube_title(api_key, yt_url)
            video_title = sanitize_filename(video_title)
            markdown_content = generate(yt_url, video_title)
            if markdown_content is None:
                return jsonify(success=False, message='Failed to generate markdown content'), 500

            blob = bucket.blob(video_title)
            blob.upload_from_string(yt_url)
            file_url = blob.public_url

            user_ref = db.collection('users').document(user_id)
            files_ref = user_ref.collection('files').document(video_title)
            files_ref.set({
                'file_name': video_title,
                'youtube_url' : yt_Url,
                'file_url': file_url,
                'content': markdown_content,
                'timestamp': datetime.now(pytz.UTC)
            })
            # print(f"在uploadLink時成功上傳到資料庫")
            return jsonify(success=True, file_url=file_url, markdown_content=markdown_content, video_title=video_title, yt_Url = yt_Url)
        else:
            return jsonify(success=False, message='不允許的影片連結')
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})

# 做 PDF 文件解析
@app.route('/uploadPdf', methods=['POST'])
def uploadPdf():
    try:
        file = request.files['file']
        user_id = request.form['user_id']

        if file and allowed_file(file.filename):
            # filename = secure_filename(file.filename)
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
                temp_file.write(file.read())
                temp_file_path = temp_file.name
 
            markdown_content = generate(temp_file_path, file.filename)
            os.remove(temp_file_path)

            if markdown_content is None:
                return jsonify(success=False, message='Failed to generate markdown content'), 500

            blob = bucket.blob(file.filename)
            file.seek(0)
            blob.upload_from_file(file)
            file_url = blob.public_url
            file.filename = sanitize_filename(file.filename)
            
            user_ref = db.collection('users').document(user_id)
            files_ref = user_ref.collection('files').document(file.filename)
            files_ref.set({
                'file_name': file.filename,
                'file_url': file_url,
                'content': markdown_content,
                'timestamp': datetime.now(pytz.UTC)
            })

            return jsonify(success=True, file_url=file_url, markdown_content=markdown_content)
        else:
            return jsonify(success=False, message='不允許的文件類型')
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})

@app.route('/upload/mindmap', methods=['POST'])
def upload_md():
    try:
        file = request.files['file']
        user_id = request.form['user_id']

        if file and allowed_file(file.filename):
            file_content = file.read().decode('utf-8')
            
            # filename = secure_filename(file.filename)
            blob = bucket.blob(file.filename)
            blob.upload_from_string(file_content)
            file_url = blob.public_url
            file.filename = sanitize_filename(file.filename)

            user_ref = db.collection('users').document(user_id)
            files_ref = user_ref.collection('files').document(file.filename)
            files_ref.set({
                'file_name': file.filename,
                'file_url': file_url,
                'content': file_content,
                'timestamp': datetime.now(pytz.UTC)
            })
            # print(f"現在的檔案名稱: {file.filename}, 現在的內容: {file_content}, 現在的檔案連結: {file_url}")
            return jsonify(success=True, file_url=file_url, markdown_content=file_content)
        else:
            return jsonify(success=False, message='不允許的文件類型')
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)})

def convert_file_to_utf8(file_content):
    encodings = ['cp950', 'big5', 'gbk', 'utf-8']
    for encoding in encodings:
        try:
            return file_content.decode(encoding).encode('utf-8').decode('utf-8')
        except UnicodeDecodeError as e:
            print(f"Error decoding file with encoding {encoding}: {e}")
    raise UnicodeDecodeError("Failed to decode file with available encodings")

def is_youtube_url(url):
    if not url:
        return False
    youtube_regex = re.compile(
        r'^(https?://)?(www\.)?(youtube\.com|youtu\.?be)/.+$',
        re.IGNORECASE
    )
    return re.match(youtube_regex, url) is not None

def sanitize_filename(filename):
    filename = re.sub(r'[\\/:"*?<>|]+', ' ', filename)
    return filename

@app.route('/uploadJson', methods=['POST'])
def upload_json():
    file = request.files.get('file')
    user_id = request.form.get('user_id')

    file_content = file.read().decode('utf-8')
    data = json.loads(file_content)
    # f"現在的youtube連結 : {yt_Url}"
    if is_youtube_url(yt_Url):
        api_key = '...'
        video_title = get_youtube_title(api_key, yt_Url)
        video_title = sanitize_filename(video_title)
        # f"在uploadJson中的video title內容為: {video_title}"
        blob = bucket.blob(video_title)
        blob.upload_from_string(json.dumps(data), content_type='application/json')
        file_url = blob.public_url

        user_ref = db.collection('users').document(user_id)
        files_ref = user_ref.collection('files').document(video_title)
        files_ref.set({
            'file_name': video_title,
            'youtube_url' : yt_Url,
            'file_url': file_url,
            'content': data,
            'timestamp': datetime.now(pytz.UTC)
        })
        getYtUrl(None)
        return jsonify({'success': True, 'file_url': file_url, 'data': data})
    
    else:
        blob = bucket.blob(file.filename)
        blob.upload_from_string(json.dumps(data), content_type='application/json')
        file_url = blob.public_url

        # f"在uploadJson中的檔案名稱: {file.filename}, 檔案內容: {data}, 檔案的連結: {file_url}"

        user_ref = db.collection('users').document(user_id)
        files_ref = user_ref.collection('files').document(file.filename)
        files_ref.set({
            'file_name': file.filename,
            'file_url': file_url,
            'content': data,
            'timestamp': datetime.now(pytz.UTC)
        })
        return jsonify({'success': True, 'file_url': file_url, 'data': data})

@app.route('/check_file_exists', methods=['POST'])
def check_file_exists():
    data = request.get_json()
    file_name = data.get('file_name')
    user_id = data.get('user_id')

    print(f"file_name: {file_name}, user_id: {user_id}")

    try:
        user_ref = db.collection('users').document(user_id)
        files_ref = user_ref.collection('files').where('file_name', '==', file_name).stream()
        file_exists = len(list(files_ref)) > 0
        print(f"file_exists counts {file_exists}") 
        return jsonify(exists=file_exists)
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify(success=False, message=str(e))

# 在側邊欄顯示用戶的文件
@app.route('/api/files', methods=['GET'])
def get_files():
    user_id = request.args.get('user_id')

    try:
        user_ref = db.collection('users').document(user_id)
        files_ref = user_ref.collection('files').stream()
        files = [{'id': file.id, 'file_name': file.to_dict()['file_name']} for file in files_ref]
        return jsonify(success=True, files=files)
    except Exception as e:
        return jsonify(success=False, message=str(e))

# 在資料庫抓取文件內容並顯示在網頁上
@app.route('/api/file', methods=['GET'])
def get_file():
    file_id = request.args.get('file_id')
    user_id = request.args.get('user_id') 

    try:
        file_ref = db.collection('users').document(user_id).collection('files').document(file_id)
        file_doc = file_ref.get()
        if file_doc.exists:
            file_data = file_doc.to_dict()
            return jsonify(success=True, file=file_data)
        else:
            return jsonify(success=False, message='File not found')
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify(success=False, message=str(e))

#修改檔案名稱
@app.route('/saveFileName', methods=['POST'])
def save_fileName():
    try:
        print("Received request data:", request.form)  

        user_id = request.form.get('user_id')
        file_id = request.form.get('file_id')
        new_file_name = request.form.get('file_Name')

        user_ref = db.collection('users').document(user_id)
        file_ref = user_ref.collection('files').document(file_id)
        print(f"file_ref is", file_ref)

        file_doc = file_ref.get()
        if not file_doc.exists:
            return jsonify({"success": False, "message": "File not found"}), 404

        new_file_check = user_ref.collection('files').where('file_name', '==', new_file_name).get()
        if len(new_file_check) > 0:
            return jsonify({"success": False, "message": f"File name '{new_file_name}' already exists"}), 409

        old_file_data = file_doc.to_dict()
        old_file_data['file_name'] = new_file_name
        new_file_ref = user_ref.collection('files').document(new_file_name)
        new_file_ref.set(old_file_data)
        file_ref.delete()
        response = {"success": True, "new_file_name": new_file_name}

        return jsonify(response)
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/deleteFile', methods=['POST'])
def delete_file():
    user_id = request.form.get('user_id')
    file_id = request.form.get('file_id')

    user_ref = db.collection('users').document(user_id)
    file_ref = user_ref.collection('files').document(file_id)

    file_ref.delete()
    response = {"success": True}

    return jsonify(response)

if __name__ == '__main__':
    app.run(port=5001, debug=True)
