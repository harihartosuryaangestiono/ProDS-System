from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import jwt
from datetime import datetime, timedelta
import re
import logging

# Configure logging for this module
logger = logging.getLogger(__name__)

# Definisikan blueprint sekali saja, tanpa url_prefix (akan diatur di app.py)
auth_bp = Blueprint('auth', __name__)

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**current_app.config['DB_CONFIG'])
        return conn
    except Exception as e:
        logger.error(f"Database connection error in auth_bp: {e}")
        return None

@auth_bp.route('/register', methods=['OPTIONS'])
def handle_register_preflight():
    response = jsonify({'message': 'OK'})
    response.headers.add('Access-Control-Allow-Methods', 'POST, OPTIONS')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    response.headers.add('Access-Control-Allow-Origin', 'http://localhost:5173')
    response.headers.add('Access-Control-Allow-Credentials', 'true')
    return response, 200

@auth_bp.route('/register', methods=['POST'])
def register():
    """User registration"""
    try:
        data = request.get_json()
        logger.info(f"Received registration data: {data}")  # Log data yang diterima
        
        if not data or not data.get('v_email') or not data.get('v_username') or not data.get('v_password_hash'):
            return jsonify({'error': 'Missing required fields'}), 400
        
        email = data['v_email'].strip().lower()
        username = data['v_username'].strip()
        password = data['v_password_hash'] # This is the raw password from frontend
        
        # Validate email format
        email_pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
        if not re.match(email_pattern, email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        # Validate password length
        if len(password) < 6:
            return jsonify({'error': 'Password must be at least 6 characters'}), 400
        
        # Hash password
        password_hash = generate_password_hash(password)
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        # Check if user already exists
        cur.execute(
            "SELECT v_id_user FROM users WHERE v_email = %s OR v_username = %s",
            (email, username)
        )
        
        if cur.fetchone():
            return jsonify({'error': 'User already exists'}), 409
        
        try:
            # Insert new user with t_tanggal_bikin defaulting to CURRENT_TIMESTAMP
            cur.execute(
                """
                INSERT INTO users (v_username, v_email, v_password_hash, f_is_admin) 
                VALUES (%s, %s, %s, %s) RETURNING v_id_user
                """,
                (username, email, password_hash, False)
            )
            
            user_id = cur.fetchone()[0]
            conn.commit()
            
            logger.info(f"New user registered: {username} (ID: {user_id})")
            
            return jsonify({
                'message': 'User registered successfully',
                'user_id': user_id,
                'success': True
            }), 201
            
        except psycopg2.Error as e:
            conn.rollback()
            logger.error(f"Database error during registration: {e}")
            return jsonify({'error': f'Database error: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@auth_bp.route('/login', methods=['POST'])
def login():
    """User login"""
    try:
        data = request.get_json()
        
        if not data or not data.get('v_email') or not data.get('v_password_hash'):
            return jsonify({'error': 'Missing email or password'}), 400
        
        email = data['v_email'].strip().lower()
        password = data['v_password_hash'] # This is the raw password from frontend
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor()
        
        # Get user
        cur.execute(
            "SELECT v_id_user, v_username, v_password_hash FROM users WHERE v_email = %s",
            (email,)
        )
        
        user = cur.fetchone()
        
        if not user or not check_password_hash(user[2], password):
            return jsonify({'error': 'Invalid credentials', 'success': False}), 401
        
        # Generate JWT token
        token_payload = {
            'user_id': user[0],
            'username': user[1],
            'exp': datetime.utcnow() + timedelta(hours=24)
        }
        
        token = jwt.encode(token_payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')
        
        logger.info(f"User logged in: {user[1]} (ID: {user[0]})")
        
        return jsonify({
            'message': 'Login successful',
            'token': token,
            'user': {
                'id': user[0],
                'username': user[1]
            },
            'success': True
        }), 200
        
    except Exception as e:
        logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed', 'success': False}), 500
    finally:
        if 'conn' in locals():
            conn.close()