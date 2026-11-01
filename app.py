from flask import Flask, render_template, request, redirect, url_for, session, jsonify, make_response, g
import pymysql
import pymysql.cursors
from dotenv import load_dotenv
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
    allowed_routes = ['login', 'signup', 'static']
    if request.endpoint not in allowed_routes and 'user_id' not in session:
        # Check if cookie exists for auto-login
        cookie_user = request.cookies.get('vibely_session_id')
        if cookie_user:
            session['user_id'] = cookie_user
        else:
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
        
        # Raw text password check
        if user and user['password'] == password:
            session['user_id'] = user['id']
            session['username'] = user['username']
            
            # Set Cookie for persistent login & redirect to home
            resp = make_response(redirect(url_for('home')))
            resp.set_cookie('vibely_session_id', str(user['id']), max_age=60*60*24*7) # 7 days
            return resp
        else:
            return render_template('login.html', error="Invalid credentials!")
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'GET':
        return render_template('login.html') # Or signup template if separate
        
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    
    try:
        cursor = mysql.connection.cursor()
        # Storing password as raw text directly
        cursor.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)", 
                       (username, email, password))
        mysql.connection.commit()
        cursor.close()
        return redirect(url_for('login'))
    except Exception as e:
        print("Signup Error:", str(e)) # Terminal mein real error print hoga
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
    
    # 1. Get ONLY users with whom the current user has an active chat history
    cursor.execute("""
        SELECT DISTINCT u.id, u.username 
        FROM users u 
        WHERE u.id IN (
            SELECT sender_id FROM messages WHERE receiver_id = %s
            UNION
            SELECT receiver_id FROM messages WHERE sender_id = %s
        )
    """, (user_id, user_id))
    chat_users = cursor.fetchall()
    
    # 2. Get ALL users (for starting new chats / search modal)
    cursor.execute("SELECT id, username FROM users WHERE id != %s", (user_id,))
    all_users = cursor.fetchall()
    
    # 3. Get current logged-in user info
    cursor.execute("SELECT username FROM users WHERE id = %s", (user_id,))
    current_user = cursor.fetchone()
    cursor.close()
    
    return render_template('chat.html', chat_users=chat_users, all_users=all_users, current_user=current_user)

# Update /home route to load random suggestions and initial 10 random posts
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
    
    # Active stories
    cursor.execute("""
        SELECT s.*, u.username, u.verified 
        FROM stories s 
        JOIN users u ON s.uploaded_by = u.id 
        WHERE s.time_of_upload >= NOW() - INTERVAL 1 DAY
        ORDER BY s.time_of_upload DESC
    """)
    stories = cursor.fetchall()
    
    # Initial 10 Random Posts (No sequence)
    cursor.execute("""
        SELECT p.*, u.username, u.verified, 
               (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count
        FROM posts p 
        JOIN users u ON p.user_id = u.id 
        ORDER BY RAND() LIMIT 10
    """)
    posts = cursor.fetchall()
    
    # Random Suggested Users (Max 5, excluding current user and already followed)
    cursor.execute("""
        SELECT id, username, verified FROM users 
        WHERE id != %s AND id NOT IN (SELECT following_id FROM followings WHERE my_id = %s)
        ORDER BY RAND() LIMIT 5
    """, (user_id, user_id))
    suggestions = cursor.fetchall()
    
    cursor.close()
    return render_template('home.html', current_user=current_user, stories=stories, posts=posts, suggestions=suggestions)

# API: Load More Random Posts on Scroll (Max 10 per request)
@app.route('/api/random_posts')
def get_random_posts():
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("""
            SELECT p.*, u.username, u.verified, 
                   (SELECT COUNT(*) FROM likes WHERE post_id = p.id) as like_count
            FROM posts p 
            JOIN users u ON p.user_id = u.id 
            ORDER BY RAND() LIMIT 10
        """)
        posts = cursor.fetchall()
        cursor.close()
        return jsonify(posts)
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

# API: Add Comment to a Post
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
    my_id = session['user_id']
    target_id = data.get('target_id')
    
    cursor = mysql.connection.cursor()
    # Add to followings
    cursor.execute("INSERT IGNORE INTO followings (my_id, following_id) VALUES (%s, %s)", (my_id, target_id))
    # Add to followers
    cursor.execute("INSERT IGNORE INTO followers (user_id, followed_by_id) VALUES (%s, %s)", (target_id, my_id))
    mysql.connection.commit()
    cursor.close()
    return jsonify({"status": "success"})

@app.route('/api/search_users')
def search_users():
    query = request.args.get('q', '')
    cursor = mysql.connection.cursor()
    cursor.execute("SELECT id, username, verified FROM users WHERE username LIKE %s LIMIT 10", ('%' + query + '%',))
    users = cursor.fetchall()
    cursor.close()
    return jsonify(users)

# API: Fetch Chat History with a specific user
@app.route('/api/messages/<int:receiver_id>')
def get_messages(receiver_id):
    sender_id = session['user_id']
    cursor = mysql.connection.cursor()
    cursor.execute("""
        SELECT * FROM messages 
        WHERE (sender_id = %s AND receiver_id = %s) 
           OR (sender_id = %s AND receiver_id = %s) 
        ORDER BY timestamp ASC
    """, (sender_id, receiver_id, receiver_id, sender_id))
    messages = cursor.fetchall()
    cursor.close()
    return jsonify(messages)

