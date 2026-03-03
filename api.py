from flask import Flask, request, jsonify
from flask_cors import CORS
import cloudscraper
from datetime import datetime
import pytz
from Crypto.Cipher import AES
from Crypto.Util.Padding import pad
from base64 import b64encode
import urllib3
from concurrent.futures import ThreadPoolExecutor
import threading

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = Flask(__name__)
CORS(app)

# Thread pool for handling concurrent requests
executor = ThreadPoolExecutor(max_workers=20)

# Thread-local storage for scrapers (one per thread)
thread_local = threading.local()

MOBILE_API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3NzI1NTUyNzAsImNvbiI6eyJpc0FkbWluIjpmYWxzZSwiYXVzZXIiOiIiLCJpZCI6Ik4xRXZTSFoxYW1aSWRYSjRiRlJvWkZaNWNHUTFRVDA5IiwiZmlyc3RfbmFtZSI6IkszUk5TR2s1ZWs4MWJETllXRmcyUmxCQ1lrSmtaejA5IiwiZW1haWwiOiJjUzlMZVVjMmJrczFTME5vVFZSd1VtdFNaa2hwZDNSdE1tRXhSbVZOTDNjdmMwZHRXak5XWm1wak5EMD0iLCJwaG9uZSI6ImQxTmplREpGVkdaWldVbFFhVkJLUm1ZMFdrcEpVVDA5IiwiYXZhdGFyIjoiIiwicmVmZXJyYWxfY29kZSI6ImFHVjBhVk5qSzBSQ2RuUnlURVJSUVdVME0xRllRVDA5IiwiZGV2aWNlX3R5cGUiOiJ3ZWIiLCJkZXZpY2VfdmVyc2lvbiI6IjE0NS4wLjAuMCIsImRldmljZV9tb2RlbCI6IkNocm9tZUNETSIsInJlbW90ZV9hZGRyIjoiMjQwMTo0OTAwOjg2Yjc6Yzc2MjoxZDZhOjk0YzI6MjE1ZDpmOTBiIn19.GTPggSCGLjxJg1kEJuCgq1aBeowdMusdm1ZqnsxvV2iQpL_zNlo1kxR7isjLTefdbNc_HA4ROsV5ruxVaGdr5H_MxHA44llb7M1HKb-W18NToAhMXuM_3Ee5JBQVIgO0F_db1qvGfoMtwOhQ6No4drQsSHivpXoLUste8fXZbqVkGze3NBTpl-l5_MI3ncDrD2NKvck3JoB64pL5SAYrGEBuYRHq4rZObHvdu6n2VzBVqo3koV5FV-sY0zFJB2o80XgOOt69VKawMhhrNBuhx-eS50b2F0Fk4pyO3HJzVaaUzzABe4V8bqMsgcFPg74KCDPZVp_5SvYofBfc7agTRQ"


class CryptoUtils:
    def __init__(self):
        self.key = b"E12K7l97Z7wCo3Gu"
        self.iv = b"mOk15J2m12qZ2tKI"

    def generate_cwkey_datetime(self, app_identifier="careerwillapp"):
        ist = pytz.timezone("Asia/Kolkata")
        dt = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
        payload = f"{dt}||{app_identifier}||{dt}".encode()

        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        encrypted = cipher.encrypt(pad(payload, AES.block_size))
        return b64encode(encrypted).decode()


def get_mobile_headers():
    crypto = CryptoUtils()
    return {
        "Host": "elearn.crwilladmin.com",
        "token": MOBILE_API_TOKEN,
        "usertype": "",
        "appver": "226",
        "apptype": "android",
        "cwkey": crypto.generate_cwkey_datetime(),
        "accept-encoding": "gzip",
        "user-agent": "okhttp/5.0.0",
    }


def get_scraper():
    """Get or create a scraper for the current thread"""
    if not hasattr(thread_local, "scraper"):
        thread_local.scraper = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'android',
                'mobile': True
            }
        )
    return thread_local.scraper


