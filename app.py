from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response, g
from dotenv import load_dotenv
import pymysql.cursors
import pymysql
import os

load_dotenv()

app = Flask(__name__)
app.secret_key = 'vibely_super_secret_key_change_this'

# Fixed PyMySQL Wrapper using Flask 'g' object (Persists connection per request so commit works!)
class PyMySQLWrapper:
    def __init__(self, app=None):
        if app:
            self.init_app(app)
            
    def init_app(self, app):
        app.teardown_appcontext(self.teardown)
        
    @property
    def connection(self):
        if 'mysql_connection' not in g:
            g.mysql_connection = pymysql.connect(
                host=os.getenv('MYSQL_HOST'),
                user=os.getenv('MYSQL_USER'),
                password=os.getenv('MYSQL_PASSWORD'),
                database=os.getenv('MYSQL_DB'),
                port=int(os.getenv('MYSQL_PORT', 4000)),
                cursorclass=pymysql.cursors.DictCursor,
                ssl={'ssl': {}}
            )
        return g.mysql_connection

    def teardown(self, exception):
        conn = g.pop('mysql_connection', None)
        if conn is not None:
            conn.close()

mysql = PyMySQLWrapper(app)

# Middleware / Before Request to check Session & Cookies
@app.before_request
def check_auth():
    allowed_routes = ['login', 'signup', 'logout', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        cookie_user = request.cookies.get('vibely_session_id')
        if cookie_user:
            try:
                user_id = int(cookie_user)
                cursor = mysql.connection.cursor()
                cursor.execute("SELECT id, username FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                cursor.close()
                if user:
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                else:
                    return redirect(url_for('login'))
            except Exception:
                return redirect(url_for('login'))
        else:
            return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_email = request.form['username']
        password = request.form['password']
        
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT * FROM users WHERE (username = %s OR email = %s)", 
                       (username_email, username_email))
        user = cursor.fetchone()
        cursor.close()
        
        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            resp = make_response(redirect(url_for('home')))
            resp.set_cookie('vibely_session_id', str(user['id']), max_age=60*60*24*7)
            return resp
        else:
            return render_template('login.html', error="Invalid credentials!")
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('login.html')
        
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    gender = request.form.get('gender', 'others')
    
    try:
        cursor = mysql.connection.cursor()
        
        # Check if username or email already exists
        cursor.execute("SELECT id FROM users WHERE username = %s OR email = %s", (username, email))
        if cursor.fetchone():
            cursor.close()
            return render_template('login.html', error="Username or Email already taken!")

        cursor.execute("INSERT INTO users (username, email, password, gender) VALUES (%s, %s, %s, %s)", 
                       (username, email, password, gender))
        mysql.connection.commit()
        
        user_id = cursor.lastrowid
        cursor.close()
        
        session['user_id'] = user_id
        session['username'] = username
        
        resp = make_response(redirect(url_for('home')))
        resp.set_cookie('vibely_session_id', str(user_id), max_age=60*60*24*7)
        return resp
        
    except Exception as e:
        print("Signup Error:", str(e))
        return render_template('login.html', error=f"Error: {str(e)}")

@app.route('/logout')
def logout():
    session.clear()
    resp = make_response(redirect(url_for('login')))
    resp.set_cookie('vibely_session_id', '', expires=0)
    return resp

@app.route('/inbox')
def chat_dashboard():
    cursor = mysql.connection.cursor()
    user_id = session['user_id']
    
    cursor.execute("""
        SELECT u.id, u.username, u.verified,
               MAX(m.timestamp) as last_time,
               SUM(CASE WHEN m.receiver_id = %s AND m.is_seen = 0 AND m.delete_status = 0 AND m.deleted = 0 THEN 1 ELSE 0 END) as unread_count
        FROM users u 
        JOIN messages m ON (u.id = m.sender_id OR u.id = m.receiver_id)
        WHERE (m.sender_id = %s OR m.receiver_id = %s) AND u.id != %s AND m.deleted = 0
        GROUP BY u.id, u.username, u.verified, u.name
        ORDER BY unread_count DESC, last_time DESC
    """, (user_id, user_id, user_id, user_id))
    chat_users = cursor.fetchall()
    
    cursor.execute("SELECT id, username FROM users WHERE id != %s", (user_id,))
    all_users = cursor.fetchall()
    
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    current_user = cursor.fetchone()
    cursor.close()
    
    return render_template('chat.html', chat_users=chat_users, all_users=all_users, current_user=current_user)

def check_privacy(val):
    if isinstance(val, bytes):
        return int(val[0]) if len(val) > 0 else 0
    return int(val) if val else 0

@app.route('/home')
def home():
    cursor = mysql.connection.cursor()
    user_id = session.get('user_id')
    
    if not user_id:
        cursor.close()
        return redirect(url_for('login'))
        
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    current_user = cursor.fetchone()
    
    if not current_user:
        cursor.close()
        session.clear()
        return redirect(url_for('login'))
    
    cursor.execute("""
        SELECT s.*, u.username, u.verified 
        FROM stories s 
        JOIN users u ON s.uploaded_by = u.id 
        WHERE s.time_of_upload >= NOW() - INTERVAL 1 DAY
        ORDER BY s.time_of_upload DESC
    """)
    stories = cursor.fetchall()
    
    cursor.execute("""
        SELECT p.*, u.username, u.verified, 
               (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count
        FROM posts p 
        JOIN users u ON p.user_id = u.id 
        WHERE (u.is_private = 0 OR p.user_id = %s OR p.user_id IN (SELECT following_id FROM followings WHERE my_id = %s))
        ORDER BY RAND() LIMIT 10
    """, (user_id, user_id))
    posts = cursor.fetchall()
    
    cursor.execute("""
        SELECT id, username, verified FROM users 
        WHERE id != %s AND id NOT IN (SELECT following_id FROM followings WHERE my_id = %s)
        ORDER BY RAND() LIMIT 5
    """, (user_id, user_id))
    suggestions = cursor.fetchall()
    
    cursor.close()
    return render_template('home.html', current_user=current_user, stories=stories, posts=posts, suggestions=suggestions)

@app.route('/api/random_posts')
def get_random_posts():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT p.*, u.username, u.verified, 
                   (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count
            FROM posts p 
            JOIN users u ON p.user_id = u.id 
            WHERE (u.is_private = 0 OR p.user_id = %s OR p.user_id IN (SELECT following_id FROM followings WHERE my_id = %s))
            ORDER BY RAND() LIMIT 10
        """, (user_id, user_id))
        posts = cursor.fetchall()
        cursor.close()
        return jsonify(posts)
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/comment', methods=['POST'])
def add_comment():
    data = request.json
    user_id = session.get('user_id')
    post_id = data.get('post_id')
    comment_text = data.get('comment_text')

    if not user_id or not post_id or not comment_text:
        return jsonify({"status": "error", "message": "Missing parameters"}), 400

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("INSERT INTO comments (post_id, user_id, comment_text) VALUES (%s, %s, %s)", 
                       (post_id, user_id, comment_text))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"status": "success"})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/create', methods=['POST'])
def create_content():
    data = request.json
    user_id = session['user_id']
    content = data.get('content')
    is_post = data.get('is_post', False)
    is_story = data.get('is_story', False)
    
    cursor = mysql.connection.cursor()
    if is_post and content:
        cursor.execute("INSERT INTO posts (user_id, content) VALUES (%s, %s)", (user_id, content))
    if is_story and content:
        cursor.execute("INSERT INTO stories (uploaded_by, text) VALUES (%s, %s)", (user_id, content))
        
    mysql.connection.commit()
    cursor.close()
    return jsonify({"status": "success"})

@app.route('/api/follow', methods=['POST'])
def follow_user():
    data = request.json
    my_id = session.get('user_id')
    target_id = data.get('target_id')
    
    if not my_id or not target_id:
        return jsonify({"status": "error", "message": "Unauthorized or missing parameters"}), 400
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT * FROM followings WHERE my_id = %s AND following_id = %s", (my_id, target_id))
        existing_follow = cursor.fetchone()
        
        if existing_follow:
            cursor.execute("DELETE FROM followings WHERE my_id = %s AND following_id = %s", (my_id, target_id))
            cursor.execute("DELETE FROM followers WHERE user_id = %s AND followed_by_id = %s", (target_id, my_id))
            action = "unfollowed"
        else:
            cursor.execute("INSERT IGNORE INTO followings (my_id, following_id) VALUES (%s, %s)", (my_id, target_id))
            cursor.execute("INSERT IGNORE INTO followers (user_id, followed_by_id) VALUES (%s, %s)", (target_id, my_id))
            action = "followed"
            
        mysql.connection.commit()
        cursor.close()
        return jsonify({"status": "success", "action": action})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/search_users')
def search_users():
    query = request.args.get('q', '')
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, username, verified FROM users WHERE username LIKE %s LIMIT 10", ('%' + query + '%',))
    users = cursor.fetchall()
    cursor.close()
    return jsonify(users)

@app.route('/api/messages/<int:receiver_id>')
def get_messages(receiver_id):
    sender_id = session['user_id']
    cursor = mysql.connection.cursor()
    
    cursor.execute("SELECT * FROM blocked_accounts WHERE (blocker_id = %s AND blocked_id = %s) OR (blocker_id = %s AND blocked_id = %s)", 
                   (sender_id, receiver_id, receiver_id, sender_id))
    blocks = cursor.fetchall()
    
    i_blocked_them = any(b['blocker_id'] == sender_id for b in blocks)
    they_blocked_me = any(b['blocker_id'] == receiver_id for b in blocks)
    
    cursor.execute("""
        UPDATE messages 
        SET is_seen = 1 
        WHERE sender_id = %s AND receiver_id = %s AND is_seen = 0
    """, (receiver_id, sender_id))
    mysql.connection.commit()

    cursor.execute("""
        SELECT * FROM messages 
        WHERE ((sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s))
          AND delete_status = 0 AND deleted = 0
        ORDER BY timestamp ASC
    """, (sender_id, receiver_id, receiver_id, sender_id))
    messages = cursor.fetchall()
    
    cursor.execute("SELECT id, username, verified, name FROM users WHERE id = %s", (receiver_id,))
    recipient = cursor.fetchone()
    cursor.close()
    
    return jsonify({
        "messages": messages,
        "i_blocked_them": i_blocked_them,
        "they_blocked_me": they_blocked_me,
        "recipient": recipient
    })

@app.route('/api/message/edit', methods=['POST'])
def edit_message():
    data = request.json
    user_id = session.get('user_id')
    msg_id = data.get('message_id')
    new_text = data.get('new_text')
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE messages SET message = %s WHERE id = %s AND sender_id = %s", (new_text, msg_id, user_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"status": "success"})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/message/delete', methods=['POST'])
def delete_message():
    data = request.json
    user_id = session.get('user_id')
    msg_id = data.get('message_id')
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE messages SET deleted = 1 WHERE id = %s AND (sender_id = %s OR receiver_id = %s)", (msg_id, user_id, user_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"status": "success"})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/send', methods=['POST'])
def send_message():
    data = request.json
    sender_id = session['user_id']
    receiver_id = data.get('receiver_id')
    message_text = data.get('message')
    
    if message_text and receiver_id:
        cursor = mysql.connection.cursor()
        cursor.execute("INSERT INTO messages (sender_id, receiver_id, message) VALUES (%s, %s, %s)", 
                       (sender_id, receiver_id, message_text))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route('/api/unread_status')
def unread_status():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"has_unread": False})
    
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT COUNT(*) as count 
        FROM messages 
        WHERE receiver_id = %s AND is_seen = 0 AND delete_status = 0
    """, (user_id,))
    res = cursor.fetchone()
    cursor.close()
    
    has_unread = res['count'] > 0 if res else False
    return jsonify({"has_unread": has_unread})

@app.route('/app/<username>')
def profile(username):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    profile_user = cursor.fetchone()
    
    if not profile_user:
        cursor.close()
        return "User not found", 404
        
    my_id = session.get('user_id')
    is_my_profile = (my_id == profile_user['id'])
    
    is_following = False
    they_follow_me = False
    if not is_my_profile and my_id:
        cursor.execute("SELECT * FROM followings WHERE my_id = %s AND following_id = %s", (my_id, profile_user['id']))
        is_following = cursor.fetchone() is not None
        
        cursor.execute("SELECT * FROM followings WHERE my_id = %s AND following_id = %s", (profile_user['id'], my_id))
        they_follow_me = cursor.fetchone() is not None

    account_is_private = check_privacy(profile_user.get('is_private'))

    can_view = True
    if account_is_private and not is_my_profile:
        can_view = they_follow_me

    posts = []
    cursor.execute("SELECT COUNT(*) as count FROM posts WHERE user_id = %s", (profile_user['id'],))
    post_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM followers WHERE user_id = %s", (profile_user['id'],))
    follower_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM followings WHERE my_id = %s", (profile_user['id'],))
    following_count = cursor.fetchone()['count']

    if can_view:
        cursor.execute("SELECT * FROM posts WHERE user_id = %s ORDER BY timestamp DESC", (profile_user['id'],))
        posts = cursor.fetchall()
        
    cursor.close()
    return render_template('profile.html', 
                           profile_user=profile_user, 
                           posts=posts, 
                           post_count=post_count, 
                           follower_count=follower_count, 
                           following_count=following_count, 
                           is_my_profile=is_my_profile, 
                           is_following=is_following,
                           they_follow_me=they_follow_me,
                           can_view=can_view)

@app.route('/api/followers/<int:user_id>')
def get_followers(user_id):
    my_id = session.get('user_id')
    cursor = mysql.connection.cursor()
    
    cursor.execute("SELECT is_private FROM users WHERE id = %s", (user_id,))
    target_user = cursor.fetchone()
    if not target_user:
        cursor.close()
        return jsonify([]), 404
        
    is_my_profile = (my_id == user_id)
    they_follow_me = False
    if not is_my_profile and my_id:
        cursor.execute("SELECT * FROM followings WHERE my_id = %s AND following_id = %s", (user_id, my_id))
        they_follow_me = cursor.fetchone() is not None
        
    account_is_private = check_privacy(target_user.get('is_private'))
    if account_is_private and not is_my_profile and not they_follow_me:
        cursor.close()
        return jsonify([]), 403

    cursor.execute("""
        SELECT u.id, u.username, u.name, u.verified 
        FROM followers f 
        JOIN users u ON f.followed_by_id = u.id 
        WHERE f.user_id = %s
    """, (user_id,))
    users = cursor.fetchall()
    cursor.close()
    return jsonify(users)

@app.route('/api/followings/<int:user_id>')
def get_followings(user_id):
    my_id = session.get('user_id')
    cursor = mysql.connection.cursor()
    
    cursor.execute("SELECT is_private FROM users WHERE id = %s", (user_id,))
    target_user = cursor.fetchone()
    if not target_user:
        cursor.close()
        return jsonify([]), 404
        
    is_my_profile = (my_id == user_id)
    they_follow_me = False
    if not is_my_profile and my_id:
        cursor.execute("SELECT * FROM followings WHERE my_id = %s AND following_id = %s", (user_id, my_id))
        they_follow_me = cursor.fetchone() is not None
        
    account_is_private = check_privacy(target_user.get('is_private'))
    if account_is_private and not is_my_profile and not they_follow_me:
        cursor.close()
        return jsonify([]), 403

    cursor.execute("""
        SELECT u.id, u.username, u.name, u.verified 
        FROM followings f 
        JOIN users u ON f.following_id = u.id 
        WHERE f.my_id = %s
    """, (user_id,))
    users = cursor.fetchall()
    cursor.close()
    return jsonify(users)

@app.route('/api/update_privacy', methods=['POST'])
def update_privacy():
    data = request.json
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    is_private = 1 if data.get('is_private') else 0
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("UPDATE users SET is_private = %s WHERE id = %s", (is_private, user_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"status": "success"})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/app/profile/<username>')
def other_profile(username):
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    profile_user = cursor.fetchone()
    
    if not profile_user:
        cursor.close()
        return "User not found", 404
        
    my_id = session.get('user_id')
    if my_id == profile_user['id']:
        cursor.close()
        return redirect(url_for('profile', username=username))
        
    cursor.execute("SELECT * FROM posts WHERE user_id = %s ORDER BY timestamp DESC", (profile_user['id'],))
    posts = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as count FROM posts WHERE user_id = %s", (profile_user['id'],))
    post_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM followers WHERE user_id = %s", (profile_user['id'],))
    follower_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM followings WHERE my_id = %s", (profile_user['id'],))
    following_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT * FROM followings WHERE my_id = %s AND following_id = %s", (my_id, profile_user['id']))
    is_following = cursor.fetchone() is not None
    
    cursor.close()
    return render_template('profile.html', profile_user=profile_user, posts=posts, post_count=post_count, follower_count=follower_count, following_count=following_count, is_my_profile=False, is_following=is_following)

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', message="Oops! The page you are looking for does not exist."), 404

@app.route('/app/feed/<int:post_id>')
def view_post(post_id):
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT p.*, u.username, u.verified, 
               (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count
        FROM posts p 
        JOIN users u ON p.user_id = u.id 
        WHERE p.id = %s
    """, (post_id,))
    post = cursor.fetchone()
    
    cursor.execute("SELECT c.*, u.username, u.verified FROM comments c JOIN users u ON c.user_id = u.id WHERE c.post_id = %s ORDER BY c.timestamp ASC", (post_id,))
    comments = cursor.fetchall()
    
    user_id = session.get('user_id')
    current_user = None
    if user_id:
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        current_user = cursor.fetchone()
        
    cursor.close()
    
    if not post:
        return render_template('404.html', message=f"Post #{post_id} could not be found or has been removed."), 404
        
    return render_template('single_post.html', post=post, comments=comments, current_user=current_user)

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    data = request.json
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    name = data.get('name', 'Vibely Member')
    new_username = data.get('username')
    new_email = data.get('email')
    bio = data.get('bio', '')
    dob = data.get('dob') or None
    gender = data.get('gender', 'others')
    
    if 'is_private' in data:
        is_private = 1 if data.get('is_private') else 0
    else:
        cursor = mysql.connection.cursor()
        cursor.execute("SELECT is_private FROM users WHERE id = %s", (user_id,))
        res = cursor.fetchone()
        cursor.close()
        is_private = res['is_private'] if res else 0
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (new_username, user_id))
        if cursor.fetchone():
            cursor.close()
            return jsonify({"status": "error", "message": "Username already taken!"}), 400

        cursor.execute("SELECT id FROM users WHERE email = %s AND id != %s", (new_email, user_id))
        if cursor.fetchone():
            cursor.close()
            return jsonify({"status": "error", "message": "Email already in use!"}), 400

        cursor.execute("""
            UPDATE users 
            SET name = %s, username = %s, email = %s, bio = %s, dob = %s, gender = %s, is_private = %s 
            WHERE id = %s
        """, (name, new_username, new_email, bio, dob, gender, is_private, user_id))
        
        mysql.connection.commit()
        cursor.close()
        session['username'] = new_username
        
        return jsonify({"status": "success", "username": new_username})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/block_user', methods=['POST'])
def block_user():
    data = request.json
    my_id = session.get('user_id')
    target_id = data.get('target_id')
    if not my_id or not target_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 400
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("INSERT IGNORE INTO blocked_accounts (blocker_id, blocked_id) VALUES (%s, %s)", (my_id, target_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"status": "success", "action": "blocked"})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/unblock_user', methods=['POST'])
def unblock_user():
    data = request.json
    my_id = session.get('user_id')
    target_id = data.get('target_id')
    if not my_id or not target_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 400
        
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("DELETE FROM blocked_accounts WHERE blocker_id = %s AND blocked_id = %s", (my_id, target_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"status": "success", "action": "unblocked"})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/delete_chat', methods=['POST'])
def delete_chat():
    data = request.json
    my_id = session.get('user_id')
    target_id = data.get('target_id')
    if not my_id or not target_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 400
        
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            UPDATE messages 
            SET deleted = 1 
            WHERE ((sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s))
        """, (my_id, target_id, target_id, my_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"status": "success"})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/recover_chat', methods=['POST'])
def recover_chat():
    data = request.json
    my_id = session.get('user_id')
    target_id = data.get('target_id')
    if not my_id or not target_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 400
        
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT verified FROM users WHERE id = %s", (my_id,))
        user = cursor.fetchone()
        
        if not user or not user.get('verified'):
            cursor.close()
            return jsonify({"status": "error", "message": "Only verified users can recover chats!"}), 403
            
        cursor.execute("""
            UPDATE messages 
            SET deleted = 0 
            WHERE ((sender_id = %s AND receiver_id = %s) OR (sender_id = %s AND receiver_id = %s))
        """, (my_id, target_id, target_id, my_id))
        mysql.connection.commit()
        cursor.close()
        return jsonify({"status": "success"})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/chat_list')
def api_chat_list():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify([])
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT u.id, u.username, u.verified, u.name,
               MAX(m.timestamp) as last_time,
               SUM(CASE WHEN m.receiver_id = %s AND m.is_seen = 0 AND m.delete_status = 0 AND m.deleted = 0 THEN 1 ELSE 0 END) as unread_count
        FROM users u 
        JOIN messages m ON (u.id = m.sender_id OR u.id = m.receiver_id)
        WHERE (m.sender_id = %s OR m.receiver_id = %s) AND u.id != %s AND m.deleted = 0
        GROUP BY u.id, u.username, u.verified, u.name
        ORDER BY unread_count DESC, last_time DESC
    """, (user_id, user_id, user_id, user_id))
    chat_users = cursor.fetchall()
    cursor.close()
    
    for cu in chat_users:
        if cu.get('last_time'):
            cu['last_time'] = cu['last_time'].strftime('%Y-%m-%d %H:%M:%S')
    return jsonify(chat_users)

@app.route('/api/like', methods=['POST'])
def toggle_like():
    data = request.json
    user_id = session.get('user_id')
    post_id = data.get('post_id')

    if not user_id or not post_id:
        return jsonify({"status": "error", "message": "Unauthorized or missing parameters"}), 400

    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT id FROM likes WHERE post_id = %s AND user_id = %s", (post_id, user_id))
        existing_like = cursor.fetchone()

        if existing_like:
            cursor.execute("DELETE FROM likes WHERE post_id = %s AND user_id = %s", (post_id, user_id))
            liked = False
        else:
            cursor.execute("INSERT INTO likes (post_id, user_id) VALUES (%s, %s)", (post_id, user_id))
            liked = True

        mysql.connection.commit()

        cursor.execute("SELECT COUNT(*) as count FROM likes WHERE post_id = %s", (post_id,))
        like_count = cursor.fetchone()['count']
        cursor.close()

        return jsonify({"status": "success", "liked": liked, "like_count": like_count})

    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/app/settings')
def settings_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('login'))
    
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    current_user = cursor.fetchone()
    cursor.close()
    
    return render_template('settings.html', current_user=current_user)
    
if __name__ == '__main__':
    app.run(debug=False)