# API: Send a Message
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

@app.route('/app/<username>')
def my_profile(username):
    cursor = mysql.connection.cursor()
    # Fetch user details
    cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
    profile_user = cursor.fetchone()
    
    if not profile_user:
        cursor.close()
        return "User not found", 404
        
    # Check if logged in user matches this profile
    if session.get('user_id') != profile_user['id']:
        cursor.close()
        return redirect(url_for('other_profile', username=username))
        
    # Fetch user's posts
    cursor.execute("SELECT * FROM posts WHERE user_id = %s ORDER BY timestamp DESC", (profile_user['id'],))
    posts = cursor.fetchall()
    
    # Fetch post count, followers count, following count
    cursor.execute("SELECT COUNT(*) as count FROM posts WHERE user_id = %s", (profile_user['id'],))
    post_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM followers WHERE user_id = %s", (profile_user['id'],))
    follower_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM followings WHERE my_id = %s", (profile_user['id'],))
    following_count = cursor.fetchone()['count']
    
    cursor.close()
    return render_template('profile.html', profile_user=profile_user, posts=posts, post_count=post_count, follower_count=follower_count, following_count=following_count, is_my_profile=True)

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
        return redirect(url_for('my_profile', username=username))
        
    # Fetch posts
    cursor.execute("SELECT * FROM posts WHERE user_id = %s ORDER BY timestamp DESC", (profile_user['id'],))
    posts = cursor.fetchall()
    
    cursor.execute("SELECT COUNT(*) as count FROM posts WHERE user_id = %s", (profile_user['id'],))
    post_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM followers WHERE user_id = %s", (profile_user['id'],))
    follower_count = cursor.fetchone()['count']
    
    cursor.execute("SELECT COUNT(*) as count FROM followings WHERE my_id = %s", (profile_user['id'],))
    following_count = cursor.fetchone()['count']
    
    # Check if already following
    cursor.execute("SELECT * FROM followings WHERE my_id = %s AND following_id = %s", (my_id, profile_user['id']))
    is_following = cursor.fetchone() is not None
    
    cursor.close()
    return render_template('profile.html', profile_user=profile_user, posts=posts, post_count=post_count, follower_count=follower_count, following_count=following_count, is_my_profile=False, is_following=is_following)

# Global 404 Error Handler (For any invalid route/link)
@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html', message="Oops! The page you are looking for does not exist."), 404

# Update view_post route to handle missing posts gracefully
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
    
    # Agar post database mein nahi mili toh Coming Soon / 404 page dikhayein
    if not post:
        return render_template('404.html', message=f"Post #{post_id} could not be found or has been removed."), 404
        
    return render_template('single_post.html', post=post, comments=comments, current_user=current_user)

# API: Toggle Like/Unlike on a post
@app.route('/api/like', methods=['POST'])
def toggle_like():
    data = request.json
    user_id = session.get('user_id')
    post_id = data.get('post_id')

    if not user_id or not post_id:
        return jsonify({"status": "error", "message": "Unauthorized or missing parameters"}), 400

    cursor = mysql.connection.cursor()
    try:
        # Check if already liked
        cursor.execute("SELECT id FROM likes WHERE post_id = %s AND user_id = %s", (post_id, user_id))
        existing_like = cursor.fetchone()

        if existing_like:
            # Unlike the post
            cursor.execute("DELETE FROM likes WHERE post_id = %s AND user_id = %s", (post_id, user_id))
            liked = False
        else:
            # Like the post
            cursor.execute("INSERT INTO likes (post_id, user_id) VALUES (%s, %s)", (post_id, user_id))
            liked = True

        mysql.connection.commit()

        # Get updated total count
        cursor.execute("SELECT COUNT(*) as count FROM likes WHERE post_id = %s", (post_id,))
        like_count = cursor.fetchone()['count']
        cursor.close()

        return jsonify({"status": "success", "liked": liked, "like_count": like_count})

    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

# Update /api/update_profile to handle DOB
@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    data = request.json
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({"status": "error", "message": "Unauthorized"}), 401
        
    name = data.get('name', 'Vibely Member')
    new_username = data.get('username')
    bio = data.get('bio', '')
    dob = data.get('dob') or None
    gender = data.get('gender', 'others')
    
    cursor = mysql.connection.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE username = %s AND id != %s", (new_username, user_id))
        if cursor.fetchone():
            cursor.close()
            return jsonify({"status": "error", "message": "Username already taken!"}), 400

        cursor.execute("""
            UPDATE users 
            SET name = %s, username = %s, bio = %s, dob = %s, gender = %s 
            WHERE id = %s
        """, (name, new_username, bio, dob, gender, user_id))
        
        mysql.connection.commit()
        cursor.close()
        session['username'] = new_username
        
        return jsonify({"status": "success", "username": new_username})
    except Exception as e:
        cursor.close()
        return jsonify({"status": "error", "message": str(e)}), 500

# Settings Page Route
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