def fetch_notes_data(batch_id, topic_id):
    notes_url = (
        f"https://elearn.crwilladmin.com/api/v10/batch-notes/"
        f"{batch_id}?type=notes&subjectId={topic_id}&chapterId=0"
    )
    pyq_url = (
        f"https://elearn.crwilladmin.com/api/v10/batch-notes/"
        f"{batch_id}?type=png&subjectId={topic_id}&chapterId=0"
    )

    headers = get_mobile_headers()
    scraper = get_scraper()

    all_items = []

    # Fetch Notes (PDFs)
    try:
        response = scraper.get(notes_url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get("responseCode") == 200:
            notes_list = data.get("data", {}).get("notesList", [])
            for note in notes_list:
                note['type'] = 'PDF'
                all_items.append(note)
    except Exception as e:
        print(f"Error fetching PDFs: {e}")

    # Fetch PYQs (PNGs)
    try:
        response = scraper.get(pyq_url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if data.get("responseCode") == 200:
            pyq_list = data.get("data", {}).get("notesList", [])
            for pyq in pyq_list:
                pyq['type'] = 'PNG'
                all_items.append(pyq)
    except Exception as e:
        print(f"Error fetching PNGs: {e}")

    # Sort by publishedAt and notesno
    if all_items:
        def parse_date(date_str):
            try:
                return datetime.strptime(date_str, "%d-%b-%Y")
            except:
                return datetime.min

        all_items.sort(key=lambda x: (parse_date(x.get("publishedAt", "")), x.get("notesno", 0)))

    return all_items


def fetch_video_details(vid_id, batch_id="3347", token=None):
    vid_url = f'https://elearn.crwilladmin.com/api/v11/class-detail/{vid_id}?batchId={batch_id}'
    
    crypto = CryptoUtils()
    headers = {
        "Host": "elearn.crwilladmin.com",
        "token": token if token else MOBILE_API_TOKEN,
        "usertype": "",
        "appver": "124",
        "apptype": "android",
        "cwkey": crypto.generate_cwkey_datetime(),
        "accept-encoding": "gzip",
        "user-agent": "okhttp/5.0.0",
    }
    
    scraper = get_scraper()
    
    try:
        response = scraper.get(vid_url, headers=headers, timeout=60)
        response.raise_for_status()
        data = response.json()
        return data
        
    except Exception as e:
        raise Exception(f"Error fetching video details: {str(e)}")


@app.route('/')
def home():
    return jsonify({
        "message": "Notes API is running",
        "endpoints": {
            "/api/notes": "GET - Fetch notes (params: batch_id, topic_id)",
            "/api/video": "GET - Fetch video details (params: vid_id, batch_id [optional], token [optional])",
            "/health": "GET - Health check"
        }
    })


@app.route('/health')
def health():
    return jsonify({"status": "healthy"}), 200


@app.route('/api/notes', methods=['GET'])
def get_notes():
    batch_id = request.args.get('batch_id')
    topic_id = request.args.get('topic_id')
    
    if not batch_id or not topic_id:
        return jsonify({
            "error": "Missing required parameters",
            "required": ["batch_id", "topic_id"]
        }), 400
    
    try:
        notes = fetch_notes_data(batch_id, topic_id)
        
        return jsonify({
            "success": True,
            "count": len(notes),
            "data": notes
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/video', methods=['GET'])
def get_video():
    vid_id = request.args.get('vid_id')
    batch_id = request.args.get('batch_id', '3347')
    token = request.args.get('token')
    
    if not vid_id:
        return jsonify({
            "error": "Missing required parameter",
            "required": ["vid_id"]
        }), 400
    
    try:
        video_data = fetch_video_details(vid_id, batch_id, token)
        
        return jsonify({
            "success": True,
            "data": video_data
        }), 200
    
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 8000))
    # Use threaded mode for better concurrency
    app.run(host='0.0.0.0', port=port, threaded=True, debug=False)
# from flask import Flask, request, jsonify
# from flask_cors import CORS
# import cloudscraper
# from datetime import datetime
# import pytz
# from Crypto.Cipher import AES
# from Crypto.Util.Padding import pad
# from base64 import b64encode
# import urllib3

# urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# app = Flask(__name__)
# CORS(app)

# MOBILE_API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3NjczNTY5ODgsImNvbiI6eyJpc0FkbWluIjpmYWxzZSwiYXVzZXIiOiIiLCJpZCI6ImEwdzFlRXcxTTFWM1JWbFJSM0Z4VVVGMlMwNDNRVDA5IiwiZmlyc3RfbmFtZSI6Ik4zUkxVRm94ZUdGb00ydDNjblJDYjIxQlZTOXlVVDA5IiwiZW1haWwiOiJUeXRJV21vcloweFdZMmxVZFhsb2FrMDBVR3h5YTI5Q1IwNVdURzF1YlhkQ1kzRkVObGxRU25OaVl6MD0iLCJwaG9uZSI6IkwzcDNRMjFzUnpOME5tWndka3RRUVRCbU9URnpkejA5IiwiYXZhdGFyIjoiY25JdmVETnBRekkyZFZZelZGUmxjakJCTkd4VFN5OHhWVTFQV2t4S1RGUm1OM2t6VTBzd1N6UlpaejA9IiwicmVmZXJyYWxfY29kZSI6Ik5sZEZNbk5IZVZRMFJFUkJTRk5hZWs1V0wwVmFVVDA5IiwiZGV2aWNlX3R5cGUiOiJ3ZWIiLCJkZXZpY2VfdmVyc2lvbiI6IjE0My4wLjAuMCIsImRldmljZV9tb2RlbCI6IkNocm9tZUNETSIsInJlbW90ZV9hZGRyIjoiMjQwOTo0MGQyOjFjOjUzYzpmNGRlOjY4NjA6YTQ3MDplZDI1In19.sats2j9LijCGRxh0mZchICkB_h_IpPWoIuwLknjZIQLD3wuMFBeS4MUr7asrt8Mur6fB8LTTE981tWD6sV_eUNhDhi6qVfmy5ty2zMX8K3rmVsvMZCwqg3hVIX7frlFLf1mwOA-rb4idstqcIszguD3uqzoD-mgUHs9QJbKuuSaHYgh-CNYlvPUgw6PUoQHCV3RnmuxjBycmm2jaHUwaBB3Pzr_6tNU_Fm3-WyFfPj7WUXEHoehaRvFr6o2DQpq2b2WEzrNKTaNS8JtV08OBoDHd55rkhvJbCfcORF89MyY96OSPKlFDeOzE9UkMpQbT99Yd9sTJsJ6nG2sTzAfcew"


# class CryptoUtils:
#     def __init__(self):
#         self.key = b"E12K7l97Z7wCo3Gu"
#         self.iv = b"mOk15J2m12qZ2tKI"

#     def generate_cwkey_datetime(self, app_identifier="careerwillapp"):
#         ist = pytz.timezone("Asia/Kolkata")
#         dt = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
#         payload = f"{dt}||{app_identifier}||{dt}".encode()

#         cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
#         encrypted = cipher.encrypt(pad(payload, AES.block_size))
#         return b64encode(encrypted).decode()


# def get_mobile_headers():
#     crypto = CryptoUtils()
#     return {
#         "Host": "elearn.crwilladmin.com",
#         "token": MOBILE_API_TOKEN,
#         "usertype": "",
#         "appver": "124",
#         "apptype": "android",
#         "cwkey": crypto.generate_cwkey_datetime(),
#         "accept-encoding": "gzip",
#         "user-agent": "okhttp/5.0.0",
#     }


# def fetch_notes_data(batch_id, topic_id):
#     notes_url = (
#         f"https://elearn.crwilladmin.com/api/v10/batch-notes/"
#         f"{batch_id}?type=notes&subjectId={topic_id}&chapterId=0"
#     )
#     pyq_url = (
#         f"https://elearn.crwilladmin.com/api/v10/batch-notes/"
#         f"{batch_id}?type=png&subjectId={topic_id}&chapterId=0"
#     )

#     headers = get_mobile_headers()
    
#     scraper = cloudscraper.create_scraper(
#         browser={
#             'browser': 'chrome',
#             'platform': 'android',
#             'mobile': True
#         }
#     )

#     all_items = []

#     # Fetch Notes (PDFs)
#     try:
#         response = scraper.get(notes_url, headers=headers, timeout=30)
#         response.raise_for_status()
#         data = response.json()
        
#         if data.get("responseCode") == 200:
#             notes_list = data.get("data", {}).get("notesList", [])
#             for note in notes_list:
#                 note['type'] = 'PDF'
#                 all_items.append(note)
#     except Exception as e:
#         print(f"Error fetching PDFs: {e}")

#     # Fetch PYQs (PNGs)
#     try:
#         response = scraper.get(pyq_url, headers=headers, timeout=30)
#         response.raise_for_status()
#         data = response.json()
        
#         if data.get("responseCode") == 200:
#             pyq_list = data.get("data", {}).get("notesList", [])
#             for pyq in pyq_list:
#                 pyq['type'] = 'PNG'
#                 all_items.append(pyq)
#     except Exception as e:
#         print(f"Error fetching PNGs: {e}")

#     # Sort by publishedAt and notesno
#     if all_items:
#         def parse_date(date_str):
#             try:
#                 return datetime.strptime(date_str, "%d-%b-%Y")
#             except:
#                 return datetime.min

#         all_items.sort(key=lambda x: (parse_date(x.get("publishedAt", "")), x.get("notesno", 0)))

#     return all_items


# def fetch_video_details(vid_id, batch_id="3347", token=None):
#     vid_url = f'https://elearn.crwilladmin.com/api/v11/class-detail/{vid_id}?batchId={batch_id}'
    
#     crypto = CryptoUtils()
#     headers = {
#         "Host": "elearn.crwilladmin.com",
#         "token": token if token else MOBILE_API_TOKEN,
#         "usertype": "",
#         "appver": "124",
#         "apptype": "android",
#         "cwkey": crypto.generate_cwkey_datetime(),
#         "accept-encoding": "gzip",
#         "user-agent": "okhttp/5.0.0",
#     }
    
#     scraper = cloudscraper.create_scraper(
#         browser={
#             'browser': 'chrome',
#             'platform': 'android',
#             'mobile': True
#         }
#     )
    
#     try:
#         response = scraper.get(vid_url, headers=headers, timeout=30)
#         response.raise_for_status()
#         data = response.json()
#         return data
        
#     except Exception as e:
#         raise Exception(f"Error fetching video details: {str(e)}")


# @app.route('/')
# def home():
#     return jsonify({
#         "message": "Notes API is running",
#         "endpoints": {
#             "/api/notes": "GET - Fetch notes (params: batch_id, topic_id)",
#             "/api/video": "GET - Fetch video details (params: vid_id, batch_id [optional], token [optional])",
#             "/health": "GET - Health check"
#         }
#     })


# @app.route('/health')
# def health():
#     return jsonify({"status": "healthy"}), 200


# @app.route('/api/notes', methods=['GET'])
# def get_notes():
#     batch_id = request.args.get('batch_id')
#     topic_id = request.args.get('topic_id')
    
#     if not batch_id or not topic_id:
#         return jsonify({
#             "error": "Missing required parameters",
#             "required": ["batch_id", "topic_id"]
#         }), 400
    
#     try:
#         notes = fetch_notes_data(batch_id, topic_id)
        
#         return jsonify({
#             "success": True,
#             "count": len(notes),
#             "data": notes
#         }), 200
    
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500


# @app.route('/api/video', methods=['GET'])
# def get_video():
#     vid_id = request.args.get('vid_id')
#     batch_id = request.args.get('batch_id', '3347')
#     token = request.args.get('token')
    
#     if not vid_id:
#         return jsonify({
#             "error": "Missing required parameter",
#             "required": ["vid_id"]
#         }), 400
    
#     try:
#         video_data = fetch_video_details(vid_id, batch_id, token)
        
#         return jsonify({
#             "success": True,
#             "data": video_data
#         }), 200
    
#     except Exception as e:
#         return jsonify({
#             "success": False,
#             "error": str(e)
#         }), 500


# if __name__ == '__main__':
#     import os
#     port = int(os.environ.get('PORT', 8000))
#     app.run(host='0.0.0.0', port=port)
    
# # from flask import Flask, request, jsonify
# # from flask_cors import CORS
# # import cloudscraper
# # from datetime import datetime
# # import pytz
# # from Crypto.Cipher import AES
# # from Crypto.Util.Padding import pad
# # from base64 import b64encode
# # import urllib3

# # urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# # app = Flask(__name__)
# # CORS(app)

# # MOBILE_API_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE3NjczNTY5ODgsImNvbiI6eyJpc0FkbWluIjpmYWxzZSwiYXVzZXIiOiIiLCJpZCI6ImEwdzFlRXcxTTFWM1JWbFJSM0Z4VVVGMlMwNDNRVDA5IiwiZmlyc3RfbmFtZSI6Ik4zUkxVRm94ZUdGb00ydDNjblJDYjIxQlZTOXlVVDA5IiwiZW1haWwiOiJUeXRJV21vcloweFdZMmxVZFhsb2FrMDBVR3h5YTI5Q1IwNVdURzF1YlhkQ1kzRkVObGxRU25OaVl6MD0iLCJwaG9uZSI6IkwzcDNRMjFzUnpOME5tWndka3RRUVRCbU9URnpkejA5IiwiYXZhdGFyIjoiY25JdmVETnBRekkyZFZZelZGUmxjakJCTkd4VFN5OHhWVTFQV2t4S1RGUm1OM2t6VTBzd1N6UlpaejA9IiwicmVmZXJyYWxfY29kZSI6Ik5sZEZNbk5IZVZRMFJFUkJTRk5hZWs1V0wwVmFVVDA5IiwiZGV2aWNlX3R5cGUiOiJ3ZWIiLCJkZXZpY2VfdmVyc2lvbiI6IjE0My4wLjAuMCIsImRldmljZV9tb2RlbCI6IkNocm9tZUNETSIsInJlbW90ZV9hZGRyIjoiMjQwOTo0MGQyOjFjOjUzYzpmNGRlOjY4NjA6YTQ3MDplZDI1In19.sats2j9LijCGRxh0mZchICkB_h_IpPWoIuwLknjZIQLD3wuMFBeS4MUr7asrt8Mur6fB8LTTE981tWD6sV_eUNhDhi6qVfmy5ty2zMX8K3rmVsvMZCwqg3hVIX7frlFLf1mwOA-rb4idstqcIszguD3uqzoD-mgUHs9QJbKuuSaHYgh-CNYlvPUgw6PUoQHCV3RnmuxjBycmm2jaHUwaBB3Pzr_6tNU_Fm3-WyFfPj7WUXEHoehaRvFr6o2DQpq2b2WEzrNKTaNS8JtV08OBoDHd55rkhvJbCfcORF89MyY96OSPKlFDeOzE9UkMpQbT99Yd9sTJsJ6nG2sTzAfcew"


# # class CryptoUtils:
# #     def __init__(self):
# #         self.key = b"E12K7l97Z7wCo3Gu"
# #         self.iv = b"mOk15J2m12qZ2tKI"

# #     def generate_cwkey_datetime(self, app_identifier="careerwillapp"):
# #         ist = pytz.timezone("Asia/Kolkata")
# #         dt = datetime.now(ist).strftime("%Y-%m-%d %H:%M:%S")
# #         payload = f"{dt}||{app_identifier}||{dt}".encode()

# #         cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
# #         encrypted = cipher.encrypt(pad(payload, AES.block_size))
# #         return b64encode(encrypted).decode()


# # def get_mobile_headers():
# #     crypto = CryptoUtils()
# #     return {
# #         "Host": "elearn.crwilladmin.com",
# #         "token": MOBILE_API_TOKEN,
# #         "usertype": "",
# #         "appver": "124",
# #         "apptype": "android",
# #         "cwkey": crypto.generate_cwkey_datetime(),
# #         "accept-encoding": "gzip",
# #         "user-agent": "okhttp/5.0.0",
# #     }


# # def fetch_notes_data(batch_id, topic_id):
# #     notes_url = (
# #         f"https://elearn.crwilladmin.com/api/v10/batch-notes/"
# #         f"{batch_id}?type=notes&subjectId={topic_id}&chapterId=0"
# #     )
# #     pyq_url = (
# #         f"https://elearn.crwilladmin.com/api/v10/batch-notes/"
# #         f"{batch_id}?type=png&subjectId={topic_id}&chapterId=0"
# #     )

# #     headers = get_mobile_headers()
    
# #     scraper = cloudscraper.create_scraper(
# #         browser={
# #             'browser': 'chrome',
# #             'platform': 'android',
# #             'mobile': True
# #         }
# #     )

# #     all_items = []

# #     # Fetch Notes (PDFs)
# #     try:
# #         response = scraper.get(notes_url, headers=headers, timeout=30)
# #         response.raise_for_status()
# #         data = response.json()
        
# #         if data.get("responseCode") == 200:
# #             notes_list = data.get("data", {}).get("notesList", [])
# #             for note in notes_list:
# #                 note['type'] = 'PDF'
# #                 all_items.append(note)
# #     except Exception as e:
# #         print(f"Error fetching PDFs: {e}")

# #     # Fetch PYQs (PNGs)
# #     try:
# #         response = scraper.get(pyq_url, headers=headers, timeout=30)
# #         response.raise_for_status()
# #         data = response.json()
        
# #         if data.get("responseCode") == 200:
# #             pyq_list = data.get("data", {}).get("notesList", [])
# #             for pyq in pyq_list:
# #                 pyq['type'] = 'PNG'
# #                 all_items.append(pyq)
# #     except Exception as e:
# #         print(f"Error fetching PNGs: {e}")

# #     # Sort by publishedAt and notesno
# #     if all_items:
# #         def parse_date(date_str):
# #             try:
# #                 return datetime.strptime(date_str, "%d-%b-%Y")
# #             except:
# #                 return datetime.min

# #         all_items.sort(key=lambda x: (parse_date(x.get("publishedAt", "")), x.get("notesno", 0)))

# #     return all_items


# # @app.route('/')
# # def home():
# #     return jsonify({
# #         "message": "Notes API is running",
# #         "endpoints": {
# #             "/api/notes": "GET - Fetch notes (params: batch_id, topic_id)",
# #             "/health": "GET - Health check"
# #         }
# #     })


# # @app.route('/health')
# # def health():
# #     return jsonify({"status": "healthy"}), 200


# # @app.route('/api/notes', methods=['GET'])
# # def get_notes():
# #     batch_id = request.args.get('batch_id')
# #     topic_id = request.args.get('topic_id')
    
# #     if not batch_id or not topic_id:
# #         return jsonify({
# #             "error": "Missing required parameters",
# #             "required": ["batch_id", "topic_id"]
# #         }), 400
    
# #     try:
# #         notes = fetch_notes_data(batch_id, topic_id)
        
# #         return jsonify({
# #             "success": True,
# #             "count": len(notes),
# #             "data": notes
# #         }), 200
    
# #     except Exception as e:
# #         return jsonify({
# #             "success": False,
# #             "error": str(e)
# #         }), 500


# # if __name__ == '__main__':
# #     import os
# #     port = int(os.environ.get('PORT', 5000))
# #     app.run(host='0.0.0.0', port=port)




