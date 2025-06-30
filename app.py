from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import requests, base64, time, json, os
from bs4 import BeautifulSoup
from datetime import datetime
from urllib.parse import unquote

app = Flask(__name__)
CORS(app)  # Buka CORS untuk akses dari frontend

API_KEY_2CAPTCHA = "bb253304e5436fd9fb8b714ddd8910fb"

@app.route("/api/login", methods=["POST"])

def login():
    data = request.json
    username = data.get("username")
    password = data.get("password")

    # Step 1: Dapatkan captcha dan token
    session = requests.Session()
    url_base64 = "aHR0cHM6Ly9zaW0ua2tuLnVkYi5hYy5pZC9zc28="
    login_url = f"https://auth.sso.udb.ac.id/?url={url_base64}"
    resp = session.get(login_url)
    soup = BeautifulSoup(resp.text, "html.parser")
    captcha_img = soup.find("img", {"id": "captcha"})["src"]
    token_hidden = soup.find("input", {"name": "token"})["value"]

    # Simpan captcha
    base64_data = captcha_img.split(",")[1]
    image_data = base64.b64decode(base64_data)
    with open("captcha.png", "wb") as f:
        f.write(image_data)

    # Kirim captcha ke 2Captcha
    files = {'file': ('captcha.png', open('captcha.png', 'rb'))}
    data = {'key': API_KEY_2CAPTCHA, 'method': 'post', 'json': 1}
    upload_response = requests.post("http://2captcha.com/in.php", files=files, data=data).json()
    captcha_id = upload_response["request"]

    # Tunggu hasil captcha
    for _ in range(20):
        result = requests.get(f"http://2captcha.com/res.php?key={API_KEY_2CAPTCHA}&action=get&id={captcha_id}&json=1").json()
        if result["status"] == 1:
            captcha_code = result["request"]
            break
        time.sleep(5)
    else:
        return jsonify({"error": "Captcha gagal"}), 400

    # Login
    login_data = {
        "user": username,
        "password": password,
        "captcha": captcha_code,
        "skin": "bootstrap",
        "timezone": "7",
        "token": token_hidden,
        "url": ""
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    login_resp = session.post(login_url, data=login_data, headers=headers, allow_redirects=False)
    redirect_url = login_resp.headers.get("Location")
    if not redirect_url.startswith("http"):
        redirect_url = "https://auth.sso.udb.ac.id" + redirect_url
    session.get(redirect_url, allow_redirects=True)
    session.get("https://sim.kkn.udb.ac.id/")

    # Ambil token
    cookies = session.cookies.get_dict()
    token = None
    if "moving_kkn" in cookies:
        parsed = json.loads(unquote(cookies["moving_kkn"]))
        token = parsed.get("token")

    if not token:
        return jsonify({"error": "Login gagal - token tidak ditemukan"}), 401

    return jsonify({"token": token, "cookies": cookies})

@app.route("/api/logbook", methods=["POST"])

def ambil_logbook():
    data = request.json
    token = data.get("token")
    cookies = data.get("cookies")
    
    cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
    headers = {
        "Authorization": token,
        "Cookie": cookie_str,
        "User-Agent": "Mozilla/5.0"
    }
    r = requests.get("https://sim.kkn.udb.ac.id/mahasiswa/logbook", headers=headers)
    try:
        return jsonify(r.json())
    except:
        return jsonify({"raw": r.text})

if __name__ == '__main__':
    app.run(debug=True)