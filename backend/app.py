from flask import Flask, request, jsonify, session, make_response
from io import BytesIO
import pandas as pd
from flask_cors import CORS
from flask_socketio import SocketIO, emit
from werkzeug.security import generate_password_hash, check_password_hash
from urllib.parse import unquote
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta
import jwt
import os
import subprocess
import sys
import importlib.util
import logging
from functools import wraps
import json
import re
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Konfigurasi dasar
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-change-this')

# ===================================
# CORS Configuration (SIMPLIFIED - FIXED)
# ===================================
# Gunakan CORS() saja, hapus @app.after_request untuk menghindari duplikasi
CORS(app, 
     resources={
         r"/*": {
             "origins": ["http://localhost:5173"],
             "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
             "allow_headers": ["Content-Type", "Authorization"],
             "supports_credentials": True
         }
     })

# Middleware untuk response headers
# @app.after_request
# def after_request(response):
#     response.headers.add('Access-Control-Allow-Origin', 'http://localhost:5173')
#     response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
#     response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
#     response.headers.add('Access-Control-Allow-Credentials', 'true')
#     return response

#  Konfigurasi SocketIO
socketio = SocketIO(app,
    cors_allowed_origins=["http://localhost:5173"],
    async_mode='threading')

# Database configuration
DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'ProDSGabungan'),
    'user': os.environ.get('DB_USER', 'postgres'),
    'password': os.environ.get('DB_PASSWORD', 'password123'),
    'host': os.environ.get('DB_HOST', 'localhost'),
    'port': os.environ.get('DB_PORT', '5432')
}
app.config['DB_CONFIG'] = DB_CONFIG

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def get_db_connection():
    """Get database connection"""
    try:
        # Add connection timeout to prevent hanging
        conn = psycopg2.connect(
            **DB_CONFIG,
            connect_timeout=10  # 10 seconds timeout
        )
        return conn
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection error (operational): {e}")
        return None
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        return None

def token_required(f):
    """JWT token decorator"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        if not token:
            return jsonify({'message': 'Token is missing'}), 401
        
        try:
            if token.startswith('Bearer '):
                token = token[7:]
            data = jwt.decode(token, app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            current_user_id = data['user_id']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': 'Token is invalid'}), 401
        
        return f(current_user_id, *args, **kwargs)
    return decorated

# Import and register blueprints
from routes.auth import auth_bp
from routes.scraping_routes import scraping_bp

app.register_blueprint(auth_bp, url_prefix='/auth')
app.register_blueprint(scraping_bp, url_prefix='')


# SocketIO event handlers
@socketio.on('connect')
def handle_connect():
    logger.info('Client connected')
    emit('connection_response', {'status': 'connected'})

@socketio.on('disconnect')
def handle_disconnect():
    logger.info('Client disconnected')

# Helper function to count SQL placeholders correctly (excluding %% escaped percents)
def count_sql_placeholders(query):
    """
    Count %s placeholders in SQL query, excluding those that are part of %% (escaped %)
    Example: 'LIKE %%sinta%%' should not count the %s in the middle
    """
    # Count %s that are not part of %% (escaped %)
    # Pattern: match %s that is not preceded by % and not followed by %
    return len(re.findall(r'(?<!%)%s(?!%)', query))

# Dashboard faculty-department mapping (must match across all dashboard functions)
DASHBOARD_FACULTY_DEPARTMENT_MAPPING = {
    'Fakultas Ekonomi': [
        'Ekonomi Pembangunan',
        'Ilmu Ekonomi',
        'Manajemen',
        'Akuntansi'
    ],
    'Fakultas Hukum': [
        'Ilmu Hukum',
        'Hukum'
    ],
    'Fakultas Ilmu Sosial dan Ilmu Politik': [
        'Administrasi Publik',
        'Administrasi Bisnis',
        'Hubungan Internasional',
        'Ilmu Administrasi Publik',
        'Ilmu Administrasi Bisnis',
        'Ilmu Hubungan Internasional'
    ],
    'Fakultas Teknik': [
        'Teknik Sipil',
        'Arsitektur',
        'Doktor Arsitektur',
        'Teknik Industri',
        'Teknik Kimia',
        'Teknik Mekatronika'
    ],
    'Fakultas Filsafat': [
        'Filsafat',
        'Ilmu Filsafat',
        'Studi Humanitas'
    ],
    'Fakultas Teknologi Informasi dan Sains': [
        'Matematika',
        'Fisika',
        'Informatika',
        'Teknik Informatika',
        'Ilmu Komputer'
    ],
    'Fakultas Kedokteran': [
        'Kedokteran',
        'Pendidikan Dokter'
    ],
    'Fakultas Keguruan dan Ilmu Pendidikan': [
        'Pendidikan Kimia',
        'Pendidikan Fisika',
        'Pendidikan Matematika',
        'Pendidikan Teknik Informatika dan Komputer',
        'Pendidikan Bahasa Inggris',
        'Pendidikan Guru Sekolah Dasar',
        'PGSD'
    ],
    'Fakultas Vokasi': [
        'Teknologi Rekayasa Pangan',
        'Bisnis Kreatif',
        'Agribisnis Pangan'
    ]
}

# Dashboard Routes
@app.route('/api/dashboard/stats', methods=['GET'])
@token_required
def dashboard_stats(current_user_id):
    """Get dashboard statistics with faculty/department filter - from latest data per dosen and publikasi"""
    try:
        # Support multiple values (comma-separated) for checkbox filters
        # URL decode to handle spaces and special characters (e.g., "Fakultas+Ilmu+Sosial+dan+Ilmu+Politik")
        faculty_param = unquote(request.args.get('faculty', '')).strip()
        department_param = unquote(request.args.get('department', '')).strip()
        
        # Parse comma-separated values into lists
        selected_faculties = [unquote(f.strip()) for f in faculty_param.split(',') if f.strip()] if faculty_param else []
        selected_departments = [unquote(d.strip()) for d in department_param.split(',') if d.strip()] if department_param else []
        
        print(f"📊 Dashboard Stats - Raw faculty param: {request.args.get('faculty', '')}")
        print(f"📊 Dashboard Stats - Decoded faculty param: {faculty_param}")
        print(f"📊 Dashboard Stats - faculties: {selected_faculties}, departments: {selected_departments}")
        print(f"📊 Has filter: {bool(selected_departments or selected_faculties)}")
        
        # Use the global mapping defined above
        FACULTY_DEPARTMENT_MAPPING = DASHBOARD_FACULTY_DEPARTMENT_MAPPING
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get latest and previous scraping dates
        cur.execute("""
            SELECT DISTINCT DATE(t_tanggal_unduh) as tanggal
            FROM tmp_dosen_dt
            WHERE t_tanggal_unduh IS NOT NULL
            UNION
            SELECT DISTINCT DATE(t_tanggal_unduh) as tanggal
            FROM stg_publikasi_tr
            WHERE t_tanggal_unduh IS NOT NULL
            ORDER BY tanggal DESC
            LIMIT 2
        """)
        dates = cur.fetchall()
        latest_date = dates[0]['tanggal'] if dates and len(dates) > 0 else None
        previous_date = dates[1]['tanggal'] if dates and len(dates) > 1 else None
        
        print(f"📅 Latest: {latest_date}, Previous: {previous_date}")
        
        # Build faculty/department filter - support multiple selections
        faculty_filter = ""
        faculty_params = []
        has_filter = bool(selected_departments or selected_faculties)

        if selected_departments:
            # Multiple departments selected - use LIKE for flexible matching
            dept_conditions = []
            for dept in selected_departments:
                dept_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE %s")
                faculty_params.append(f"%{dept.lower()}%")
            if dept_conditions:
                faculty_filter = f"AND ({' OR '.join(dept_conditions)})"
                print(f"🔍 Department filter: {faculty_filter}")
                print(f"🔍 Department params: {faculty_params}")
        elif selected_faculties:
            # Multiple faculties selected - collect all departments from selected faculties
            all_departments = []
            print(f"🔍 Available faculties in mapping: {list(DASHBOARD_FACULTY_DEPARTMENT_MAPPING.keys())}")
            for faculty in selected_faculties:
                print(f"🔍 Looking up faculty: '{faculty}'")
                print(f"🔍 Faculty in mapping: {faculty in DASHBOARD_FACULTY_DEPARTMENT_MAPPING}")
                departments_in_faculty = DASHBOARD_FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
                if not departments_in_faculty:
                    print(f"⚠️ Warning: No departments found for faculty: '{faculty}'")
                    print(f"⚠️ Available faculties: {list(DASHBOARD_FACULTY_DEPARTMENT_MAPPING.keys())}")
                else:
                    print(f"✅ Found {len(departments_in_faculty)} departments for '{faculty}': {departments_in_faculty}")
                all_departments.extend(departments_in_faculty)
            
            # Remove duplicates while preserving order
            unique_departments = []
            seen = set()
            for dept in all_departments:
                if dept.lower() not in seen:
                    unique_departments.append(dept)
                    seen.add(dept.lower())
            
            if unique_departments:
                like_conditions = []
                for dept in unique_departments:
                    # Use LIKE for flexible matching (handles variations in department names)
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE %s")
                    faculty_params.append(f"%{dept.lower()}%")
                faculty_filter = f"AND ({' OR '.join(like_conditions)})"
                print(f"🔍 Faculty filter (multiple): {faculty_filter}")
                print(f"🔍 Faculty params: {faculty_params}")
                print(f"🔍 Total params: {len(faculty_params)}")
            else:
                print(f"⚠️ Warning: No unique departments found for selected faculties: {selected_faculties}")
                print(f"⚠️ Filter will not be applied - returning all data")
                has_filter = False
                faculty_filter = ""
                faculty_params = []
        
        # Ensure has_filter matches actual filter state
        if not faculty_filter:
            has_filter = False
            faculty_params = []

        ORIGINAL_FACULTY_PARAMS = tuple(faculty_params) if faculty_params else tuple()
        print(f"🔍 ORIGINAL_FACULTY_PARAMS: {ORIGINAL_FACULTY_PARAMS}")
        print(f"🔍 Has filter: {has_filter}, Faculty filter: {faculty_filter}")
        print(f"🔍 Will filter data by: {'Departments' if selected_departments else 'Faculties' if selected_faculties else 'None'}")
        print(f"🔍 Selected Faculties: {selected_faculties}")
        print(f"🔍 Selected Departments: {selected_departments}")
        print(f"🔍 Filter will be applied to ALL queries: total_dosen, total_publikasi, sitasi, h-index, breakdowns, top authors, top dosen, publikasi_by_year")
        
        # Debug: Test query to see actual department names in database and test filter
        if has_filter and selected_faculties:
            # Show all departments in database
            test_query = """
                SELECT DISTINCT dm.v_nama_homebase_unpar
                FROM tmp_dosen_dt d
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                ORDER BY dm.v_nama_homebase_unpar
                LIMIT 50
            """
            cur.execute(test_query)
            test_results = cur.fetchall()
            print(f"🔍 [DEBUG] Sample department names in database:")
            for row in test_results[:20]:  # Show first 20
                print(f"   - {row['v_nama_homebase_unpar']}")
            
            # Test filter with actual query
            if faculty_filter:
                test_filter_query = f"""
                    SELECT COUNT(DISTINCT d.v_id_dosen) as count, 
                           STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar) as departments
                    FROM tmp_dosen_dt d
                    INNER JOIN datamaster dm ON (
                        (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                        OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                    )
                    WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                        AND TRIM(dm.v_nama_homebase_unpar) != '' {faculty_filter}
                """
                print(f"🔍 [DEBUG] Testing filter query...")
                print(f"🔍 [DEBUG] Filter query: {test_filter_query}")
                print(f"🔍 [DEBUG] Filter params: {list(ORIGINAL_FACULTY_PARAMS)}")
                
                # Validate parameter count
                placeholder_count = test_filter_query.count('%s')
                params_list = list(ORIGINAL_FACULTY_PARAMS)
                if placeholder_count != len(params_list):
                    print(f"⚠️ [TEST FILTER] Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
                    print(f"⚠️ [TEST FILTER] Skipping test filter query")
                else:
                    try:
                        cur.execute(test_filter_query, params_list)
                        test_filter_result = cur.fetchone()
                        print(f"🔍 [DEBUG] Filter test result: {test_filter_result['count']} dosen found")
                        print(f"🔍 [DEBUG] Matching departments: {test_filter_result['departments']}")
                    except Exception as test_error:
                        print(f"⚠️ [TEST FILTER] Error executing test filter query: {test_error}")
                        import traceback
                        print(f"⚠️ [TEST FILTER] Traceback: {traceback.format_exc()}")
        
        # CTE for latest dosen (GS and SINTA combined)
        latest_dosen_all_cte = """
            WITH latest_dosen_all AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # CTE for latest dosen (only GS)
        latest_dosen_gs_cte = """
            WITH latest_dosen_gs AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                WHERE (d.v_sumber = 'Google Scholar' OR d.v_id_googleScholar IS NOT NULL)
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # CTE for latest publikasi
        latest_publikasi_cte = """
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # Get total dosen (with faculty filter)
        if faculty_filter:
            try:
                query = f"""
                    {latest_dosen_all_cte}
                    SELECT COUNT(DISTINCT d.v_id_dosen) as total
                    FROM latest_dosen_all d
                    INNER JOIN datamaster dm ON (
                        (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                        OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                    )
                    WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                        AND TRIM(dm.v_nama_homebase_unpar) != '' {faculty_filter}
                """
                print(f"🔍 [DEBUG] Total Dosen Query: {query}")
                print(f"🔍 [DEBUG] Total Dosen Params: {list(ORIGINAL_FACULTY_PARAMS)}")
                
                # Validate parameter count
                placeholder_count = query.count('%s')
                params_list = list(ORIGINAL_FACULTY_PARAMS)
                if placeholder_count != len(params_list):
                    raise ValueError(f"Total Dosen: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
                
                cur.execute(query, params_list)
            except Exception as e:
                print(f"❌ Error in Total Dosen query: {e}")
                import traceback
                print(f"❌ Traceback: {traceback.format_exc()}")
                raise
        else:
            cur.execute(f"{latest_dosen_all_cte} SELECT COUNT(*) as total FROM latest_dosen_all")
        
        total_dosen = cur.fetchone()['total']
        
        # Get total publikasi (with faculty filter)
        if faculty_filter:
            query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as total
                FROM latest_publikasi p
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != '' {faculty_filter}
            """
            print(f"🔍 [DEBUG] Total Publikasi Query: {query}")
            print(f"🔍 [DEBUG] Total Publikasi Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Total Publikasi: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
        else:
            cur.execute(f"{latest_publikasi_cte} SELECT COUNT(*) as total FROM latest_publikasi")
        
        total_publikasi = cur.fetchone()['total']
        
        # Get sitasi stats (with faculty filter)
        if faculty_filter:
            # GS sitasi
            query = f"""
                {latest_dosen_gs_cte}
                SELECT COALESCE(SUM(d.n_total_sitasi_gs), 0) as total
                FROM latest_dosen_gs d
                INNER JOIN datamaster dm ON d.v_id_googlescholar IS NOT NULL 
                    AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs)
                WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != '' {faculty_filter}
            """
            print(f"🔍 [DEBUG] GS Sitasi Query: {query}")
            print(f"🔍 [DEBUG] GS Sitasi Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"GS Sitasi: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
            total_sitasi_gs = int(cur.fetchone()['total'])
            
            # GS-SINTA and Scopus sitasi
            query = f"""
                {latest_dosen_all_cte}
                SELECT 
                    COALESCE(SUM(d.n_sitasi_gs), 0) as gs_sinta,
                    COALESCE(SUM(d.n_sitasi_scopus), 0) as scopus
                FROM latest_dosen_all d
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != '' {faculty_filter}
            """
            print(f"🔍 [DEBUG] GS-SINTA & Scopus Sitasi Query: {query}")
            print(f"🔍 [DEBUG] GS-SINTA & Scopus Sitasi Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"GS-SINTA & Scopus Sitasi: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
            result = cur.fetchone()
            total_sitasi_gs_sinta = int(result['gs_sinta'])
            total_sitasi_scopus = int(result['scopus'])
        else:
            cur.execute(f"""
                {latest_dosen_gs_cte}
                SELECT COALESCE(SUM(n_total_sitasi_gs), 0) as total FROM latest_dosen_gs
            """)
            total_sitasi_gs = int(cur.fetchone()['total'])
            
            cur.execute(f"""
                {latest_dosen_all_cte}
                SELECT 
                    COALESCE(SUM(n_sitasi_gs), 0) as gs_sinta,
                    COALESCE(SUM(n_sitasi_scopus), 0) as scopus
                FROM latest_dosen_all
            """)
            result = cur.fetchone()
            total_sitasi_gs_sinta = int(result['gs_sinta'])
            total_sitasi_scopus = int(result['scopus'])
        
        total_sitasi = total_sitasi_gs + total_sitasi_gs_sinta + total_sitasi_scopus
        
        # Get h-index stats (with faculty filter)
        if faculty_filter:
            query = f"""
                {latest_dosen_all_cte}
                SELECT
                    COALESCE(AVG(d.n_h_index_gs), 0) as avg_h,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.n_h_index_gs), 0) as median_h
                FROM latest_dosen_all d
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != '' {faculty_filter}
            """
            print(f"🔍 [DEBUG] H-Index Query: {query}")
            print(f"🔍 [DEBUG] H-Index Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"H-Index: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
        else:
            cur.execute(f"""
                {latest_dosen_all_cte}
                SELECT
                    COALESCE(AVG(n_h_index_gs), 0) as avg_h,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n_h_index_gs), 0) as median_h
                FROM latest_dosen_all
            """)
        
        h_stats = cur.fetchone()
        avg_h_index = h_stats['avg_h']
        median_h_index = h_stats['median_h']
        
        # ===================================
        # PUBLIKASI BY YEAR
        # ===================================

        # Get publikasi by year (with faculty filter) - grouped by faculty
        current_year = datetime.now().year
        start_year = current_year - 15

        # Get publikasi by year (with faculty filter) - separated by source (SINTA vs Google Scholar)
        publikasi_by_year = []
        try:
            if faculty_filter:
                # ✅ DENGAN FILTER: Data per tahun dipisahkan per sumber (SINTA vs Google Scholar)
                # Note: Use %% to escape % in f-string for ILIKE patterns, and use .format() for faculty_filter
                query = f"""
                    WITH latest_publikasi AS (
                        SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                            p.*
                        FROM stg_publikasi_tr p
                        ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
                    ),
                    year_range AS (
                        SELECT generate_series(%s, %s) as year_num
                    ),
                    filtered_publikasi AS (
                        SELECT DISTINCT p.v_id_publikasi, p.v_tahun_publikasi, p.v_sumber
                        FROM latest_publikasi p
                        INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                        INNER JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL
                            AND TRIM(dm.v_nama_homebase_unpar) != ''
                            AND d.v_nama_dosen IS NOT NULL {faculty_filter}
                    )
                    SELECT 
                        yr.year_num::TEXT as v_tahun_publikasi,
                        COALESCE(COUNT(DISTINCT CASE 
                            WHEN (fp.v_sumber ILIKE '%%SINTA%%' OR fp.v_sumber ILIKE '%%Sinta%%' OR fp.v_sumber IS NULL OR fp.v_sumber = '')
                            THEN fp.v_id_publikasi 
                        END), 0) as count_sinta,
                        COALESCE(COUNT(DISTINCT CASE 
                            WHEN (fp.v_sumber ILIKE '%%Scholar%%' OR fp.v_sumber ILIKE '%%Google Scholar%%' OR fp.v_sumber ILIKE '%%GoogleScholar%%')
                            THEN fp.v_id_publikasi 
                        END), 0) as count_gs
                    FROM year_range yr
                    LEFT JOIN filtered_publikasi fp ON CAST(fp.v_tahun_publikasi AS TEXT) = CAST(yr.year_num AS TEXT)
                    GROUP BY yr.year_num
                    ORDER BY yr.year_num
                """
                query_params = [start_year, current_year] + list(ORIGINAL_FACULTY_PARAMS)
                
                print(f"🔍 [DEBUG] Publikasi by Year Query (with filter): {query}")
                print(f"🔍 Query has {query.count('%s')} placeholders")
                print(f"🔍 Params has {len(query_params)} values: {query_params}")
                
                # Validate parameter count
                placeholder_count = query.count('%s')
                if placeholder_count != len(query_params):
                    raise ValueError(f"Parameter count mismatch: query has {placeholder_count} placeholders but {len(query_params)} params provided")
                
                cur.execute(query, query_params)
                publikasi_by_year = [dict(row) for row in cur.fetchall()]
            else:
                # ✅ TANPA FILTER: Data per tahun dipisahkan per sumber (SINTA vs Google Scholar)
                # Note: Use %% to escape % in f-string for ILIKE patterns
                query = """
                    WITH latest_publikasi AS (
                        SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                            p.*
                        FROM stg_publikasi_tr p
                        ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
                    ),
                    year_range AS (
                        SELECT generate_series(%s, %s) as year_num
                    )
                    SELECT 
                        yr.year_num::TEXT as v_tahun_publikasi,
                        COALESCE(COUNT(DISTINCT CASE 
                            WHEN (p.v_sumber ILIKE '%%SINTA%%' OR p.v_sumber ILIKE '%%Sinta%%' OR p.v_sumber IS NULL OR p.v_sumber = '')
                            THEN p.v_id_publikasi 
                        END), 0) as count_sinta,
                        COALESCE(COUNT(DISTINCT CASE 
                            WHEN (p.v_sumber ILIKE '%%Scholar%%' OR p.v_sumber ILIKE '%%Google Scholar%%' OR p.v_sumber ILIKE '%%GoogleScholar%%')
                            THEN p.v_id_publikasi 
                        END), 0) as count_gs
                    FROM year_range yr
                    LEFT JOIN latest_publikasi p ON CAST(p.v_tahun_publikasi AS TEXT) = CAST(yr.year_num AS TEXT)
                    GROUP BY yr.year_num
                    ORDER BY yr.year_num
                """
                
                print(f"🔍 [DEBUG] Publikasi by Year Query (no filter): {query}")
                print(f"🔍 Query has {query.count('%s')} placeholders")
                print(f"🔍 Params: start_year={start_year}, current_year={current_year}")
                
                cur.execute(query, (start_year, current_year))
                publikasi_by_year = [dict(row) for row in cur.fetchall()]
            
            print(f"✅ publikasi_by_year fetched: {len(publikasi_by_year)} rows")
            if len(publikasi_by_year) > 0:
                print(f"📊 Sample data: {publikasi_by_year[0]}")
        except Exception as e:
            print(f"❌ Error executing publikasi by year query: {e}")
            import traceback
            error_details = traceback.format_exc()
            print(f"❌ Traceback: {error_details}")
            # Set empty list on error instead of raising
            publikasi_by_year = []
            print(f"⚠️ Using empty publikasi_by_year due to error")
        
        # Get top authors (with faculty filter)
        if faculty_filter:
            # Top Scopus
            query = f"""
                {latest_dosen_all_cte}
                SELECT d.v_nama_dosen, COALESCE(d.n_h_index_scopus, 0) as n_h_index_scopus
                FROM latest_dosen_all d
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND COALESCE(d.n_h_index_scopus, 0) > 0 {faculty_filter}
                ORDER BY n_h_index_scopus DESC LIMIT 10
            """
            print(f"🔍 [DEBUG] Top Scopus Query: {query}")
            print(f"🔍 [DEBUG] Top Scopus Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Top Scopus: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
            top_authors_scopus = [dict(row) for row in cur.fetchall()]
            
            # ✅ Top GS - PERBAIKAN: Gabungkan n_h_index_gs dan n_h_index_gs_sinta
            query = f"""
                {latest_dosen_all_cte}
                SELECT 
                    d.v_nama_dosen, 
                    GREATEST(
                        COALESCE(d.n_h_index_gs, 0),
                        COALESCE(d.n_h_index_gs_sinta, 0)
                    ) as n_h_index_gs
                FROM latest_dosen_all d
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != '' {faculty_filter}
                ORDER BY n_h_index_gs DESC 
                LIMIT 10
            """
            print(f"🔍 [DEBUG] Top GS Query: {query}")
            print(f"🔍 [DEBUG] Top GS Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Top GS: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
            top_authors_gs = [dict(row) for row in cur.fetchall()]
        else:
            # ✅ Top Scopus - Tanpa filter
            cur.execute(f"""
                {latest_dosen_all_cte}
                SELECT v_nama_dosen, COALESCE(n_h_index_scopus, 0) as n_h_index_scopus
                FROM latest_dosen_all
                WHERE COALESCE(n_h_index_scopus, 0) > 0
                ORDER BY n_h_index_scopus DESC LIMIT 10
            """)
            top_authors_scopus = [dict(row) for row in cur.fetchall()]
            
            # ✅ Top GS - PERBAIKAN: Gabungkan n_h_index_gs dan n_h_index_gs_sinta
            cur.execute(f"""
                {latest_dosen_all_cte}
                SELECT 
                    v_nama_dosen, 
                    GREATEST(
                        COALESCE(n_h_index_gs, 0),
                        COALESCE(n_h_index_gs_sinta, 0)
                    ) as n_h_index_gs
                FROM latest_dosen_all
                ORDER BY n_h_index_gs DESC 
                LIMIT 10
            """)
            top_authors_gs = [dict(row) for row in cur.fetchall()]
        
        # ===================================
        # SCOPUS Q BREAKDOWN & SINTA BREAKDOWN
        # Menggunakan relasi ID dan v_homebase_unpar dari datamaster
        # ===================================

        if has_filter:
            # ✅ DENGAN FILTER: Simple aggregation (tidak digrupkan per fakultas)
            query = f"""
                {latest_publikasi_cte}
                SELECT
                    CASE
                        WHEN COALESCE(a.v_ranking,'') IN ('Q1','Q2','Q3','Q4') THEN a.v_ranking
                        ELSE 'noQ'
                    END AS ranking,
                    COUNT(DISTINCT p.v_id_publikasi) AS count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                    AND dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND d.v_nama_dosen IS NOT NULL {faculty_filter}
                GROUP BY 1
                ORDER BY 1
            """
            print(f"🔍 [DEBUG] Scopus Q Breakdown Query: {query}")
            print(f"🔍 [DEBUG] Scopus Q Breakdown Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Scopus Q Breakdown: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
            scopus_q_breakdown = [dict(row) for row in cur.fetchall()]
            
            query = f"""
                {latest_publikasi_cte}
                SELECT
                    CASE
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 1' THEN 'Sinta 1'
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 2' THEN 'Sinta 2'
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 3' THEN 'Sinta 3'
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 4' THEN 'Sinta 4'
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 5' THEN 'Sinta 5'
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 6' THEN 'Sinta 6'
                        ELSE 'Other'
                    END AS ranking,
                    COUNT(DISTINCT p.v_id_publikasi) AS count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND d.v_nama_dosen IS NOT NULL
                    AND LOWER(COALESCE(a.v_terindeks, '')) LIKE '%%sinta%%'
                    {faculty_filter}
                GROUP BY 1
                ORDER BY 1
            """
            print(f"🔍 [DEBUG] Sinta Rank Breakdown Query: {query}")
            print(f"🔍 [DEBUG] Sinta Rank Breakdown Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count - use helper function to count only standalone %s, not %%s
            placeholder_count = count_sql_placeholders(query)
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                # Also try simple count for comparison
                simple_count = query.count('%s')
                print(f"⚠️ [Sinta Rank] Regex count: {placeholder_count}, Simple count: {simple_count}, Params: {len(params_list)}")
                print(f"⚠️ [Sinta Rank] Query snippet with LIKE: {query[query.find('LIKE'):query.find('LIKE')+50] if 'LIKE' in query else 'N/A'}")
                raise ValueError(f"Sinta Rank Breakdown: Parameter count mismatch: query has {placeholder_count} placeholders (corrected) / {simple_count} (simple) but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
            sinta_rank_breakdown = [dict(row) for row in cur.fetchall()]
            
        else:
            # ✅ TANPA FILTER: Grouped by faculty (stacked)
            query = f"""
                {latest_publikasi_cte}
                SELECT
                    CASE
                        WHEN COALESCE(a.v_ranking,'') IN ('Q1','Q2','Q3','Q4') THEN a.v_ranking
                        ELSE 'noQ'
                    END AS ranking,
                    COALESCE(dm_faculty.faculty_name, 'Lainnya') as faculty,
                    COUNT(DISTINCT p.v_id_publikasi) AS count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                LEFT JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                LEFT JOIN LATERAL (
                    SELECT CASE
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%ekonomi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%manajemen%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%akuntansi%%' THEN 'Fakultas Ekonomi'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%hukum%%' THEN 'Fakultas Hukum'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%teknik%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%sipil%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%arsitektur%%' THEN 'Fakultas Teknik'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%matematika%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%fisika%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%informatika%%' THEN 'Fakultas Teknologi Informasi dan Sains'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%filsafat%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%humanitas%%' THEN 'Fakultas Filsafat'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%kedokteran%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%dokter%%' THEN 'Fakultas Kedokteran'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%pendidikan%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%pgsd%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%keguruan%%' THEN 'Fakultas Keguruan dan Ilmu Pendidikan'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%vokasi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%agribisnis%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%bisnis kreatif%%' THEN 'Fakultas Vokasi'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%administrasi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%hubungan internasional%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%ilmu sosial%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%politik%%' THEN 'Fakultas Ilmu Sosial dan Ilmu Politik'
                        ELSE 'Lainnya'
                    END as faculty_name
                ) dm_faculty ON TRUE
                WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND d.v_nama_dosen IS NOT NULL
                GROUP BY 1, 2
                ORDER BY 1, 2
            """
            cur.execute(query)
            scopus_q_breakdown = [dict(row) for row in cur.fetchall()]
            
            query = f"""
                {latest_publikasi_cte}
                SELECT
                    CASE
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 1' THEN 'Sinta 1'
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 2' THEN 'Sinta 2'
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 3' THEN 'Sinta 3'
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 4' THEN 'Sinta 4'
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 5' THEN 'Sinta 5'
                        WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 6' THEN 'Sinta 6'
                        ELSE 'Other'
                    END AS ranking,
                    COALESCE(dm_faculty.faculty_name, 'Lainnya') as faculty,
                    COUNT(DISTINCT p.v_id_publikasi) AS count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                LEFT JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                LEFT JOIN LATERAL (
                    SELECT CASE
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%ekonomi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%manajemen%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%akuntansi%%' THEN 'Fakultas Ekonomi'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%hukum%%' THEN 'Fakultas Hukum'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%teknik%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%sipil%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%arsitektur%%' THEN 'Fakultas Teknik'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%matematika%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%fisika%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%informatika%%' THEN 'Fakultas Teknologi Informasi dan Sains'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%filsafat%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%humanitas%%' THEN 'Fakultas Filsafat'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%kedokteran%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%dokter%%' THEN 'Fakultas Kedokteran'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%pendidikan%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%pgsd%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%keguruan%%' THEN 'Fakultas Keguruan dan Ilmu Pendidikan'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%vokasi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%agribisnis%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%bisnis kreatif%%' THEN 'Fakultas Vokasi'
                        WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%administrasi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%hubungan internasional%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%ilmu sosial%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%politik%%' THEN 'Fakultas Ilmu Sosial dan Ilmu Politik'
                        ELSE 'Lainnya'
                    END as faculty_name
                ) dm_faculty ON TRUE
                WHERE dm.v_nama_homebase_unpar IS NOT NULL
                    AND d.v_nama_dosen IS NOT NULL
                    AND LOWER(COALESCE(a.v_terindeks, '')) LIKE '%sinta%'
                GROUP BY 1, 2
                ORDER BY 1, 2
            """
            cur.execute(query)
            sinta_rank_breakdown = [dict(row) for row in cur.fetchall()]
        
        # ===================================
        # COUNT PUBLIKASI BERDASARKAN KATEGORI (FIXED VERSION)
        # Menggunakan relasi ID dari stg_publikasi_dosen_dt
        # ===================================

        # Publikasi Internasional Q1-Q2
        if faculty_filter:
            query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                    AND UPPER(COALESCE(a.v_ranking, '')) IN ('Q1', 'Q2')
                    AND dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND d.v_nama_dosen IS NOT NULL {faculty_filter}
            """
            print(f"🔍 [DEBUG] Publikasi Q1-Q2 Query: {query}")
            print(f"🔍 [DEBUG] Publikasi Q1-Q2 Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Publikasi Q1-Q2: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
        else:
            cur.execute(f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                    AND UPPER(COALESCE(a.v_ranking, '')) IN ('Q1', 'Q2')
            """)
        publikasi_internasional_q12 = cur.fetchone()['count'] or 0

        # Publikasi Internasional Q3-Q4/noQ
        if faculty_filter:
            query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                    AND (UPPER(COALESCE(a.v_ranking, '')) IN ('Q3', 'Q4') OR COALESCE(a.v_ranking, '') = '')
                    AND dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND d.v_nama_dosen IS NOT NULL {faculty_filter}
            """
            print(f"🔍 [DEBUG] Publikasi Q3-Q4/noQ Query: {query}")
            print(f"🔍 [DEBUG] Publikasi Q3-Q4/noQ Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Publikasi Q3-Q4/noQ: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
        else:
            cur.execute(f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                    AND (UPPER(COALESCE(a.v_ranking, '')) IN ('Q3', 'Q4') OR COALESCE(a.v_ranking, '') = '')
            """)
        publikasi_internasional_q34_noq = cur.fetchone()['count'] or 0

        # Publikasi Nasional Sinta 1-2
        if faculty_filter:
            query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 1', 'sinta 2')
                    AND dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND d.v_nama_dosen IS NOT NULL {faculty_filter}
            """
            print(f"🔍 [DEBUG] Publikasi Sinta 1-2 Query: {query}")
            print(f"🔍 [DEBUG] Publikasi Sinta 1-2 Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Publikasi Sinta 1-2: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
        else:
            cur.execute(f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 1', 'sinta 2')
            """)
        publikasi_nasional_sinta12 = cur.fetchone()['count'] or 0

        # Publikasi Nasional Sinta 3-4
        if faculty_filter:
            query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 3', 'sinta 4')
                    AND dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND d.v_nama_dosen IS NOT NULL {faculty_filter}
            """
            print(f"🔍 [DEBUG] Publikasi Sinta 3-4 Query: {query}")
            print(f"🔍 [DEBUG] Publikasi Sinta 3-4 Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Publikasi Sinta 3-4: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
        else:
            cur.execute(f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 3', 'sinta 4')
            """)
        publikasi_nasional_sinta34 = cur.fetchone()['count'] or 0

        # Publikasi Nasional Sinta 5
        if faculty_filter:
            query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 5'
                    AND dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND d.v_nama_dosen IS NOT NULL {faculty_filter}
            """
            print(f"🔍 [DEBUG] Publikasi Sinta 5 Query: {query}")
            print(f"🔍 [DEBUG] Publikasi Sinta 5 Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Publikasi Sinta 5: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
        else:
            cur.execute(f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 5'
            """)
        publikasi_nasional_sinta5 = cur.fetchone()['count'] or 0

        # Publikasi Nasional Sinta 6
        if faculty_filter:
            query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 6'
                    AND dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND d.v_nama_dosen IS NOT NULL {faculty_filter}
            """
            print(f"🔍 [DEBUG] Publikasi Sinta 6 Query: {query}")
            print(f"🔍 [DEBUG] Publikasi Sinta 6 Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Publikasi Sinta 6: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
        else:
            cur.execute(f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 6'
            """)
        publikasi_nasional_sinta6 = cur.fetchone()['count'] or 0

        # ===================================
        # TOP DOSEN BERDASARKAN PUBLIKASI (FIXED VERSION)
        # ===================================

        # Top 10 Dosen Internasional (Scopus)
        if faculty_filter:
            query = f"""
                {latest_publikasi_cte}
                SELECT 
                    d.v_nama_dosen,
                    COUNT(DISTINCT pd.v_id_publikasi) as count_international
                FROM tmp_dosen_dt d
                INNER JOIN stg_publikasi_dosen_dt pd ON d.v_id_dosen = pd.v_id_dosen
                INNER JOIN latest_publikasi p ON pd.v_id_publikasi = p.v_id_publikasi
                INNER JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE (
                    LOWER(TRIM(COALESCE(a.v_terindeks, ''))) = 'scopus'
                    OR LOWER(TRIM(COALESCE(a.v_terindeks, ''))) LIKE 'scopus,%%'
                    OR LOWER(TRIM(COALESCE(a.v_terindeks, ''))) LIKE '%%,scopus,%%'
                    OR LOWER(TRIM(COALESCE(a.v_terindeks, ''))) LIKE '%%,scopus'
                )
                    AND d.v_nama_dosen IS NOT NULL
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != '' {faculty_filter}
                GROUP BY d.v_nama_dosen
                ORDER BY count_international DESC
                LIMIT 10
            """
            print(f"🔍 [DEBUG] Top Dosen International Query: {query}")
            print(f"🔍 [DEBUG] Top Dosen International Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            # ✅ PENTING: Buat list baru dari tuple
            params_for_query = list(ORIGINAL_FACULTY_PARAMS)
            
            # Debug
            print(f"🔍 [Top Dosen Int] Query placeholders: {query.count('%s')}")
            print(f"🔍 [Top Dosen Int] Params count: {len(params_for_query)}")
            
            print(f"🔍 [DEBUG] Query yang akan dieksekusi:")
            print(query)
            print(f"🔍 [DEBUG] Params: {params_for_query}")
            print(f"🔍 [DEBUG] Query length: {len(query)} chars")
            cur.execute(query, params_for_query)
        else:
            cur.execute(f"""
                {latest_publikasi_cte}
                SELECT 
                    d.v_nama_dosen,
                    COUNT(DISTINCT pd.v_id_publikasi) as count_international
                FROM tmp_dosen_dt d
                INNER JOIN stg_publikasi_dosen_dt pd ON d.v_id_dosen = pd.v_id_dosen
                INNER JOIN latest_publikasi p ON pd.v_id_publikasi = p.v_id_publikasi
                INNER JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE (
                    LOWER(TRIM(COALESCE(a.v_terindeks, ''))) = 'scopus'
                    OR LOWER(TRIM(COALESCE(a.v_terindeks, ''))) LIKE 'scopus,%%'
                    OR LOWER(TRIM(COALESCE(a.v_terindeks, ''))) LIKE '%%,scopus,%%'
                    OR LOWER(TRIM(COALESCE(a.v_terindeks, ''))) LIKE '%%,scopus'
                )
                    AND d.v_nama_dosen IS NOT NULL
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                GROUP BY d.v_nama_dosen
                ORDER BY count_international DESC
                LIMIT 10
            """)
        top_dosen_international = [dict(row) for row in cur.fetchall()]

        # Top 10 Dosen Nasional (Sinta 1-6)
        if faculty_filter:
            query = f"""
                {latest_publikasi_cte}
                SELECT 
                    d.v_nama_dosen,
                    COUNT(DISTINCT pd.v_id_publikasi) as count_national
                FROM tmp_dosen_dt d
                INNER JOIN stg_publikasi_dosen_dt pd ON d.v_id_dosen = pd.v_id_dosen
                INNER JOIN latest_publikasi p ON pd.v_id_publikasi = p.v_id_publikasi
                INNER JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE LOWER(TRIM(COALESCE(a.v_ranking, ''))) IN ('sinta 1', 'sinta 2', 'sinta 3', 'sinta 4', 'sinta 5', 'sinta 6')
                    AND d.v_nama_dosen IS NOT NULL
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != '' {faculty_filter}
                GROUP BY d.v_nama_dosen
                ORDER BY count_national DESC
                LIMIT 10
            """
            print(f"🔍 [DEBUG] Top Dosen National Query: {query}")
            print(f"🔍 [DEBUG] Top Dosen National Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            # ✅ PENTING: Buat list baru dari tuple
            params_for_query = list(ORIGINAL_FACULTY_PARAMS)
            
            # Debug
            print(f"🔍 [Top Dosen Nat] Query placeholders: {query.count('%s')}")
            print(f"🔍 [Top Dosen Nat] Params count: {len(params_for_query)}")
            
            cur.execute(query, params_for_query)
        else:
            cur.execute(f"""
                {latest_publikasi_cte}
                SELECT 
                    d.v_nama_dosen,
                    COUNT(DISTINCT pd.v_id_publikasi) as count_national
                FROM tmp_dosen_dt d
                INNER JOIN stg_publikasi_dosen_dt pd ON d.v_id_dosen = pd.v_id_dosen
                INNER JOIN latest_publikasi p ON pd.v_id_publikasi = p.v_id_publikasi
                INNER JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE LOWER(TRIM(COALESCE(a.v_ranking, ''))) IN ('sinta 1', 'sinta 2', 'sinta 3', 'sinta 4', 'sinta 5', 'sinta 6')
                    AND d.v_nama_dosen IS NOT NULL
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                GROUP BY d.v_nama_dosen
                ORDER BY count_national DESC
                LIMIT 10
            """)
        top_dosen_national = [dict(row) for row in cur.fetchall()]
        
        # ===================================
        # GET PREVIOUS VALUES
        # ===================================
        previous_values = {}
        if previous_date:
            # CTE for previous dosen (all sources)
            previous_dosen_all_cte = f"""
                WITH previous_dosen_all AS (
                    SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                        d.*
                    FROM tmp_dosen_dt d
                    WHERE DATE(d.t_tanggal_unduh) = %s
                    ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
                )
            """
            
            # CTE for previous dosen (only GS)
            previous_dosen_gs_cte = f"""
                WITH previous_dosen_gs AS (
                    SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                        d.*
                    FROM tmp_dosen_dt d
                    WHERE DATE(d.t_tanggal_unduh) = %s
                        AND (d.v_sumber = 'Google Scholar' OR d.v_id_googleScholar IS NOT NULL)
                    ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
                )
            """
            
            # CTE for previous publikasi
            previous_publikasi_cte = f"""
                WITH previous_publikasi AS (
                    SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                        p.*
                    FROM stg_publikasi_tr p
                    WHERE DATE(p.t_tanggal_unduh) = %s
                    ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
                )
            """
            
            try:
                # Get previous total dosen
                if faculty_filter:
                    query = f"""
                        {previous_dosen_all_cte}
                        SELECT COUNT(DISTINCT d.v_id_dosen) as total
                        FROM previous_dosen_all d
                        LEFT JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"{previous_dosen_all_cte} SELECT COUNT(*) as total FROM previous_dosen_all", [previous_date])
                prev_total_dosen = cur.fetchone()['total'] or 0
                
                # Get previous total publikasi
                if faculty_filter:
                    query = f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as total
                        FROM previous_publikasi p
                        CROSS JOIN LATERAL (
                            SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
                        ) authors
                        LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
                            AND DATE(d.t_tanggal_unduh) = %s
                        LEFT JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"{previous_publikasi_cte} SELECT COUNT(*) as total FROM previous_publikasi", [previous_date])
                prev_total_publikasi = cur.fetchone()['total'] or 0
                
                # Get previous sitasi stats
                if faculty_filter:
                    # GS sitasi
                    query = f"""
                        {previous_dosen_gs_cte}
                        SELECT COALESCE(SUM(d.n_total_sitasi_gs), 0) as total
                        FROM previous_dosen_gs d
                        LEFT JOIN datamaster dm ON d.v_id_googlescholar IS NOT NULL 
                            AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs)
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                    prev_total_sitasi_gs = int(cur.fetchone()['total'])
                    
                    # GS-SINTA and Scopus sitasi
                    query = f"""
                        {previous_dosen_all_cte}
                        SELECT 
                            COALESCE(SUM(d.n_sitasi_gs), 0) as gs_sinta,
                            COALESCE(SUM(d.n_sitasi_scopus), 0) as scopus
                        FROM previous_dosen_all d
                        LEFT JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                    result = cur.fetchone()
                    prev_total_sitasi_gs_sinta = int(result['gs_sinta'])
                    prev_total_sitasi_scopus = int(result['scopus'])
                else:
                    cur.execute(f"""
                        {previous_dosen_gs_cte}
                        SELECT COALESCE(SUM(n_total_sitasi_gs), 0) as total FROM previous_dosen_gs
                    """, [previous_date])
                    prev_total_sitasi_gs = int(cur.fetchone()['total'])
                    
                    cur.execute(f"""
                        {previous_dosen_all_cte}
                        SELECT 
                            COALESCE(SUM(n_sitasi_gs), 0) as gs_sinta,
                            COALESCE(SUM(n_sitasi_scopus), 0) as scopus
                        FROM previous_dosen_all
                    """, [previous_date])
                    result = cur.fetchone()
                    prev_total_sitasi_gs_sinta = int(result['gs_sinta'])
                    prev_total_sitasi_scopus = int(result['scopus'])
                
                prev_total_sitasi = prev_total_sitasi_gs + prev_total_sitasi_gs_sinta + prev_total_sitasi_scopus
                
                # Get previous h-index stats
                if faculty_filter:
                    query = f"""
                        {previous_dosen_all_cte}
                        SELECT
                            COALESCE(AVG(d.n_h_index_gs), 0) as avg_h,
                            COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.n_h_index_gs), 0) as median_h
                        FROM previous_dosen_all d
                        LEFT JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"""
                        {previous_dosen_all_cte}
                        SELECT
                            COALESCE(AVG(n_h_index_gs), 0) as avg_h,
                            COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n_h_index_gs), 0) as median_h
                        FROM previous_dosen_all
                    """, [previous_date])
                
                h_stats = cur.fetchone()
                prev_avg_h_index = float(h_stats['avg_h']) if h_stats['avg_h'] else 0.0
                prev_median_h_index = float(h_stats['median_h']) if h_stats['median_h'] else 0.0
                
                # Get previous publikasi internasional Q1-Q2
                if faculty_filter:
                    query = f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                            AND DATE(d.t_tanggal_unduh) = %s
                        INNER JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                            AND UPPER(COALESCE(a.v_ranking, '')) IN ('Q1', 'Q2')
                            AND dm.v_nama_homebase_unpar IS NOT NULL 
                            AND TRIM(dm.v_nama_homebase_unpar) != ''
                            AND d.v_nama_dosen IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                            AND UPPER(COALESCE(a.v_ranking, '')) IN ('Q1', 'Q2')
                    """, [previous_date])
                prev_publikasi_internasional_q12 = cur.fetchone()['count'] or 0
                
                # Get previous publikasi internasional Q3-Q4/noQ
                if faculty_filter:
                    query = f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                            AND DATE(d.t_tanggal_unduh) = %s
                        INNER JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                            AND (UPPER(COALESCE(a.v_ranking, '')) IN ('Q3', 'Q4') OR COALESCE(a.v_ranking, '') = '')
                            AND dm.v_nama_homebase_unpar IS NOT NULL 
                            AND TRIM(dm.v_nama_homebase_unpar) != ''
                            AND d.v_nama_dosen IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                            AND (UPPER(COALESCE(a.v_ranking, '')) IN ('Q3', 'Q4') OR COALESCE(a.v_ranking, '') = '')
                    """, [previous_date])
                prev_publikasi_internasional_q34_noq = cur.fetchone()['count'] or 0
                
                # Get previous publikasi nasional Sinta 1-2
                if faculty_filter:
                    query = f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                            AND DATE(d.t_tanggal_unduh) = %s
                        INNER JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 1', 'sinta 2')
                            AND dm.v_nama_homebase_unpar IS NOT NULL 
                            AND TRIM(dm.v_nama_homebase_unpar) != ''
                            AND d.v_nama_dosen IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 1', 'sinta 2')
                    """, [previous_date])
                prev_publikasi_nasional_sinta12 = cur.fetchone()['count'] or 0
                
                # Get previous publikasi nasional Sinta 3-4
                if faculty_filter:
                    query = f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                            AND DATE(d.t_tanggal_unduh) = %s
                        INNER JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 3', 'sinta 4')
                            AND dm.v_nama_homebase_unpar IS NOT NULL 
                            AND TRIM(dm.v_nama_homebase_unpar) != ''
                            AND d.v_nama_dosen IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 3', 'sinta 4')
                    """, [previous_date])
                prev_publikasi_nasional_sinta34 = cur.fetchone()['count'] or 0
                
                # Get previous publikasi nasional Sinta 5
                if faculty_filter:
                    query = f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                            AND DATE(d.t_tanggal_unduh) = %s
                        LEFT JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 5'
                            AND dm.v_nama_homebase_unpar IS NOT NULL 
                            AND TRIM(dm.v_nama_homebase_unpar) != ''
                            AND d.v_nama_dosen IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 5'
                    """, [previous_date])
                prev_publikasi_nasional_sinta5 = cur.fetchone()['count'] or 0
                
                # Get previous publikasi nasional Sinta 6
                if faculty_filter:
                    query = f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        INNER JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        INNER JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                            AND DATE(d.t_tanggal_unduh) = %s
                        INNER JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 6'
                            AND dm.v_nama_homebase_unpar IS NOT NULL 
                            AND TRIM(dm.v_nama_homebase_unpar) != ''
                            AND d.v_nama_dosen IS NOT NULL {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as count
                        FROM previous_publikasi p
                        LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                        WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 6'
                    """, [previous_date])
                prev_publikasi_nasional_sinta6 = cur.fetchone()['count'] or 0
                
                previous_values = {
                    'total_dosen': prev_total_dosen,
                    'total_publikasi': prev_total_publikasi,
                    'total_sitasi': prev_total_sitasi,
                    'total_sitasi_gs': prev_total_sitasi_gs,
                    'total_sitasi_gs_sinta': prev_total_sitasi_gs_sinta,
                    'total_sitasi_scopus': prev_total_sitasi_scopus,
                    'avg_h_index': prev_avg_h_index,
                    'median_h_index': prev_median_h_index,
                    'publikasi_internasional_q12': prev_publikasi_internasional_q12,
                    'publikasi_internasional_q34_noq': prev_publikasi_internasional_q34_noq,
                    'publikasi_nasional_sinta12': prev_publikasi_nasional_sinta12,
                    'publikasi_nasional_sinta34': prev_publikasi_nasional_sinta34,
                    'publikasi_nasional_sinta5': prev_publikasi_nasional_sinta5,
                    'publikasi_nasional_sinta6': prev_publikasi_nasional_sinta6
                }
                print(f"📊 Previous dashboard stats: {previous_values}")
            except Exception as e:
                import traceback
                error_details = traceback.format_exc()
                print(f"⚠️ Error fetching previous dashboard stats: {e}\n{error_details}")
                previous_values = {}
        
        return jsonify({
            'success': True,
            'data': {
                'total_dosen': total_dosen or 0,
                'total_publikasi': total_publikasi or 0,
                'total_sitasi': total_sitasi or 0,
                'total_sitasi_gs': total_sitasi_gs or 0,
                'total_sitasi_gs_sinta': total_sitasi_gs_sinta or 0,
                'total_sitasi_scopus': total_sitasi_scopus or 0,
                'avg_h_index': float(avg_h_index) if avg_h_index else 0.0,
                'median_h_index': float(median_h_index) if median_h_index else 0.0,
                'publikasi_by_year': publikasi_by_year or [],
                'top_authors_scopus': top_authors_scopus or [],
                'top_authors_gs': top_authors_gs or [],
                'publikasi_internasional_q12': publikasi_internasional_q12 or 0,
                'publikasi_internasional_q34_noq': publikasi_internasional_q34_noq or 0,
                'publikasi_nasional_sinta12': publikasi_nasional_sinta12 or 0,
                'publikasi_nasional_sinta34': publikasi_nasional_sinta34 or 0,
                'publikasi_nasional_sinta5': publikasi_nasional_sinta5 or 0,
                'publikasi_nasional_sinta6': publikasi_nasional_sinta6 or 0,
                'scopus_q_breakdown': scopus_q_breakdown or [],
                'sinta_rank_breakdown': sinta_rank_breakdown or [],
                'top_dosen_international': top_dosen_international or [],
                'top_dosen_national': top_dosen_national or [],
                'previous_date': previous_date.strftime('%d/%m/%Y') if previous_date else None,
                'previous_values': previous_values or {},
                'has_filter': has_filter  # ✅ TAMBAHKAN FLAG INI untuk frontend
            }
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Dashboard stats error:\n", error_details)
        logger.error(f"Dashboard stats error: {e}\n{error_details}")
        
        # Return more detailed error for debugging
        error_lines = error_details.split('\n') if error_details else []
        last_10_lines = error_lines[-10:] if len(error_lines) > 10 else error_lines
        
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to fetch dashboard stats',
            'details': last_10_lines,
            'error_type': type(e).__name__,
            'traceback': error_details
        }), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


@app.route('/api/dashboard/sinta-breakdown-per-fakultas', methods=['GET'])
@token_required
def get_sinta_breakdown_per_fakultas(current_user_id):
    """Get Sinta Breakdown (S1–S6) - Per Fakultas
    Filters: ranking Sinta 1-6 and Other, Terindeks SINTA or Garuda"""
    conn = None
    cur = None
    
    try:
        print(f"📊 Sinta Breakdown Per Fakultas - Authenticated user ID: {current_user_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # CTE for latest publikasi
        latest_publikasi_cte = """
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # Query to get Sinta breakdown per faculty
        # Filter: ranking Sinta 1-6 and Other, Terindeks SINTA or Garuda
        query = f"""
            {latest_publikasi_cte}
            SELECT
                COALESCE(dm_faculty.faculty_name, 'Lainnya') as faculty,
                CASE
                    WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 1' THEN 'Sinta 1'
                    WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 2' THEN 'Sinta 2'
                    WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 3' THEN 'Sinta 3'
                    WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 4' THEN 'Sinta 4'
                    WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 5' THEN 'Sinta 5'
                    WHEN LOWER(COALESCE(a.v_ranking,'')) = 'sinta 6' THEN 'Sinta 6'
                    ELSE 'Other'
                END AS ranking,
                COUNT(DISTINCT p.v_id_publikasi) AS count
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            CROSS JOIN LATERAL (
                SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
            ) authors
            LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
            LEFT JOIN datamaster dm ON (
                (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
            )
            LEFT JOIN LATERAL (
                SELECT CASE
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%ekonomi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%manajemen%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%akuntansi%%' THEN 'Fakultas Ekonomi'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%hukum%%' THEN 'Fakultas Hukum'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%teknik%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%sipil%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%arsitektur%%' THEN 'Fakultas Teknik'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%matematika%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%fisika%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%informatika%%' THEN 'Fakultas Teknologi Informasi dan Sains'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%filsafat%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%humanitas%%' THEN 'Fakultas Filsafat'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%kedokteran%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%dokter%%' THEN 'Fakultas Kedokteran'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%pendidikan%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%pgsd%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%keguruan%%' THEN 'Fakultas Keguruan dan Ilmu Pendidikan'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%vokasi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%agribisnis%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%bisnis kreatif%%' THEN 'Fakultas Vokasi'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%administrasi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%hubungan internasional%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%ilmu sosial%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%politik%%' THEN 'Fakultas Ilmu Sosial dan Ilmu Politik'
                    ELSE 'Lainnya'
                END as faculty_name
            ) dm_faculty ON TRUE
            WHERE dm.v_nama_homebase_unpar IS NOT NULL
                AND LOWER(COALESCE(a.v_terindeks, '')) LIKE '%sinta%'
                -- Ranking filter: Include Sinta 1-6 and Other (handled by CASE statement above)
            GROUP BY 1, 2
            ORDER BY 1, 2
        """
        
        cur.execute(query)
        results = [dict(row) for row in cur.fetchall()]
        
        print(f"✅ Sinta Breakdown Per Fakultas - Found {len(results)} records")
        
        return jsonify({
            'success': True,
            'data': results
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Sinta Breakdown Per Fakultas error:\n{error_details}")
        logger.error(f"Sinta Breakdown Per Fakultas error: {e}\n{error_details}")
        return jsonify({'success': False, 'error': 'Failed to fetch Sinta breakdown per fakultas'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


@app.route('/api/dashboard/scopus-breakdown-per-fakultas', methods=['GET'])
@token_required
def get_scopus_breakdown_per_fakultas(current_user_id):
    """Get Scopus Breakdown (Q) - Per Fakultas
    Filters: ranking Q1-Q4 and no-Q, Terindeks Scopus"""
    conn = None
    cur = None
    
    try:
        print(f"📊 Scopus Breakdown Per Fakultas - Authenticated user ID: {current_user_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # CTE for latest publikasi
        latest_publikasi_cte = """
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # Query to get Scopus breakdown per faculty
        # Filter: ranking Q1-Q4 and no-Q, Terindeks Scopus (mirip dengan Sinta Breakdown)
        query = f"""
            {latest_publikasi_cte}
            SELECT
                COALESCE(dm_faculty.faculty_name, 'Lainnya') as faculty,
                CASE
                    WHEN COALESCE(a.v_ranking, '') IN ('Q1', 'Q2', 'Q3', 'Q4') THEN a.v_ranking
                    ELSE 'noQ'
                END AS ranking,
                COUNT(DISTINCT p.v_id_publikasi) AS count
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            CROSS JOIN LATERAL (
                SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
            ) authors
            LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
            LEFT JOIN datamaster dm ON (
                (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
            )
            LEFT JOIN LATERAL (
                SELECT CASE
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%ekonomi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%manajemen%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%akuntansi%%' THEN 'Fakultas Ekonomi'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%hukum%%' THEN 'Fakultas Hukum'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%teknik%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%sipil%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%arsitektur%%' THEN 'Fakultas Teknik'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%matematika%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%fisika%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%informatika%%' THEN 'Fakultas Teknologi Informasi dan Sains'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%filsafat%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%humanitas%%' THEN 'Fakultas Filsafat'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%kedokteran%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%dokter%%' THEN 'Fakultas Kedokteran'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%pendidikan%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%pgsd%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%keguruan%%' THEN 'Fakultas Keguruan dan Ilmu Pendidikan'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%vokasi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%agribisnis%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%bisnis kreatif%%' THEN 'Fakultas Vokasi'
                    WHEN LOWER(dm.v_nama_homebase_unpar) LIKE '%%administrasi%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%hubungan internasional%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%ilmu sosial%%' OR LOWER(dm.v_nama_homebase_unpar) LIKE '%%politik%%' THEN 'Fakultas Ilmu Sosial dan Ilmu Politik'
                    ELSE 'Lainnya'
                END as faculty_name
            ) dm_faculty ON TRUE
            WHERE dm.v_nama_homebase_unpar IS NOT NULL
                AND (
                    -- Filter: Terindeks Scopus (case-insensitive, handle comma-separated values)
                    LOWER(COALESCE(a.v_terindeks, '')) LIKE '%%scopus%%'
                )
                -- Ranking filter: Include Q1-Q4 and no-Q (handled by CASE statement above)
            GROUP BY 1, 2
            ORDER BY 1, 2
        """
        
        cur.execute(query)
        results = [dict(row) for row in cur.fetchall()]
        
        print(f"✅ Scopus Breakdown Per Fakultas - Found {len(results)} records")
        
        return jsonify({
            'success': True,
            'data': results
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Scopus Breakdown Per Fakultas error:\n{error_details}")
        logger.error(f"Scopus Breakdown Per Fakultas error: {e}\n{error_details}")
        return jsonify({'success': False, 'error': 'Failed to fetch Scopus breakdown per fakultas'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


@app.route('/api/dashboard/top-dosen-international', methods=['GET'])
@token_required
def get_top_dosen_international(current_user_id):
    """Get Top 10 Dosen Berdasarkan Publikasi Internasional (Scopus)"""
    conn = None
    cur = None
    
    try:
        print(f"📊 Top Dosen International (Scopus) - Authenticated user ID: {current_user_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # CTE for latest publikasi
        latest_publikasi_cte = """
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # Query to get Top 10 Dosen based on Scopus publications
        query = f"""
            {latest_publikasi_cte}
            SELECT 
                d.v_nama_dosen,
                COUNT(DISTINCT p.v_id_publikasi) as count_international
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            CROSS JOIN LATERAL (
                SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
            ) authors
            LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
            LEFT JOIN datamaster dm ON (
                (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
            )
            WHERE LOWER(COALESCE(a.v_terindeks, '')) LIKE '%%scopus%%'
                AND d.v_nama_dosen IS NOT NULL
                AND dm.v_nama_homebase_unpar IS NOT NULL
            GROUP BY d.v_nama_dosen
            ORDER BY count_international DESC
            LIMIT 10
        """
        
        cur.execute(query)
        results = [dict(row) for row in cur.fetchall()]
        
        print(f"✅ Top Dosen International (Scopus) - Found {len(results)} records")
        
        return jsonify({
            'success': True,
            'data': results
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Top Dosen International error:\n{error_details}")
        logger.error(f"Top Dosen International error: {e}\n{error_details}")
        return jsonify({'success': False, 'error': 'Failed to fetch top dosen international'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


@app.route('/api/dashboard/top-dosen-national', methods=['GET'])
@token_required
def get_top_dosen_national(current_user_id):
    """Get Top 10 Dosen Berdasarkan Publikasi Nasional (Sinta 1-6)"""
    conn = None
    cur = None
    
    try:
        print(f"📊 Top Dosen National (Sinta 1-6) - Authenticated user ID: {current_user_id}")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # CTE for latest publikasi
        latest_publikasi_cte = """
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # Query to get Top 10 Dosen based on Sinta 1-6 publications
        query = f"""
            {latest_publikasi_cte}
            SELECT 
                d.v_nama_dosen,
                COUNT(DISTINCT p.v_id_publikasi) as count_national
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            CROSS JOIN LATERAL (
                SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
            ) authors
            LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
            LEFT JOIN datamaster dm ON (
                (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
            )
            WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 1', 'sinta 2', 'sinta 3', 'sinta 4', 'sinta 5', 'sinta 6')
                AND d.v_nama_dosen IS NOT NULL
                AND dm.v_nama_homebase_unpar IS NOT NULL
            GROUP BY d.v_nama_dosen
            ORDER BY count_national DESC
            LIMIT 10
        """
        
        cur.execute(query)
        results = [dict(row) for row in cur.fetchall()]
        
        print(f"✅ Top Dosen National (Sinta 1-6) - Found {len(results)} records")
        
        return jsonify({
            'success': True,
            'data': results
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Top Dosen National error:\n{error_details}")
        logger.error(f"Top Dosen National error: {e}\n{error_details}")
        return jsonify({'success': False, 'error': 'Failed to fetch top dosen national'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()


# Get faculties for dashboard filter
@app.route('/api/dashboard/faculties', methods=['GET'])
@token_required
def get_dashboard_faculties(current_user_id):
    """Get list of faculties for dashboard filter"""
    try:
        faculties = sorted(list(DASHBOARD_FACULTY_DEPARTMENT_MAPPING.keys()))
        return jsonify({
            'success': True,
            'data': faculties
        }), 200
    except Exception as e:
        logger.error(f"Get dashboard faculties error: {e}")
        return jsonify({'error': 'Failed to fetch faculties'}), 500


# Get departments for dashboard filter
@app.route('/api/dashboard/departments', methods=['GET'])
@token_required
def get_dashboard_departments(current_user_id):
    """Get list of departments in a faculty for dashboard filter"""
    try:
        faculty = request.args.get('faculty', '').strip()
        
        if not faculty:
            return jsonify({'error': 'Faculty parameter is required'}), 400
        
        departments = DASHBOARD_FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
        
        return jsonify({
            'success': True,
            'data': sorted(departments)
        }), 200
    except Exception as e:
        logger.error(f"Get dashboard departments error: {e}")
        return jsonify({'error': 'Failed to fetch departments'}), 500   

# SINTA Routes
@app.route('/api/sinta/dosen', methods=['GET'])
@token_required
def get_sinta_dosen(current_user_id):
    """Get SINTA dosen data with pagination, search, and faculty/department filters"""
    conn = None
    cur = None
    print(f"🔑 Authenticated user ID: {current_user_id}")
    
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        offset = (page - 1) * per_page
        
        # Debug logging
        print(f"📥 SINTA Dosen - page: {page}, per_page: {per_page}, search: '{search}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query for SINTA data
        where_clause = "WHERE (d.v_sumber = 'SINTA' OR d.v_sumber IS NULL)"
        params = []
        
        if search:
            where_clause += " AND LOWER(d.v_nama_dosen) LIKE LOWER(%s)"
            params.append(f'%{search}%')
            print(f"🔍 Adding search filter for dosen name: {search}")
        
        print(f"🗃️ WHERE clause: {where_clause}")
        print(f"🗃️ Params: {params}")
        
        # Create CTE to get only latest version of each dosen (by nama_dosen)
        latest_dosen_cte = f"""
            WITH latest_dosen AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                {where_clause}
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # Build faculty/department filter for the main query
        faculty_filter = ""
        faculty_params = []
        
        if department:
            # Specific department selected
            faculty_filter = "WHERE LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            faculty_params.append(department.lower())
            print(f"🏢 Filtering by department: {department}")
        elif faculty:
            # Only faculty selected, filter by all departments in that faculty
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                # Create LIKE conditions for each department
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    faculty_params.append(f"%{dept.lower()}%")
                
                faculty_filter = f"WHERE ({' OR '.join(like_conditions)})"
                print(f"🏛️ Filtering by faculty: {faculty} (departments: {departments_in_faculty})")
                print(f"🔍 Faculty filter SQL: {faculty_filter}")
                print(f"🔍 Faculty params: {faculty_params}")
        
        # Get total count from CTE with faculty filter
        count_query = f"""
            {latest_dosen_cte}
            SELECT COUNT(*) as total
            FROM latest_dosen d
            LEFT JOIN datamaster dm ON d.v_id_sinta IS NOT NULL 
                AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
            {faculty_filter}
        """
        cur.execute(count_query, params + faculty_params)
        total = cur.fetchone()['total']
        
        print(f"📊 Total unique SINTA dosen found: {total}")
        
        # Get data from CTE with jurusan from datamaster
        data_query = f"""
            {latest_dosen_cte}
            SELECT
                d.v_id_dosen, 
                d.v_nama_dosen, 
                d.v_id_sinta, 
                d.v_id_googlescholar,
                COALESCE(d.n_total_publikasi, 0) AS n_total_publikasi, 
                COALESCE(d.n_sitasi_gs, 0) AS n_sitasi_gs, 
                COALESCE(d.n_sitasi_scopus, 0) AS n_sitasi_scopus,
                COALESCE(d.n_h_index_gs_sinta, 0) AS n_h_index_gs_sinta, 
                COALESCE(d.n_h_index_scopus, 0) AS n_h_index_scopus,
                COALESCE(d.n_i10_index_gs, 0) AS n_i10_index_gs, 
                d.n_skor_sinta, 
                d.n_skor_sinta_3yr,
                d.t_tanggal_unduh, 
                d.v_link_url,
                dm.v_nama_homebase_unpar AS v_nama_jurusan
            FROM latest_dosen d
            LEFT JOIN datamaster dm ON d.v_id_sinta IS NOT NULL 
                AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
            {faculty_filter}
            ORDER BY (COALESCE(d.n_sitasi_gs, 0) + COALESCE(d.n_sitasi_scopus, 0)) DESC, d.t_tanggal_unduh DESC
            LIMIT %s OFFSET %s
        """
        params_full = params + faculty_params + [per_page, offset]
        
        try:
            cur.execute(data_query, params_full)
            sinta_data = [dict(row) for row in cur.fetchall()]
            
            # Add faculty information to each record based on department
            for dosen in sinta_data:
                department_name = dosen.get('v_nama_jurusan')
                if department_name:
                    faculty_name = get_faculty_from_department(department_name)
                    dosen['v_nama_fakultas'] = faculty_name
                else:
                    dosen['v_nama_fakultas'] = None
            
            # Debug: Log jurusan sources
            if sinta_data and len(sinta_data) > 0:
                print(f"📤 Returning {len(sinta_data)} SINTA dosen records")
                for i, dosen in enumerate(sinta_data[:5]):
                    sinta_id = dosen.get('v_id_sinta', 'N/A')
                    jurusan = dosen.get('v_nama_jurusan', 'N/A')
                    fakultas = dosen.get('v_nama_fakultas', 'N/A')
                    print(f"   Record {i+1}: {dosen.get('v_nama_dosen', 'N/A')} | SINTA_ID: {sinta_id} | Fakultas: {fakultas} | Jurusan: {jurusan}")
        
        except Exception as query_error:
            # If DataMaster join fails, return data without jurusan
            logger.warning(f"Query with DataMaster failed: {query_error}, trying fallback query")
            # Rollback the failed transaction before trying fallback
            conn.rollback()
            
            fallback_query = f"""
                {latest_dosen_cte}
                SELECT
                    d.v_id_dosen, 
                    d.v_nama_dosen, 
                    d.v_id_sinta, 
                    d.v_id_googlescholar,
                    COALESCE(d.n_total_publikasi, 0) AS n_total_publikasi, 
                    COALESCE(d.n_sitasi_gs, 0) AS n_sitasi_gs, 
                    COALESCE(d.n_sitasi_scopus, 0) AS n_sitasi_scopus,
                    COALESCE(d.n_h_index_gs_sinta, 0) AS n_h_index_gs_sinta, 
                    COALESCE(d.n_h_index_scopus, 0) AS n_h_index_scopus,
                    COALESCE(d.n_i10_index_gs, 0) AS n_i10_index_gs, 
                    d.n_skor_sinta, 
                    d.n_skor_sinta_3yr,
                    d.t_tanggal_unduh, 
                    d.v_link_url,
                    NULL AS v_nama_jurusan,
                    NULL AS v_nama_fakultas
                FROM latest_dosen d
                ORDER BY (COALESCE(d.n_sitasi_gs, 0) + COALESCE(d.n_sitasi_scopus, 0)) DESC, d.t_tanggal_unduh DESC
                LIMIT %s OFFSET %s
            """
            cur.execute(fallback_query, params + [per_page, offset])
            sinta_data = [dict(row) for row in cur.fetchall()]
            print(f"⚠️ Using fallback query without DataMaster join")
        
        # Commit the transaction after successful queries
        conn.commit()
        
        return jsonify({
            'success': True,  # ✅ ADDED
            'data': {
                'data': sinta_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ SINTA Dosen error:\n", error_details)
        logger.error(f"Get SINTA dosen error: {e}\n{error_details}")
        # Rollback any failed transaction
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({'error': 'Failed to fetch SINTA dosen data'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/sinta/dosen/stats', methods=['GET'])
@token_required
def get_sinta_dosen_stats(current_user_id):
    """Get SINTA dosen aggregate statistics with faculty/department filter"""
    conn = None
    cur = None
    
    try:
        search = request.args.get('search', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        
        print(f"📊 SINTA Dosen Stats - search: '{search}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # ✅ TAMBAHAN: Get latest and previous scraping dates
        cur.execute("""
            SELECT DISTINCT DATE(t_tanggal_unduh) as tanggal
            FROM tmp_dosen_dt
            WHERE t_tanggal_unduh IS NOT NULL
            ORDER BY tanggal DESC
            LIMIT 2
        """)
        dates = cur.fetchall()
        latest_date = dates[0]['tanggal'] if dates and len(dates) > 0 else None
        previous_date = dates[1]['tanggal'] if dates and len(dates) > 1 else None
        
        print(f"📅 Latest: {latest_date}, Previous: {previous_date}")
        
        # Build query for SINTA data
        where_clause = "WHERE (d.v_sumber = 'SINTA' OR d.v_sumber IS NULL)"
        params = []
        
        if search:
            where_clause += " AND LOWER(d.v_nama_dosen) LIKE LOWER(%s)"
            params.append(f'%{search}%')
        
        # Create CTE to get only latest version of each dosen
        latest_dosen_cte = f"""
            WITH latest_dosen AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                {where_clause}
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # ✅ TAMBAHAN: CTE for previous data
        previous_dosen_cte = f"""
            , previous_dosen AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                {where_clause}
                    AND DATE(d.t_tanggal_unduh) <= %s
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # Build faculty/department filter
        faculty_filter = ""
        faculty_params = []
        
        if department:
            # Specific department selected
            faculty_filter = "WHERE LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            faculty_params.append(department.lower())
        elif faculty:
            # Only faculty selected, filter by all departments in that faculty
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                # Create LIKE conditions for each department
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    faculty_params.append(f"%{dept.lower()}%")
                
                faculty_filter = f"WHERE ({' OR '.join(like_conditions)})"
                print(f"🏛️ Stats filtering by faculty: {faculty} with {len(departments_in_faculty)} departments")
        
        # Get aggregate statistics from CTE with median (LATEST)
        stats_query = f"""
            {latest_dosen_cte}
            SELECT
                COUNT(*) as total_dosen,
                COALESCE(SUM(d.n_sitasi_gs), 0) as total_sitasi_gs,
                COALESCE(SUM(d.n_sitasi_scopus), 0) as total_sitasi_scopus,
                COALESCE(AVG(d.n_h_index_gs_sinta), 0) as avg_h_index,
                COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.n_h_index_gs_sinta), 0) as median_h_index,
                COALESCE(SUM(d.n_total_publikasi), 0) as total_publikasi
            FROM latest_dosen d
            LEFT JOIN datamaster dm ON d.v_id_sinta IS NOT NULL 
                AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
            {faculty_filter}
        """
        cur.execute(stats_query, params + faculty_params)
        stats = cur.fetchone()
        
        print(f"📊 Stats result: {stats}")
        
        # ✅ TAMBAHAN: Get previous statistics if previous_date exists
        previous_values = {}
        if previous_date:
            previous_stats_query = f"""
                {latest_dosen_cte}
                {previous_dosen_cte}
                SELECT
                    COUNT(*) as total_dosen,
                    COALESCE(SUM(d.n_sitasi_gs), 0) as total_sitasi_gs,
                    COALESCE(SUM(d.n_sitasi_scopus), 0) as total_sitasi_scopus,
                    COALESCE(AVG(d.n_h_index_gs_sinta), 0) as avg_h_index,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.n_h_index_gs_sinta), 0) as median_h_index,
                    COALESCE(SUM(d.n_total_publikasi), 0) as total_publikasi
                FROM previous_dosen d
                LEFT JOIN datamaster dm ON d.v_id_sinta IS NOT NULL 
                    AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
                {faculty_filter}
            """
            # Add previous_date parameter after params
            prev_params = params + [previous_date] + faculty_params
            cur.execute(previous_stats_query, prev_params)
            prev_stats = cur.fetchone()
            
            if prev_stats:
                previous_values = {
                    'totalDosen': prev_stats['total_dosen'] or 0,
                    'totalSitasiGS': int(prev_stats['total_sitasi_gs']) if prev_stats['total_sitasi_gs'] else 0,
                    'totalSitasiScopus': int(prev_stats['total_sitasi_scopus']) if prev_stats['total_sitasi_scopus'] else 0,
                    'avgHIndex': round(float(prev_stats['avg_h_index']), 1) if prev_stats['avg_h_index'] else 0,
                    'medianHIndex': round(float(prev_stats['median_h_index']), 1) if prev_stats['median_h_index'] else 0,
                    'totalPublikasi': prev_stats['total_publikasi'] or 0
                }
                print(f"📊 Previous stats: {previous_values}")
        
        return jsonify({
            'success': True,
            'data': {
                'totalDosen': stats['total_dosen'] or 0,
                'totalSitasiGS': int(stats['total_sitasi_gs']) if stats['total_sitasi_gs'] else 0,
                'totalSitasiScopus': int(stats['total_sitasi_scopus']) if stats['total_sitasi_scopus'] else 0,
                'avgHIndex': round(float(stats['avg_h_index']), 1) if stats['avg_h_index'] else 0,
                'medianHIndex': round(float(stats['median_h_index']), 1) if stats['median_h_index'] else 0,
                'totalPublikasi': stats['total_publikasi'] or 0,
                'previousDate': previous_date.strftime('%d/%m/%Y') if previous_date else None,  # ✅ TAMBAHAN
                'previousValues': previous_values  # ✅ TAMBAHAN
            }
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ SINTA Dosen stats error:\n", error_details)
        logger.error(f"Get SINTA dosen stats error: {e}\n{error_details}")
        return jsonify({'error': 'Failed to fetch SINTA dosen statistics'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/sinta/dosen/faculties', methods=['GET'])
@token_required
def get_sinta_faculties(current_user_id):
    """Get list of faculties with SINTA dosen"""
    conn = None
    cur = None
    
    try:
        print(f"🔑 Fetching faculties for user: {current_user_id}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Get all departments from datamaster that have SINTA data
            query = """
                SELECT DISTINCT 
                    TRIM(dm.v_nama_homebase_unpar) as jurusan
                FROM datamaster dm
                WHERE dm.id_sinta IS NOT NULL 
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
            """
            
            print(f"🔍 Executing department query to derive faculties...")
            cur.execute(query)
            results = cur.fetchall()
            departments = [row['jurusan'] for row in results if row['jurusan']]
            
            print(f"📋 Found {len(departments)} departments with SINTA data")
            
            # Map departments to faculties
            faculties_set = set()
            for dept in departments:
                faculty = get_faculty_from_department(dept)
                if faculty:
                    faculties_set.add(faculty)
                    print(f"  • {dept} → {faculty}")
            
            faculties = sorted(list(faculties_set))
            
            print(f"📚 Derived {len(faculties)} faculties from departments")
            
            # If no faculties found, return all possible faculties
            if not faculties:
                print("⚠️ No faculties derived, using complete list")
                faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
            
            return jsonify({
                'success': True,
                'data': {
                    'faculties': faculties
                }
            }), 200
            
        except Exception as query_error:
            import traceback
            print(f"❌ Query error: {query_error}")
            print(traceback.format_exc())
            # Return all faculties if query fails
            faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
            print(f"⚠️ Using complete faculty list ({len(faculties)} faculties)")
            return jsonify({
                'success': True,
                'data': {
                    'faculties': faculties
                }
            }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Get faculties error:\n", error_details)
        logger.error(f"Get faculties error: {e}\n{error_details}")
        
        # Return all faculties even on major error
        faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
        return jsonify({
            'success': True,
            'data': {
                'faculties': faculties
            }
        }), 200
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/sinta/dosen/departments', methods=['GET'])
@token_required
def get_sinta_departments(current_user_id):
    """Get list of departments in a faculty with SINTA dosen"""
    conn = None
    cur = None
    
    try:
        faculty = request.args.get('faculty', '').strip()
        
        print(f"🔑 Fetching departments for user: {current_user_id}, faculty: {faculty}")
        
        if not faculty:
            return jsonify({'error': 'Faculty parameter is required'}), 400
        
        # Get departments from mapping first
        mapped_departments = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
        print(f"📋 Mapped departments for {faculty}: {mapped_departments}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed, using mapped departments")
            return jsonify({
                'success': True,
                'data': {
                    'departments': mapped_departments
                }
            }), 200
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Get all departments from datamaster that have SINTA data
            query = """
                SELECT DISTINCT 
                    TRIM(dm.v_nama_homebase_unpar) as jurusan
                FROM datamaster dm
                WHERE dm.id_sinta IS NOT NULL 
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                ORDER BY jurusan
            """
            
            print(f"🔍 Executing department query...")
            cur.execute(query)
            results = cur.fetchall()
            all_departments = [row['jurusan'] for row in results if row['jurusan']]
            
            print(f"📊 Found {len(all_departments)} total departments with SINTA data")
            
            # Filter departments that belong to the selected faculty
            filtered_departments = []
            for dept in all_departments:
                dept_faculty = get_faculty_from_department(dept)
                if dept_faculty == faculty:
                    filtered_departments.append(dept)
                    print(f"  ✓ {dept} belongs to {faculty}")
            
            print(f"🏢 Found {len(filtered_departments)} departments for {faculty}")
            
            # If no departments found, use mapped departments
            if not filtered_departments:
                print(f"⚠️ No departments found in DB, using mapped list")
                filtered_departments = mapped_departments
            
            return jsonify({
                'success': True,
                'data': {
                    'departments': sorted(filtered_departments)
                }
            }), 200
            
        except Exception as query_error:
            import traceback
            print(f"❌ Query error: {query_error}")
            print(traceback.format_exc())
            # Return mapped departments if query fails
            print(f"⚠️ Using mapped departments for {faculty}")
            return jsonify({
                'departments': mapped_departments
            }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Get departments error:\n", error_details)
        logger.error(f"Get departments error: {e}\n{error_details}")
        # Return mapped departments even on major error
        mapped_departments = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
        return jsonify({
            'success': True,
            'data': {
                'departments': mapped_departments
            }
        }), 200
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/sinta/dosen/export', methods=['GET'])
@token_required
def export_sinta_dosen(current_user_id):
    """Export SINTA dosen data to Excel"""
    conn = None
    cur = None
    
    try:
        search = request.args.get('search', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        
        print(f"📥 Export SINTA Dosen - search: '{search}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query for SINTA data (same as get_sinta_dosen but without pagination)
        where_clause = "WHERE (d.v_sumber = 'SINTA' OR d.v_sumber IS NULL)"
        params = []
        
        if search:
            where_clause += " AND LOWER(d.v_nama_dosen) LIKE LOWER(%s)"
            params.append(f'%{search}%')
        
        latest_dosen_cte = f"""
            WITH latest_dosen AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                {where_clause}
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # Build faculty/department filter (same as get_sinta_dosen)
        faculty_filter = ""
        faculty_params = []
        
        if department:
            # Specific department selected
            faculty_filter = "WHERE LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            faculty_params.append(department.lower())
            print(f"🏢 Filtering by department: {department}")
        elif faculty:
            # Only faculty selected, filter by all departments in that faculty
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                # Create LIKE conditions for each department
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    faculty_params.append(f"%{dept.lower()}%")
                
                faculty_filter = f"WHERE ({' OR '.join(like_conditions)})"
                print(f"🏛️ Filtering by faculty: {faculty} (departments: {departments_in_faculty})")
        
        # Get all data without pagination
        data_query = f"""
            {latest_dosen_cte}
            SELECT
                d.v_id_dosen, 
                d.v_nama_dosen, 
                d.v_id_sinta, 
                d.v_id_googlescholar,
                COALESCE(d.n_total_publikasi, 0) AS n_total_publikasi, 
                COALESCE(d.n_sitasi_gs, 0) AS n_sitasi_gs, 
                COALESCE(d.n_sitasi_scopus, 0) AS n_sitasi_scopus,
                COALESCE(d.n_h_index_gs_sinta, 0) AS n_h_index_gs_sinta, 
                COALESCE(d.n_h_index_scopus, 0) AS n_h_index_scopus,
                COALESCE(d.n_i10_index_gs, 0) AS n_i10_index_gs, 
                d.n_skor_sinta, 
                d.n_skor_sinta_3yr,
                d.t_tanggal_unduh, 
                d.v_link_url,
                dm.v_nama_homebase_unpar AS v_nama_jurusan
            FROM latest_dosen d
            LEFT JOIN datamaster dm ON d.v_id_sinta IS NOT NULL 
                AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
            {faculty_filter}
            ORDER BY (COALESCE(d.n_sitasi_gs, 0) + COALESCE(d.n_sitasi_scopus, 0)) DESC, d.t_tanggal_unduh DESC
        """
        params_full = params + faculty_params
        cur.execute(data_query, params_full)
        dosen_data = [dict(row) for row in cur.fetchall()]
        
        # Add faculty information to each record based on department (same as get_sinta_dosen)
        for dosen in dosen_data:
            department_name = dosen.get('v_nama_jurusan')
            if department_name:
                faculty_name = get_faculty_from_department(department_name)
                dosen['v_nama_fakultas'] = faculty_name
            else:
                dosen['v_nama_fakultas'] = None
        
        # Convert to DataFrame
        df = pd.DataFrame(dosen_data)
        
        # Rename columns to Indonesian
        column_mapping = {
            'v_nama_dosen': 'Nama Dosen',
            'v_nama_fakultas': 'Fakultas',
            'v_nama_jurusan': 'Jurusan',
            'v_id_sinta': 'ID SINTA',
            'v_id_googlescholar': 'ID Google Scholar',
            'n_total_publikasi': 'Total Publikasi',
            'n_sitasi_gs': 'Sitasi Google Scholar',
            'n_sitasi_scopus': 'Sitasi Scopus',
            'n_h_index_gs_sinta': 'H-Index Google Scholar',
            'n_h_index_scopus': 'H-Index Scopus',
            'n_i10_index_gs': 'i10-Index Google Scholar',
            'n_skor_sinta': 'Skor SINTA',
            'n_skor_sinta_3yr': 'Skor SINTA 3 Tahun',
            't_tanggal_unduh': 'Tanggal Unduh',
            'v_link_url': 'Link URL'
        }
        
        # Select and rename columns
        available_columns = [col for col in column_mapping.keys() if col in df.columns]
        df_export = df[available_columns].rename(columns=column_mapping)
        
        # Format tanggal
        if 'Tanggal Unduh' in df_export.columns:
            df_export['Tanggal Unduh'] = pd.to_datetime(df_export['Tanggal Unduh'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='SINTA Dosen')
        
        output.seek(0)
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=sinta_dosen_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        return response
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Export SINTA Dosen error:\n", error_details)
        logger.error(f"Export SINTA dosen error: {e}\n{error_details}")
        return jsonify({'error': 'Failed to export SINTA dosen data'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/sinta/publikasi', methods=['GET'])
@token_required
def get_sinta_publikasi(current_user_id):
    """Get SINTA publikasi data with pagination, search, tipe, year range, and faculty/department filter"""
    conn = None
    cur = None
    print(f"🔑 Authenticated user ID: {current_user_id}")
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        tipe_filter = request.args.get('tipe', '').strip().lower()
        terindeks_filter = request.args.get('terindeks', '').strip()
        year_start = request.args.get('year_start', '').strip()
        year_end = request.args.get('year_end', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        offset = (page - 1) * per_page

        print(f"📥 Request params - page: {page}, per_page: {per_page}, search: '{search}', tipe: '{tipe_filter}', terindeks: '{terindeks_filter}', year_start: '{year_start}', year_end: '{year_end}', faculty: '{faculty}', department: '{department}'")

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Build base WHERE clause for SINTA publications
        where_clause = "WHERE (p.v_sumber ILIKE %s OR p.v_sumber IS NULL)"
        params = ['%SINTA%']

        # Add tipe filter
        if tipe_filter and tipe_filter != 'all':
            where_clause += " AND LOWER(p.v_jenis) = %s"
            params.append(tipe_filter)
            print(f"🔍 Adding tipe filter: {tipe_filter}")

        # Add year range filter
        if year_start:
            where_clause += " AND p.v_tahun_publikasi >= %s"
            params.append(int(year_start))
            print(f"🔍 Adding year_start filter: {year_start}")

        if year_end:
            where_clause += " AND p.v_tahun_publikasi <= %s"
            params.append(int(year_end))
            print(f"🔍 Adding year_end filter: {year_end}")

        # Expand search to include title, authors, and publisher
        if search:
            where_clause += """ AND (
                LOWER(p.v_judul) LIKE LOWER(%s) OR
                LOWER(p.v_authors) LIKE LOWER(%s) OR
                LOWER(p.v_publisher) LIKE LOWER(%s)
            )"""
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
            print(f"🔍 Adding search filter: {search}")

        # Build faculty/department filter
        jurusan_filter = ""
        jurusan_params = []
        
        if department:
            jurusan_filter = "AND LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            jurusan_params.append(department.lower())
            print(f"🏢 Filtering by department: {department}")
        elif faculty:
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    jurusan_params.append(f"%{dept.lower()}%")
                jurusan_filter = f"AND ({' OR '.join(like_conditions)})"
                print(f"🏛️ Filtering by faculty: {faculty} (departments: {departments_in_faculty})")

        # CTE: Using stg_publikasi_dosen_dt as bridge table
        latest_publikasi_cte = f"""
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                {where_clause}
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            ),
            publikasi_with_metadata AS (
                SELECT 
                    p.v_id_publikasi,
                    COALESCE(
                        NULLIF(
                            STRING_AGG(DISTINCT d.v_nama_dosen, ', ' ORDER BY d.v_nama_dosen) 
                            FILTER (WHERE d.v_nama_dosen IS NOT NULL AND TRIM(d.v_nama_dosen) != ''),
                            ''
                        ),
                        NULLIF(TRIM(p.v_authors), ''),
                        'N/A'
                    ) as authors,
                    STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar) 
                        FILTER (WHERE dm.v_nama_homebase_unpar IS NOT NULL AND TRIM(dm.v_nama_homebase_unpar) != '') 
                        as jurusan_names
                FROM latest_publikasi p
                LEFT JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                LEFT JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                    AND d.v_sumber = 'SINTA'
                    AND d.v_id_sinta IS NOT NULL 
                    AND TRIM(d.v_id_sinta) != ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    {jurusan_filter}
                GROUP BY p.v_id_publikasi, p.v_authors
            )
        """

        # ✅ PERBAIKAN: Build terindeks filter - PISAHKAN GARUDA DAN SINTA
        terindeks_filter_clause = ""
        terindeks_params = []
        
        if terindeks_filter and terindeks_filter != 'all':
            if terindeks_filter == 'Other':
                terindeks_filter_clause = """AND (
                    a.v_terindeks IS NULL 
                    OR TRIM(a.v_terindeks) = '' 
                    OR (
                        a.v_terindeks !~* '\\y(scopus|garuda|sinta|googlescholar|google scholar)\\y'
                    )
                )"""
                print(f"🔍 Filter: Other (not in major indexes)")
                
            elif terindeks_filter == 'GoogleScholar':
                terindeks_filter_clause = """AND (
                    a.v_terindeks ~* '\\y(googlescholar|google scholar)\\y'
                )"""
                print(f"🔍 Filter: Google Scholar (word boundary match)")
                
            else:
                # ✅ Exact match untuk Garuda, SINTA, Scopus, DOAJ (TERPISAH)
                terindeks_filter_clause = """AND (
                    a.v_terindeks ~* %s
                )"""
                regex_pattern = f'\\y{terindeks_filter.lower()}\\y'
                terindeks_params.append(regex_pattern)
                print(f"🔍 Filter: {terindeks_filter} (exact match, regex: {regex_pattern})")

        cte_params = params + jurusan_params

        # Count query
        if jurusan_filter:
            count_query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(*) AS total
                FROM latest_publikasi p
                INNER JOIN publikasi_with_metadata pm ON p.v_id_publikasi = pm.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE pm.jurusan_names IS NOT NULL AND pm.jurusan_names != ''
                {terindeks_filter_clause}
            """
        else:
            count_query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(*) AS total
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE 1=1
                {terindeks_filter_clause}
            """

        cur.execute(count_query, cte_params + terindeks_params)
        count_result = cur.fetchone()
        total = count_result.get('total', 0) or 0 if count_result else 0
        print(f"📊 Total unique records found: {total}")

        # Data query
        if jurusan_filter:
            data_query = f"""
                {latest_publikasi_cte}
                SELECT
                    p.v_id_publikasi,
                    pm.authors,
                    COALESCE(pm.jurusan_names, 'N/A') AS v_nama_jurusan,
                    p.v_judul,
                    p.v_jenis AS tipe,
                    p.v_tahun_publikasi,
                    COALESCE(j.v_nama_jurnal, pr.v_nama_konferensi, 'N/A') AS venue,
                    COALESCE(p.v_publisher, '') AS publisher,
                    COALESCE(a.v_volume, '') AS volume,
                    COALESCE(a.v_issue, '') AS issue,
                    COALESCE(a.v_pages, '') AS pages,
                    COALESCE(a.v_terindeks, '') AS v_terindeks,
                    COALESCE(a.v_ranking, '') AS v_ranking,
                    COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                    p.v_sumber,
                    p.t_tanggal_unduh,
                    p.v_link_url
                FROM latest_publikasi p
                INNER JOIN publikasi_with_metadata pm ON p.v_id_publikasi = pm.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                WHERE pm.jurusan_names IS NOT NULL AND pm.jurusan_names != ''
                {terindeks_filter_clause}
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
                LIMIT %s OFFSET %s
            """
        else:
            data_query = f"""
                {latest_publikasi_cte}
                SELECT
                    p.v_id_publikasi,
                    COALESCE(pm.authors, NULLIF(TRIM(p.v_authors), ''), 'N/A') AS authors,
                    COALESCE(NULLIF(TRIM(pm.jurusan_names), ''), 'N/A') AS v_nama_jurusan,
                    p.v_judul,
                    p.v_jenis AS tipe,
                    p.v_tahun_publikasi,
                    COALESCE(j.v_nama_jurnal, pr.v_nama_konferensi, 'N/A') AS venue,
                    COALESCE(p.v_publisher, '') AS publisher,
                    COALESCE(a.v_volume, '') AS volume,
                    COALESCE(a.v_issue, '') AS issue,
                    COALESCE(a.v_pages, '') AS pages,
                    COALESCE(a.v_terindeks, '') AS v_terindeks,
                    COALESCE(a.v_ranking, '') AS v_ranking,
                    COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                    p.v_sumber,
                    p.t_tanggal_unduh,
                    p.v_link_url
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_metadata pm ON p.v_id_publikasi = pm.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                WHERE 1=1
                {terindeks_filter_clause}
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
                LIMIT %s OFFSET %s
            """

        final_params = cte_params + terindeks_params + [per_page, offset]
        cur.execute(data_query, final_params)
        rows = cur.fetchall()

        # Add fakultas information
        for row in rows:
            jurusan_names = row.get('v_nama_jurusan', '')
            if jurusan_names and jurusan_names != 'N/A' and jurusan_names.strip():
                departments = [dept.strip() for dept in jurusan_names.split(',')]
                faculties = set()
                for dept in departments:
                    fakultas = get_faculty_from_department(dept)
                    if fakultas:
                        faculties.add(fakultas)
                
                if faculties:
                    row['v_nama_fakultas'] = ', '.join(sorted(faculties))
                else:
                    row['v_nama_fakultas'] = None
            else:
                row['v_nama_fakultas'] = None

        # Debug log
        if rows and len(rows) > 0:
            print(f"📤 Retrieved {len(rows)} SINTA publikasi records")
            for i, row in enumerate(rows[:3]):
                terindeks = row.get('v_terindeks', 'N/A')
                print(f"   Record {i+1}: {row.get('v_judul', 'N/A')[:40]}...")
                print(f"      Terindeks: {terindeks}")

        # Format data
        publikasi_data = []
        if rows:
            for row in rows:
                row_dict = dict(row)
                
                # Format vol/issue
                vol = row_dict.get('volume', '').strip()
                issue = row_dict.get('issue', '').strip()
                if vol and issue:
                    row_dict['vol_issue'] = f"{vol}({issue})"
                elif vol:
                    row_dict['vol_issue'] = vol
                elif issue:
                    row_dict['vol_issue'] = f"({issue})"
                else:
                    row_dict['vol_issue'] = "-"

                # Format tipe
                tipe_value = row_dict.get('tipe', '').strip() if row_dict.get('tipe') else ''
                tipe_mapping = {
                    'artikel': 'Artikel',
                    'buku': 'Buku',
                    'prosiding': 'Prosiding',
                    'penelitian': 'Penelitian',
                    'lainnya': 'Lainnya'
                }
                if tipe_value:
                    row_dict['tipe'] = tipe_mapping.get(tipe_value.lower(), tipe_value.capitalize())
                else:
                    row_dict['tipe'] = 'N/A'

                publikasi_data.append(row_dict)

        conn.commit()

        total_pages = 0
        if total > 0 and per_page > 0:
            total_pages = (total + per_page - 1) // per_page

        return jsonify({
            'success': True,
            'data': {
                'data': publikasi_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': total_pages
                }
            }
        }), 200

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Full error traceback:\n", error_details)
        logger.error(f"Get SINTA publikasi error: {e}\n{error_details}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({
            'success': False,
            'error': 'Failed to fetch SINTA publikasi data',
            'details': str(e)
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/sinta/publikasi/stats', methods=['GET'])
@token_required
def get_sinta_publikasi_stats(current_user_id):
    """Get SINTA publikasi aggregate statistics with faculty/department filter"""
    conn = None
    cur = None
    try:
        search = request.args.get('search', '').strip()
        tipe_filter = request.args.get('tipe', '').strip().lower()
        terindeks_filter = request.args.get('terindeks', '').strip()
        year_start = request.args.get('year_start', '').strip()
        year_end = request.args.get('year_end', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()

        print(f"📊 SINTA Publikasi Stats - search: '{search}', tipe: '{tipe_filter}', terindeks: '{terindeks_filter}', year_start: '{year_start}', year_end: '{year_end}', faculty: '{faculty}', department: '{department}'")

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Get latest and previous scraping dates
        cur.execute("""
            SELECT DISTINCT DATE(t_tanggal_unduh) as tanggal
            FROM stg_publikasi_tr
            WHERE t_tanggal_unduh IS NOT NULL
                AND (v_sumber ILIKE '%SINTA%' OR v_sumber IS NULL)
            ORDER BY tanggal DESC
            LIMIT 2
        """)
        dates = cur.fetchall()
        latest_date = dates[0]['tanggal'] if dates and len(dates) > 0 else None
        previous_date = dates[1]['tanggal'] if dates and len(dates) > 1 else None
        print(f"📅 SINTA Latest: {latest_date}, Previous: {previous_date}")

        # Build base WHERE clause for SINTA publications
        where_clause = "WHERE (p.v_sumber ILIKE %s OR p.v_sumber IS NULL)"
        params = ['%SINTA%']

        if tipe_filter and tipe_filter != 'all':
            where_clause += " AND LOWER(p.v_jenis) = %s"
            params.append(tipe_filter)

        if year_start:
            where_clause += " AND p.v_tahun_publikasi >= %s"
            params.append(int(year_start))

        if year_end:
            where_clause += " AND p.v_tahun_publikasi <= %s"
            params.append(int(year_end))

        if search:
            where_clause += """ AND (
                LOWER(p.v_judul) LIKE LOWER(%s) OR
                LOWER(p.v_authors) LIKE LOWER(%s) OR
                LOWER(p.v_publisher) LIKE LOWER(%s)
            )"""
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])

        # Build faculty/department filter
        jurusan_filter = ""
        jurusan_params = []
        
        if department:
            jurusan_filter = "AND LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            jurusan_params.append(department.lower())
            print(f"🏢 Filtering by department: {department}")
        elif faculty:
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    jurusan_params.append(f"%{dept.lower()}%")
                jurusan_filter = f"AND ({' OR '.join(like_conditions)})"
                print(f"🏛️ Filtering by faculty: {faculty} (departments: {departments_in_faculty})")

        # CTE menggunakan stg_publikasi_dosen_dt
        latest_publikasi_cte = f"""
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                {where_clause}
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            ),
            publikasi_with_metadata AS (
                SELECT 
                    p.v_id_publikasi,
                    p.n_total_sitasi,
                    STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar) 
                        FILTER (WHERE dm.v_nama_homebase_unpar IS NOT NULL AND TRIM(dm.v_nama_homebase_unpar) != '') 
                        as jurusan_names
                FROM latest_publikasi p
                LEFT JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                LEFT JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                    AND d.v_sumber = 'SINTA'
                    AND d.v_id_sinta IS NOT NULL 
                    AND TRIM(d.v_id_sinta) != ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    {jurusan_filter}
                GROUP BY p.v_id_publikasi, p.n_total_sitasi
            )
        """

        # ✅ PERBAIKAN: Build terindeks filter - SAMA SEPERTI PUBLIKASI ENDPOINT
        terindeks_filter_clause = ""
        terindeks_params = []
        
        if terindeks_filter and terindeks_filter != 'all':
            if terindeks_filter == 'Other':
                terindeks_filter_clause = """AND (
                    a.v_terindeks IS NULL 
                    OR TRIM(a.v_terindeks) = '' 
                    OR (
                        a.v_terindeks !~* '\\y(scopus|garuda|sinta|googlescholar|google scholar)\\y'
                    )
                )"""
                print(f"🔍 Filter: Other (not in major indexes)")
                
            elif terindeks_filter == 'GoogleScholar':
                terindeks_filter_clause = """AND (
                    a.v_terindeks ~* '\\y(googlescholar|google scholar)\\y'
                )"""
                print(f"🔍 Filter: Google Scholar (word boundary match)")
                
            else:
                # ✅ Exact match untuk Garuda, SINTA, Scopus, DOAJ (TERPISAH)
                terindeks_filter_clause = """AND (
                    a.v_terindeks ~* %s
                )"""
                regex_pattern = f'\\y{terindeks_filter.lower()}\\y'
                terindeks_params.append(regex_pattern)
                print(f"🔍 Filter: {terindeks_filter} (exact match, regex: {regex_pattern})")

        cte_params = params + jurusan_params

        # Get aggregate statistics (LATEST)
        if jurusan_filter:
            stats_query = f"""
                {latest_publikasi_cte}
                SELECT
                    COUNT(*) as total_publikasi,
                    COALESCE(SUM(pm.n_total_sitasi), 0) as total_sitasi,
                    COALESCE(AVG(pm.n_total_sitasi), 0) as avg_sitasi,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pm.n_total_sitasi), 0) as median_sitasi
                FROM publikasi_with_metadata pm
                LEFT JOIN stg_artikel_dr a ON pm.v_id_publikasi = a.v_id_publikasi
                WHERE pm.jurusan_names IS NOT NULL AND pm.jurusan_names != ''
                {terindeks_filter_clause}
            """
            print("📊 Using filtered stats")
        else:
            stats_query = f"""
                {latest_publikasi_cte}
                SELECT
                    COUNT(*) as total_publikasi,
                    COALESCE(SUM(p.n_total_sitasi), 0) as total_sitasi,
                    COALESCE(AVG(p.n_total_sitasi), 0) as avg_sitasi,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.n_total_sitasi), 0) as median_sitasi
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE 1=1
                {terindeks_filter_clause}
            """
            print("📊 Using all stats")

        stats_params = cte_params + terindeks_params
        print(f"🔍 Stats query params count: {len(stats_params)}")
        
        cur.execute(stats_query, stats_params)
        stats = cur.fetchone()
        print(f"📊 Stats result: Total={stats['total_publikasi']}, Sitasi={stats['total_sitasi']}")

        # Get previous statistics if previous_date exists
        previous_values = {}
        if previous_date:
            previous_publikasi_cte = f"""
                , previous_publikasi AS (
                    SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                        p.*
                    FROM stg_publikasi_tr p
                    {where_clause}
                        AND DATE(p.t_tanggal_unduh) <= %s
                    ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
                    ),
                    previous_publikasi_with_metadata AS (
                    SELECT
                    p.v_id_publikasi,
                    p.n_total_sitasi,
                    STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar)
                    FILTER (WHERE dm.v_nama_homebase_unpar IS NOT NULL AND TRIM(dm.v_nama_homebase_unpar) != '')
                    as jurusan_names
                    FROM previous_publikasi p
                    LEFT JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                    LEFT JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                    AND d.v_sumber = 'SINTA'
                    AND d.v_id_sinta IS NOT NULL
                    AND TRIM(d.v_id_sinta) != ''
                    LEFT JOIN datamaster dm ON TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    {jurusan_filter}
                    GROUP BY p.v_id_publikasi, p.n_total_sitasi
                    )
            """

            if jurusan_filter:
                previous_stats_query = f"""
                    {latest_publikasi_cte}
                    {previous_publikasi_cte}
                    SELECT
                        COUNT(*) as total_publikasi,
                        COALESCE(SUM(pm.n_total_sitasi), 0) as total_sitasi,
                        COALESCE(AVG(pm.n_total_sitasi), 0) as avg_sitasi,
                        COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY pm.n_total_sitasi), 0) as median_sitasi
                    FROM previous_publikasi_with_metadata pm
                    LEFT JOIN stg_artikel_dr a ON pm.v_id_publikasi = a.v_id_publikasi
                    WHERE pm.jurusan_names IS NOT NULL AND pm.jurusan_names != ''
                    {terindeks_filter_clause}
                """
            else:
                previous_stats_query = f"""
                    {latest_publikasi_cte}
                    {previous_publikasi_cte}
                    SELECT
                        COUNT(*) as total_publikasi,
                        COALESCE(SUM(p.n_total_sitasi), 0) as total_sitasi,
                        COALESCE(AVG(p.n_total_sitasi), 0) as avg_sitasi,
                        COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.n_total_sitasi), 0) as median_sitasi
                    FROM previous_publikasi p
                    LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                    WHERE 1=1
                    {terindeks_filter_clause}
                """

            prev_params = cte_params + [previous_date] + terindeks_params
            print(f"🔍 Previous query params count: {len(prev_params)}")
            
            try:
                cur.execute(previous_stats_query, prev_params)
                prev_stats = cur.fetchone()
                if prev_stats:
                    previous_values = {
                        'totalPublikasi': prev_stats['total_publikasi'] or 0,
                        'totalSitasi': int(prev_stats['total_sitasi']) if prev_stats['total_sitasi'] else 0,
                        'avgSitasi': round(float(prev_stats['avg_sitasi']), 1) if prev_stats['avg_sitasi'] else 0,
                        'medianSitasi': round(float(prev_stats['median_sitasi']), 1) if prev_stats['median_sitasi'] else 0
                    }
                    print(f"📊 Previous stats: {previous_values}")
            except Exception as e:
                print(f"⚠️ Error fetching previous stats: {e}")
                import traceback
                print(traceback.format_exc())
                previous_values = {}

        return jsonify({
            'success': True,
            'data': {
                'totalPublikasi': stats['total_publikasi'] or 0,
                'totalSitasi': int(stats['total_sitasi']) if stats['total_sitasi'] else 0,
                'avgSitasi': round(float(stats['avg_sitasi']), 1) if stats['avg_sitasi'] else 0,
                'medianSitasi': round(float(stats['median_sitasi']), 1) if stats['median_sitasi'] else 0,
                'previousDate': previous_date.strftime('%d/%m/%Y') if previous_date else None,
                'previousValues': previous_values
            }
        }), 200

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ SINTA Publikasi stats error:\n", error_details)
        logger.error(f"Get SINTA publikasi stats error: {e}\n{error_details}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({'success': False, 'error': 'Failed to fetch SINTA publikasi statistics'}), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/sinta/publikasi/export', methods=['GET'])
@token_required
def export_sinta_publikasi(current_user_id):
    """Export SINTA publikasi data to Excel"""
    conn = None
    cur = None
    
    try:
        search = request.args.get('search', '').strip()
        tipe_filter = request.args.get('tipe', '').strip().lower()
        terindeks_filter = request.args.get('terindeks', '').strip()
        year_start = request.args.get('year_start', '').strip()
        year_end = request.args.get('year_end', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        
        print(f"📥 Export SINTA Publikasi - search: '{search}', tipe: '{tipe_filter}', terindeks: '{terindeks_filter}', year_start: '{year_start}', year_end: '{year_end}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build base WHERE clause (same as get_sinta_publikasi)
        where_clause = "WHERE (p.v_sumber ILIKE %s OR p.v_sumber IS NULL)"
        params = ['%SINTA%']
        
        if tipe_filter and tipe_filter != 'all':
            where_clause += " AND LOWER(p.v_jenis) = %s"
            params.append(tipe_filter)
        
        if year_start:
            where_clause += " AND p.v_tahun_publikasi >= %s"
            params.append(int(year_start))
        
        if year_end:
            where_clause += " AND p.v_tahun_publikasi <= %s"
            params.append(int(year_end))
        
        if search:
            where_clause += """ AND (
                LOWER(p.v_judul) LIKE LOWER(%s) OR
                LOWER(p.v_authors) LIKE LOWER(%s) OR
                LOWER(p.v_publisher) LIKE LOWER(%s)
            )"""
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        # Build faculty/department filter
        jurusan_filter = ""
        jurusan_params = []
        if department:
            jurusan_filter = "AND LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            jurusan_params.append(department.lower())
        elif faculty:
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    jurusan_params.append(f"%{dept.lower()}%")
                jurusan_filter = f"AND ({' OR '.join(like_conditions)})"
        
        # Build terindeks filter
        terindeks_filter_clause = ""
        terindeks_params = []
        if terindeks_filter and terindeks_filter != 'all':
            if terindeks_filter == 'Other':
                terindeks_filter_clause = """AND (
                    a.v_terindeks IS NULL 
                    OR TRIM(a.v_terindeks) = '' 
                    OR (a.v_terindeks !~* '\\y(scopus|garuda|sinta|googlescholar|google scholar)\\y')
                )"""
            elif terindeks_filter == 'GoogleScholar':
                terindeks_filter_clause = """AND (a.v_terindeks ~* '\\y(googlescholar|google scholar)\\y')"""
            else:
                terindeks_filter_clause = "AND (a.v_terindeks ~* %s)"
                regex_pattern = f'\\y{terindeks_filter.lower()}\\y'
                terindeks_params.append(regex_pattern)
        
        # CTE (same as get_sinta_publikasi)
        latest_publikasi_cte = f"""
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                {where_clause}
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            ),
            publikasi_with_metadata AS (
                SELECT 
                    p.v_id_publikasi,
                    COALESCE(
                        NULLIF(
                            STRING_AGG(DISTINCT d.v_nama_dosen, ', ' ORDER BY d.v_nama_dosen) 
                            FILTER (WHERE d.v_nama_dosen IS NOT NULL AND TRIM(d.v_nama_dosen) != ''),
                            ''
                        ),
                        NULLIF(TRIM(p.v_authors), ''),
                        'N/A'
                    ) as authors,
                    STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar) 
                        FILTER (WHERE dm.v_nama_homebase_unpar IS NOT NULL AND TRIM(dm.v_nama_homebase_unpar) != '') 
                        as jurusan_names
                FROM latest_publikasi p
                LEFT JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                LEFT JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                    AND d.v_sumber = 'SINTA'
                    AND d.v_id_sinta IS NOT NULL 
                    AND TRIM(d.v_id_sinta) != ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    {jurusan_filter}
                GROUP BY p.v_id_publikasi, p.v_authors
            )
        """
        
        cte_params = params + jurusan_params
        
        # Get all data without pagination
        if jurusan_filter:
            data_query = f"""
                {latest_publikasi_cte}
                SELECT
                    pm.authors,
                    COALESCE(pm.jurusan_names, 'N/A') AS v_nama_jurusan,
                    p.v_judul,
                    p.v_jenis AS tipe,
                    p.v_tahun_publikasi,
                    COALESCE(j.v_nama_jurnal, pr.v_nama_konferensi, 'N/A') AS venue,
                    COALESCE(p.v_publisher, '') AS publisher,
                    COALESCE(a.v_volume, '') AS volume,
                    COALESCE(a.v_issue, '') AS issue,
                    COALESCE(a.v_pages, '') AS pages,
                    COALESCE(a.v_terindeks, '') AS v_terindeks,
                    COALESCE(a.v_ranking, '') AS v_ranking,
                    COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                    p.t_tanggal_unduh,
                    p.v_link_url
                FROM latest_publikasi p
                INNER JOIN publikasi_with_metadata pm ON p.v_id_publikasi = pm.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                WHERE pm.jurusan_names IS NOT NULL AND pm.jurusan_names != ''
                {terindeks_filter_clause}
                ORDER BY p.v_tahun_publikasi DESC NULLS LAST, p.v_judul
            """
        else:
            data_query = f"""
                {latest_publikasi_cte}
                SELECT
                    COALESCE(pm.authors, p.v_authors, 'N/A') AS authors,
                    COALESCE(pm.jurusan_names, 'N/A') AS v_nama_jurusan,
                    p.v_judul,
                    p.v_jenis AS tipe,
                    p.v_tahun_publikasi,
                    COALESCE(j.v_nama_jurnal, pr.v_nama_konferensi, 'N/A') AS venue,
                    COALESCE(p.v_publisher, '') AS publisher,
                    COALESCE(a.v_volume, '') AS volume,
                    COALESCE(a.v_issue, '') AS issue,
                    COALESCE(a.v_pages, '') AS pages,
                    COALESCE(a.v_terindeks, '') AS v_terindeks,
                    COALESCE(a.v_ranking, '') AS v_ranking,
                    COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                    p.t_tanggal_unduh,
                    p.v_link_url
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_metadata pm ON p.v_id_publikasi = pm.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                WHERE 1=1
                {terindeks_filter_clause}
                ORDER BY p.v_tahun_publikasi DESC NULLS LAST, p.v_judul
            """
        
        params_full = cte_params + terindeks_params
        cur.execute(data_query, params_full)
        publikasi_data = cur.fetchall()
        
        # Convert to DataFrame
        df = pd.DataFrame(publikasi_data)
        
        # Create vol_issue column
        if 'volume' in df.columns and 'issue' in df.columns:
            df['vol_issue'] = df.apply(
                lambda row: f"Vol {row['volume']}, Issue {row['issue']}" 
                if row['volume'] and row['issue'] 
                else (f"Vol {row['volume']}" if row['volume'] else (f"Issue {row['issue']}" if row['issue'] else '')),
                axis=1
            )
        
        # Rename columns to Indonesian
        column_mapping = {
            'authors': 'Author',
            'v_nama_jurusan': 'Jurusan',
            'v_judul': 'Judul Publikasi',
            'tipe': 'Tipe',
            'v_tahun_publikasi': 'Tahun',
            'venue': 'Venue/Jurnal',
            'publisher': 'Publisher',
            'vol_issue': 'Vol/Issue',
            'pages': 'Pages',
            'v_terindeks': 'Terindeks',
            'v_ranking': 'Ranking',
            'n_total_sitasi': 'Total Sitasi',
            't_tanggal_unduh': 'Tanggal Unduh',
            'v_link_url': 'Link URL'
        }
        
        # Select and rename columns
        available_columns = [col for col in column_mapping.keys() if col in df.columns]
        df_export = df[available_columns].rename(columns=column_mapping)
        
        # Format tanggal
        if 'Tanggal Unduh' in df_export.columns:
            df_export['Tanggal Unduh'] = pd.to_datetime(df_export['Tanggal Unduh'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='SINTA Publikasi')
        
        output.seek(0)
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=sinta_publikasi_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        return response
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Export SINTA Publikasi error:\n", error_details)
        logger.error(f"Export SINTA publikasi error: {e}\n{error_details}")
        return jsonify({'error': 'Failed to export SINTA publikasi data'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/sinta/publikasi/faculties', methods=['GET'])
@token_required
def get_sinta_publikasi_faculties(current_user_id):
    """Get list of faculties with SINTA publikasi"""
    conn = None
    cur = None
    
    try:
        print(f"🔑 Fetching publikasi faculties for user: {current_user_id}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed")
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Get all departments from publications via authors
            query = """
                SELECT DISTINCT 
                    TRIM(dm.v_nama_homebase_unpar) as jurusan
                FROM stg_publikasi_tr p
                CROSS JOIN LATERAL (
                    SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
                ) authors
                LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
                    AND d.v_id_sinta IS NOT NULL 
                    AND TRIM(d.v_id_sinta) <> ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
                WHERE (p.v_sumber ILIKE '%SINTA%' OR p.v_sumber IS NULL)
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
            """
            
            print(f"🔍 Executing department query to derive faculties...")
            cur.execute(query)
            results = cur.fetchall()
            departments = [row['jurusan'] for row in results if row['jurusan']]
            
            print(f"📋 Found {len(departments)} departments with SINTA publikasi data")
            
            # Map departments to faculties
            faculties_set = set()
            for dept in departments:
                faculty = get_faculty_from_department(dept)
                if faculty:
                    faculties_set.add(faculty)
                    print(f"  • {dept} → {faculty}")
            
            faculties = sorted(list(faculties_set))
            
            print(f"📚 Derived {len(faculties)} faculties from departments")
            
            # If no faculties found, return all possible faculties
            if not faculties:
                print("⚠️ No faculties derived, using complete list")
                faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
            
            return jsonify({
                'success': True,
                'data': {
                    'faculties': faculties
                }
            }), 200
            
        except Exception as query_error:
            import traceback
            print(f"❌ Query error: {query_error}")
            print(traceback.format_exc())
            # Return all faculties if query fails
            faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
            print(f"⚠️ Using complete faculty list ({len(faculties)} faculties)")
            return jsonify({
                'success': True,
                'data': {
                    'faculties': faculties
                }
            }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Get publikasi faculties error:\n", error_details)
        logger.error(f"Get publikasi faculties error: {e}\n{error_details}")
        
        # Return all faculties even on major error
        faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
        return jsonify({
                'success': True,
                'data': {
                    'faculties': faculties
                }
            }), 200
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/sinta/publikasi/departments', methods=['GET'])
@token_required
def get_sinta_publikasi_departments(current_user_id):
    """Get list of departments in a faculty with SINTA publikasi"""
    conn = None
    cur = None
    
    try:
        faculty = request.args.get('faculty', '').strip()
        
        print(f"🔑 Fetching publikasi departments for user: {current_user_id}, faculty: {faculty}")
        
        if not faculty:
            return jsonify({'error': 'Faculty parameter is required'}), 400
        
        # Get departments from mapping first
        mapped_departments = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
        print(f"📋 Mapped departments for {faculty}: {mapped_departments}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed, using mapped departments")
            return jsonify({
                'success': True,
                'data': {
                    'departments': mapped_departments
                }
            }), 200
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Get all departments from publications via authors
            query = """
                SELECT DISTINCT 
                    TRIM(dm.v_nama_homebase_unpar) as jurusan
                FROM stg_publikasi_tr p
                CROSS JOIN LATERAL (
                    SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
                ) authors
                LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
                    AND d.v_id_sinta IS NOT NULL 
                    AND TRIM(d.v_id_sinta) <> ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
                WHERE (p.v_sumber ILIKE '%SINTA%' OR p.v_sumber IS NULL)
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                ORDER BY jurusan
            """
            
            print(f"🔍 Executing department query...")
            cur.execute(query)
            results = cur.fetchall()
            all_departments = [row['jurusan'] for row in results if row['jurusan']]
            
            print(f"📊 Found {len(all_departments)} total departments with SINTA publikasi data")
            
            # Filter departments that belong to the selected faculty
            filtered_departments = []
            for dept in all_departments:
                dept_faculty = get_faculty_from_department(dept)
                if dept_faculty == faculty:
                    filtered_departments.append(dept)
                    print(f"  ✓ {dept} belongs to {faculty}")
            
            print(f"🏢 Found {len(filtered_departments)} departments for {faculty}")
            
            # If no departments found, use mapped departments
            if not filtered_departments:
                print(f"⚠️ No departments found in DB, using mapped list")
                filtered_departments = mapped_departments
            
            return jsonify({
                'success': True,
                'data': {
                    'departments': sorted(filtered_departments)
                }
            }), 200
            
        except Exception as query_error:
            import traceback
            print(f"❌ Query error: {query_error}")
            print(traceback.format_exc())
            # Return mapped departments if query fails
            print(f"⚠️ Using mapped departments for {faculty}")
            return jsonify({
                'success': True,
                'data': {
                    'departments': mapped_departments
                }
            }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Get publikasi departments error:\n", error_details)
        logger.error(f"Get publikasi departments error: {e}\n{error_details}")
        # Return mapped departments even on major error
        mapped_departments = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
        return jsonify({
                'success': True,
                'data': {
                    'departments': mapped_departments
                }
            }), 200
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# Faculty mapping based on department names
FACULTY_DEPARTMENT_MAPPING = {
    'Ekonomi': [
        'Ekonomi Pembangunan',
        'Ilmu Ekonomi',
        'Manajemen',
        'Akuntansi'
    ],
    'Hukum': [
        'Ilmu Hukum',
        'Hukum'
    ],
    'Ilmu Sosial dan Ilmu Politik': [
        'Administrasi Publik',
        'Administrasi Bisnis',
        'Hubungan Internasional',
        'Ilmu Administrasi Publik',
        'Ilmu Administrasi Bisnis',
        'Ilmu Hubungan Internasional'
    ],
    'Teknik': [
        'Teknik Sipil',
        'Arsitektur'
    ],
    'Filsafat': [
        'Filsafat',
        'Ilmu Filsafat',
        'Studi Humanitas'
    ],
    'Sains': [
        'Matematika',
        'Fisika',
        'Informatika',
        'Teknik Informatika',
        'Ilmu Komputer'
    ],
    'Kedokteran': [
        'Kedokteran',
        'Pendidikan Dokter'
    ],
    'Keguruan dan Ilmu Pendidikan': [
        'Pendidikan Kimia',
        'Pendidikan Fisika',
        'Pendidikan Matematika',
        'Pendidikan Teknik Informatika dan Komputer',
        'Pendidikan Bahasa Inggris',
        'Pendidikan Guru Sekolah Dasar',
        'PGSD'
    ],
    'Vokasi': [
        'Teknologi Rekayasa Pangan',
        'Bisnis Kreatif',
        'Agribisnis Pangan'
    ],
    'Teknik Rekayasa': [
        'Teknik Industri',
        'Teknik Kimia',
        'Teknik Mekatronika'
    ]
}

def get_faculty_from_department(department):
    """Get faculty name from department name"""
    if not department:
        return None
    
    department_lower = department.lower().strip()
    
    for faculty, departments in FACULTY_DEPARTMENT_MAPPING.items():
        for dept in departments:
            if dept.lower() in department_lower or department_lower in dept.lower():
                return faculty
    
    return None

# Google Scholar Routes
@app.route('/api/scholar/dosen', methods=['GET'])
@token_required
def get_scholar_dosen(current_user_id):
    """Get Google Scholar dosen data with pagination, search, and faculty/department filters"""
    conn = None
    cur = None
    print(f"🔑 Authenticated user ID: {current_user_id}")
    
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        offset = (page - 1) * per_page
        
        # Debug logging
        print(f"📥 Scholar Dosen - page: {page}, per_page: {per_page}, search: '{search}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query for Google Scholar data
        where_clause = "WHERE (d.v_sumber = 'Google Scholar' OR d.v_id_googleScholar IS NOT NULL)"
        params = []
        
        if search:
            where_clause += " AND LOWER(d.v_nama_dosen) LIKE LOWER(%s)"
            params.append(f'%{search}%')
            print(f"🔍 Adding search filter for dosen name: {search}")
        
        print(f"🗃️ WHERE clause: {where_clause}")
        print(f"🗃️ Params: {params}")
        
        # Create CTE to get only latest version of each dosen (by nama_dosen)
        latest_dosen_cte = f"""
            WITH latest_dosen AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                {where_clause}
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # Build faculty/department filter for the main query
        faculty_filter = ""
        faculty_params = []
        
        if department:
            # Specific department selected
            faculty_filter = "WHERE LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            faculty_params.append(department.lower())
            print(f"🏢 Filtering by department: {department}")
        elif faculty:
            # Only faculty selected, filter by all departments in that faculty
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                # Create LIKE conditions for each department
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    faculty_params.append(f"%{dept.lower()}%")
                
                faculty_filter = f"WHERE ({' OR '.join(like_conditions)})"
                print(f"🏛️ Filtering by faculty: {faculty} (departments: {departments_in_faculty})")
                print(f"🔍 Faculty filter SQL: {faculty_filter}")
                print(f"🔍 Faculty params: {faculty_params}")
        
        # Get total count from CTE with faculty filter
        count_query = f"""
            {latest_dosen_cte}
            SELECT COUNT(*) as total
            FROM latest_dosen d
            LEFT JOIN datamaster dm ON d.v_id_googleScholar IS NOT NULL 
                AND TRIM(d.v_id_googleScholar) = TRIM(dm.id_gs)
            {faculty_filter}
        """
        cur.execute(count_query, params + faculty_params)
        total = cur.fetchone()['total']
        
        print(f"📊 Total unique Scholar dosen found: {total}")
        
        # Get data from CTE with jurusan from datamaster
        data_query = f"""
            {latest_dosen_cte}
            SELECT
                d.v_id_dosen, 
                d.v_nama_dosen, 
                d.v_id_googleScholar,
                d.n_total_publikasi, 
                d.n_total_sitasi_gs, 
                d.n_total_sitasi_gs2020,
                d.n_h_index_gs, 
                d.n_h_index_gs2020,
                d.n_i10_index_gs, 
                d.n_i10_index_gs2020,
                d.v_link_url, 
                d.t_tanggal_unduh,
                dm.v_nama_homebase_unpar AS v_nama_jurusan
            FROM latest_dosen d
            LEFT JOIN datamaster dm ON d.v_id_googleScholar IS NOT NULL 
                AND TRIM(d.v_id_googleScholar) = TRIM(dm.id_gs)
            {faculty_filter}
            ORDER BY d.n_total_sitasi_gs DESC NULLS LAST, d.t_tanggal_unduh DESC
            LIMIT %s OFFSET %s
        """
        params_full = params + faculty_params + [per_page, offset]
        
        try:
            cur.execute(data_query, params_full)
            scholar_data = [dict(row) for row in cur.fetchall()]
            
            # Add faculty information to each record based on department
            for dosen in scholar_data:
                department_name = dosen.get('v_nama_jurusan')
                if department_name:
                    faculty_name = get_faculty_from_department(department_name)
                    dosen['v_nama_fakultas'] = faculty_name
                else:
                    dosen['v_nama_fakultas'] = None
            
            # Debug: Log jurusan sources
            if scholar_data and len(scholar_data) > 0:
                print(f"📤 Returning {len(scholar_data)} Scholar dosen records")
                for i, dosen in enumerate(scholar_data[:5]):
                    gs_id = dosen.get('v_id_googlescholar', 'N/A')
                    jurusan = dosen.get('v_nama_jurusan', 'N/A')
                    fakultas = dosen.get('v_nama_fakultas', 'N/A')
                    print(f"   Record {i+1}: {dosen.get('v_nama_dosen', 'N/A')} | GS_ID: {gs_id} | Fakultas: {fakultas} | Jurusan: {jurusan}")
        
        except Exception as query_error:
            # If DataMaster join fails, return data without jurusan
            logger.warning(f"Query with DataMaster failed: {query_error}, trying fallback query")
            # Rollback the failed transaction before trying fallback
            conn.rollback()
            
            fallback_query = f"""
                {latest_dosen_cte}
                SELECT
                    d.v_id_dosen, 
                    d.v_nama_dosen, 
                    d.v_id_googleScholar,
                    d.n_total_publikasi, 
                    d.n_total_sitasi_gs, 
                    d.n_total_sitasi_gs2020,
                    d.n_h_index_gs, 
                    d.n_h_index_gs2020,
                    d.n_i10_index_gs, 
                    d.n_i10_index_gs2020,
                    d.v_link_url, 
                    d.t_tanggal_unduh,
                    NULL AS v_nama_jurusan,
                    NULL AS v_nama_fakultas
                FROM latest_dosen d
                ORDER BY d.n_total_sitasi_gs DESC NULLS LAST, d.t_tanggal_unduh DESC
                LIMIT %s OFFSET %s
            """
            cur.execute(fallback_query, params + [per_page, offset])
            scholar_data = [dict(row) for row in cur.fetchall()]
            print(f"⚠️ Using fallback query without DataMaster join")
        
        # Commit the transaction after successful queries
        conn.commit()
        
        return jsonify({
            'success': True,  # ✅ ADDED
            'data': {
                'data': scholar_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': (total + per_page - 1) // per_page
                }
            }
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Scholar Dosen error:\n", error_details)
        logger.error(f"Get Scholar dosen error: {e}\n{error_details}")
        # Rollback any failed transaction
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({'success': False, 'error': 'Failed to fetch Scholar dosen data'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/scholar/dosen/stats', methods=['GET'])
@token_required
def get_scholar_dosen_stats(current_user_id):
    """Get Google Scholar dosen aggregate statistics with faculty/department filter"""
    conn = None
    cur = None
    
    try:
        search = request.args.get('search', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        
        print(f"📊 Scholar Dosen Stats - search: '{search}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # ✅ TAMBAHAN: Get latest and previous scraping dates
        cur.execute("""
            SELECT DISTINCT DATE(t_tanggal_unduh) as tanggal
            FROM tmp_dosen_dt
            WHERE t_tanggal_unduh IS NOT NULL
                AND (v_sumber = 'Google Scholar' OR v_id_googlescholar IS NOT NULL)
            ORDER BY tanggal DESC
            LIMIT 2
        """)
        dates = cur.fetchall()
        latest_date = dates[0]['tanggal'] if dates and len(dates) > 0 else None
        previous_date = dates[1]['tanggal'] if dates and len(dates) > 1 else None
        
        print(f"📅 Latest: {latest_date}, Previous: {previous_date}")
        
        # Build query for Google Scholar data
        where_clause = "WHERE (d.v_sumber = 'Google Scholar' OR d.v_id_googlescholar IS NOT NULL)"
        params = []
        
        if search:
            where_clause += " AND LOWER(d.v_nama_dosen) LIKE LOWER(%s)"
            params.append(f'%{search}%')
        
        # Create CTE to get only latest version of each dosen
        latest_dosen_cte = f"""
            WITH latest_dosen AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                {where_clause}
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # ✅ TAMBAHAN: CTE for previous data
        previous_dosen_cte = f"""
            , previous_dosen AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                {where_clause}
                    AND DATE(d.t_tanggal_unduh) <= %s
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # Build faculty/department filter
        faculty_filter = ""
        faculty_params = []
        
        if department:
            # Specific department selected
            faculty_filter = "WHERE LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            faculty_params.append(department.lower())
        elif faculty:
            # Only faculty selected, filter by all departments in that faculty
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                # Create LIKE conditions for each department
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    faculty_params.append(f"%{dept.lower()}%")
                
                faculty_filter = f"WHERE ({' OR '.join(like_conditions)})"
                print(f"🏛️ Stats filtering by faculty: {faculty} with {len(departments_in_faculty)} departments")
        
        # Get aggregate statistics from CTE with median (LATEST)
        stats_query = f"""
            {latest_dosen_cte}
            SELECT
                COUNT(*) as total_dosen,
                COALESCE(SUM(d.n_total_sitasi_gs), 0) as total_sitasi,
                COALESCE(AVG(d.n_h_index_gs), 0) as avg_h_index,
                COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.n_h_index_gs), 0) as median_h_index,
                COALESCE(SUM(d.n_total_publikasi), 0) as total_publikasi,
                COALESCE(AVG(d.n_i10_index_gs), 0) as avg_i10_index,
                COALESCE(AVG(d.n_h_index_gs2020), 0) as avg_h_index_2020,
                COALESCE(AVG(d.n_i10_index_gs2020), 0) as avg_i10_index_2020
            FROM latest_dosen d
            LEFT JOIN datamaster dm ON d.v_id_googleScholar IS NOT NULL 
                AND TRIM(d.v_id_googleScholar) = TRIM(dm.id_gs)
            {faculty_filter}
        """
        cur.execute(stats_query, params + faculty_params)
        stats = cur.fetchone()
        
        print(f"📊 Stats result: {stats}")
        
        # ✅ TAMBAHAN: Get previous statistics if previous_date exists
        previous_values = {}
        if previous_date:
            previous_stats_query = f"""
                {latest_dosen_cte}
                {previous_dosen_cte}
                SELECT
                    COUNT(*) as total_dosen,
                    COALESCE(SUM(d.n_total_sitasi_gs), 0) as total_sitasi,
                    COALESCE(AVG(d.n_h_index_gs), 0) as avg_h_index,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.n_h_index_gs), 0) as median_h_index,
                    COALESCE(SUM(d.n_total_publikasi), 0) as total_publikasi
                FROM previous_dosen d
                LEFT JOIN datamaster dm ON d.v_id_googleScholar IS NOT NULL 
                    AND TRIM(d.v_id_googleScholar) = TRIM(dm.id_gs)
                {faculty_filter}
            """
            # Add previous_date parameter after params
            prev_params = params + [previous_date] + faculty_params
            cur.execute(previous_stats_query, prev_params)
            prev_stats = cur.fetchone()
            
            if prev_stats:
                previous_values = {
                    'totalDosen': prev_stats['total_dosen'] or 0,
                    'totalSitasi': int(prev_stats['total_sitasi']) if prev_stats['total_sitasi'] else 0,
                    'avgHIndex': round(float(prev_stats['avg_h_index']), 1) if prev_stats['avg_h_index'] else 0,
                    'medianHIndex': round(float(prev_stats['median_h_index']), 1) if prev_stats['median_h_index'] else 0,
                    'totalPublikasi': prev_stats['total_publikasi'] or 0
                }
                print(f"📊 Previous stats: {previous_values}")
        
        return jsonify({
            'success': True,
            'data': {
                'totalDosen': stats['total_dosen'] or 0,
                'totalSitasi': int(stats['total_sitasi']) if stats['total_sitasi'] else 0,
                'avgHIndex': round(float(stats['avg_h_index']), 1) if stats['avg_h_index'] else 0,
                'medianHIndex': round(float(stats['median_h_index']), 1) if stats['median_h_index'] else 0,
                'totalPublikasi': stats['total_publikasi'] or 0,
                'avgI10Index': round(float(stats['avg_i10_index']), 1) if stats['avg_i10_index'] else 0,
                'avgHIndex2020': round(float(stats['avg_h_index_2020']), 1) if stats['avg_h_index_2020'] else 0,
                'avgI10Index2020': round(float(stats['avg_i10_index_2020']), 1) if stats['avg_i10_index_2020'] else 0,
                'previousDate': previous_date.strftime('%d/%m/%Y') if previous_date else None,  # ✅ TAMBAHAN
                'previousValues': previous_values  # ✅ TAMBAHAN
            }
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Scholar Dosen stats error:\n", error_details)
        logger.error(f"Get Scholar dosen stats error: {e}\n{error_details}")
        return jsonify({'success': False, 'error': 'Failed to fetch Scholar dosen statistics'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/scholar/dosen/export', methods=['GET'])
@token_required
def export_scholar_dosen(current_user_id):
    """Export Google Scholar dosen data to Excel"""
    conn = None
    cur = None
    
    try:
        search = request.args.get('search', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        
        print(f"📥 Export Scholar Dosen - search: '{search}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query (same as get_scholar_dosen but without pagination)
        where_clause = "WHERE (d.v_sumber = 'Google Scholar' OR d.v_id_googleScholar IS NOT NULL)"
        params = []
        
        if search:
            where_clause += " AND LOWER(d.v_nama_dosen) LIKE LOWER(%s)"
            params.append(f'%{search}%')
        
        latest_dosen_cte = f"""
            WITH latest_dosen AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                {where_clause}
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        faculty_filter = ""
        faculty_params = []
        if department:
            faculty_filter = "WHERE LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            faculty_params.append(department.lower())
        elif faculty:
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    faculty_params.append(f"%{dept.lower()}%")
                faculty_filter = f"WHERE ({' OR '.join(like_conditions)})"
        
        # Get all data without pagination
        data_query = f"""
            {latest_dosen_cte}
            SELECT
                d.v_id_dosen, 
                d.v_nama_dosen, 
                d.v_id_googleScholar,
                d.n_total_publikasi, 
                d.n_total_sitasi_gs, 
                d.n_total_sitasi_gs2020,
                d.n_h_index_gs, 
                d.n_h_index_gs2020,
                d.n_i10_index_gs, 
                d.n_i10_index_gs2020,
                d.v_link_url, 
                d.t_tanggal_unduh,
                dm.v_nama_homebase_unpar AS v_nama_jurusan
            FROM latest_dosen d
            LEFT JOIN datamaster dm ON d.v_id_googleScholar IS NOT NULL 
                AND TRIM(d.v_id_googleScholar) = TRIM(dm.id_gs)
            {faculty_filter}
            ORDER BY d.n_total_sitasi_gs DESC NULLS LAST, d.t_tanggal_unduh DESC
        """
        params_full = params + faculty_params
        cur.execute(data_query, params_full)
        dosen_data = cur.fetchall()
        
        # Add faculty information
        for dosen in dosen_data:
            department_name = dosen.get('v_nama_jurusan')
            if department_name:
                faculty_name = get_faculty_from_department(department_name)
                dosen['v_nama_fakultas'] = faculty_name
            else:
                dosen['v_nama_fakultas'] = None
        
        # Convert to DataFrame
        df = pd.DataFrame(dosen_data)
        
        # Rename columns to Indonesian
        column_mapping = {
            'v_nama_dosen': 'Nama Dosen',
            'v_nama_fakultas': 'Fakultas',
            'v_nama_jurusan': 'Jurusan',
            'v_id_googleScholar': 'ID Google Scholar',
            'n_total_publikasi': 'Total Publikasi',
            'n_total_sitasi_gs': 'Sitasi Total',
            'n_total_sitasi_gs2020': 'Sitasi (2020)',
            'n_h_index_gs': 'H-Index',
            'n_h_index_gs2020': 'H-Index (2020)',
            'n_i10_index_gs': 'i10-Index',
            'n_i10_index_gs2020': 'i10-Index (2020)',
            't_tanggal_unduh': 'Tanggal Unduh',
            'v_link_url': 'Link URL'
        }
        
        # Select and rename columns
        available_columns = [col for col in column_mapping.keys() if col in df.columns]
        df_export = df[available_columns].rename(columns=column_mapping)
        
        # Format tanggal
        if 'Tanggal Unduh' in df_export.columns:
            df_export['Tanggal Unduh'] = pd.to_datetime(df_export['Tanggal Unduh'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Google Scholar Dosen')
        
        output.seek(0)
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=scholar_dosen_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        return response
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Export Scholar Dosen error:\n", error_details)
        logger.error(f"Export Scholar dosen error: {e}\n{error_details}")
        return jsonify({'error': 'Failed to export Scholar dosen data'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/scholar/dosen/faculties', methods=['GET'])
@token_required
def get_scholar_faculties(current_user_id):
    """Get list of faculties with Scholar dosen"""
    conn = None
    cur = None
    
    try:
        print(f"🔑 Fetching faculties for user: {current_user_id}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed")
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Get all departments from datamaster that have Scholar data
            query = """
                SELECT DISTINCT 
                    TRIM(dm.v_nama_homebase_unpar) as jurusan
                FROM datamaster dm
                WHERE dm.id_gs IS NOT NULL 
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
            """
            
            print(f"🔍 Executing department query to derive faculties...")
            cur.execute(query)
            results = cur.fetchall()
            departments = [row['jurusan'] for row in results if row['jurusan']]
            
            print(f"📋 Found {len(departments)} departments with Scholar data")
            
            # Map departments to faculties
            faculties_set = set()
            for dept in departments:
                faculty = get_faculty_from_department(dept)
                if faculty:
                    faculties_set.add(faculty)
                    print(f"  • {dept} → {faculty}")
            
            faculties = sorted(list(faculties_set))
            
            print(f"📚 Derived {len(faculties)} faculties from departments")
            
            # If no faculties found, return all possible faculties
            if not faculties:
                print("⚠️ No faculties derived, using complete list")
                faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
            
            return jsonify({
                'success': True,  # ✅ ADDED
                'data': {
                    'faculties': faculties
                }
            }), 200
            
        except Exception as query_error:
            import traceback
            print(f"❌ Query error: {query_error}")
            print(traceback.format_exc())
            # Return all faculties if query fails
            faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
            print(f"⚠️ Using complete faculty list ({len(faculties)} faculties)")
            return jsonify({
                'success': True,  # ✅ ADDED
                'data': {
                    'faculties': faculties
                }
            }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Get faculties error:\n", error_details)
        logger.error(f"Get faculties error: {e}\n{error_details}")
        
        # Return all faculties even on major error
        faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
        return jsonify({
            'success': True,  # ✅ ADDED (even on error, return data)
            'data': {
                'faculties': faculties
            }
        }), 200
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/scholar/dosen/departments', methods=['GET'])
@token_required
def get_scholar_departments(current_user_id):
    """Get list of departments in a faculty with Scholar dosen"""
    conn = None
    cur = None
    
    try:
        faculty = request.args.get('faculty', '').strip()
        
        print(f"🔑 Fetching departments for user: {current_user_id}, faculty: {faculty}")
        
        if not faculty:
            return jsonify({'success': False, 'error': 'Faculty parameter is required'}), 400
        
        # Get departments from mapping first
        mapped_departments = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
        print(f"📋 Mapped departments for {faculty}: {mapped_departments}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed, using mapped departments")
            return jsonify({
                'success': True,  # ✅ ADDED
                'data': {
                    'departments': mapped_departments
                }
            }), 200
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # Get all departments from datamaster that have Scholar data
            query = """
                SELECT DISTINCT 
                    TRIM(dm.v_nama_homebase_unpar) as jurusan
                FROM datamaster dm
                WHERE dm.id_gs IS NOT NULL 
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                ORDER BY jurusan
            """
            
            print(f"🔍 Executing department query...")
            cur.execute(query)
            results = cur.fetchall()
            all_departments = [row['jurusan'] for row in results if row['jurusan']]
            
            print(f"📊 Found {len(all_departments)} total departments with Scholar data")
            
            # Filter departments that belong to the selected faculty
            filtered_departments = []
            for dept in all_departments:
                dept_faculty = get_faculty_from_department(dept)
                if dept_faculty == faculty:
                    filtered_departments.append(dept)
                    print(f"  ✓ {dept} belongs to {faculty}")
            
            print(f"🏢 Found {len(filtered_departments)} departments for {faculty}")
            
            # If no departments found, use mapped departments
            if not filtered_departments:
                print(f"⚠️ No departments found in DB, using mapped list")
                filtered_departments = mapped_departments
            
            return jsonify({
                'success': True,  # ✅ ADDED
                'data': {
                    'departments': sorted(filtered_departments)
                }
            }), 200
            
        except Exception as query_error:
            import traceback
            print(f"❌ Query error: {query_error}")
            print(traceback.format_exc())
            # Return mapped departments if query fails
            print(f"⚠️ Using mapped departments for {faculty}")
            return jsonify({
                'success': True,  # ✅ ADDED
                'data': {
                    'departments': mapped_departments
                }
            }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Get departments error:\n", error_details)
        logger.error(f"Get departments error: {e}\n{error_details}")
        # Return mapped departments even on major error
        mapped_departments = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
        return jsonify({
            'success': True,  # ✅ ADDED (even on error)
            'data': {
                'departments': mapped_departments
            }
        }), 200
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/scholar/publikasi', methods=['GET'])
@token_required
def get_scholar_publikasi(current_user_id):
    """Get Google Scholar publikasi data with pagination, search, tipe, year range, and faculty/department filter"""
    conn = None
    cur = None
    print(f"🔑 Authenticated user ID: {current_user_id}")
    
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        tipe_filter = request.args.get('tipe', '').strip().lower()
        year_start = request.args.get('year_start', '').strip()
        year_end = request.args.get('year_end', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        offset = (page - 1) * per_page
        
        # Debug logging
        print(f"📥 Request params - page: {page}, per_page: {per_page}, search: '{search}', tipe: '{tipe_filter}', year_start: '{year_start}', year_end: '{year_end}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build base query - filter untuk Google Scholar
        where_clause = "WHERE p.v_sumber ILIKE %s"
        params = ['%Scholar%']
        
        # Add tipe filter
        if tipe_filter and tipe_filter != 'all':
            where_clause += " AND LOWER(p.v_jenis) = %s"
            params.append(tipe_filter)
            print(f"🔍 Adding tipe filter: {tipe_filter}")
        
        # Add year range filter
        if year_start:
            where_clause += " AND CAST(p.v_tahun_publikasi AS INTEGER) >= %s"
            params.append(int(year_start))
            print(f"🔍 Adding year_start filter: {year_start}")
        
        if year_end:
            where_clause += " AND CAST(p.v_tahun_publikasi AS INTEGER) <= %s"
            params.append(int(year_end))
            print(f"🔍 Adding year_end filter: {year_end}")
        
        # Expand search to include author, title, publisher
        if search:
            where_clause += """ AND (
                LOWER(p.v_judul) LIKE LOWER(%s) OR
                LOWER(p.v_authors) LIKE LOWER(%s) OR
                LOWER(p.v_publisher) LIKE LOWER(%s)
            )"""
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
            print(f"🔍 Adding search filter: {search}")
        
        print(f"🗃️ WHERE clause: {where_clause}")
        
        # Build faculty/department filter for jurusan
        jurusan_filter = ""
        jurusan_params = []
        
        if department:
            # Specific department selected
            jurusan_filter = "AND LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            jurusan_params.append(department.lower())
            print(f"🏢 Filtering by department: {department}")
        elif faculty:
            # Only faculty selected, filter by all departments in that faculty
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                # Create LIKE conditions for each department
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    jurusan_params.append(f"%{dept.lower()}%")
                
                jurusan_filter = f"AND ({' OR '.join(like_conditions)})"
                print(f"🏛️ Filtering by faculty: {faculty} (departments: {departments_in_faculty})")
        
        # Create CTE to get only latest version of each publication (by title and year)
        latest_publikasi_cte = f"""
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                {where_clause}
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            ),
            -- Parse authors from v_authors field and match with datamaster
            publikasi_with_jurusan AS (
                SELECT 
                    p.v_id_publikasi,
                    p.v_authors,
                    STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar) 
                        FILTER (WHERE dm.v_nama_homebase_unpar IS NOT NULL) as jurusan_names
                FROM latest_publikasi p
                CROSS JOIN LATERAL (
                    -- Split authors by comma and trim spaces
                    SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
                ) authors
                LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
                    AND d.v_id_googlescholar IS NOT NULL 
                    AND TRIM(d.v_id_googlescholar) <> ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs)
                    {jurusan_filter}
                GROUP BY p.v_id_publikasi, p.v_authors
            )
        """
        
        # Combine all params for CTE
        cte_params = params + jurusan_params
        
        # Get total count from CTE - only count publications that have matching jurusan if filter applied
        if jurusan_filter:
            count_query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(*) AS total
                FROM latest_publikasi p
                INNER JOIN publikasi_with_jurusan pj ON p.v_id_publikasi = pj.v_id_publikasi
                WHERE pj.jurusan_names IS NOT NULL AND pj.jurusan_names != ''
            """
        else:
            count_query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(*) AS total
                FROM latest_publikasi
            """
        
        cur.execute(count_query, cte_params)
        count_result = cur.fetchone()
        total = count_result.get('total', 0) or 0 if count_result else 0
        
        print(f"📊 Total unique records found: {total}")
        
        # Get data from CTE with proper jurusan join
        if jurusan_filter:
            # If faculty/department filter applied, only show publications with matching jurusan
            data_query = f"""
                {latest_publikasi_cte}
                SELECT
                    p.v_id_publikasi,
                    COALESCE(NULLIF(TRIM(p.v_authors), ''), 'N/A') AS authors,
                    COALESCE(pj.jurusan_names, 'N/A') AS v_nama_jurusan,
                    p.v_judul,
                    p.v_jenis AS tipe,
                    p.v_tahun_publikasi,
                    COALESCE(
                        j.v_nama_jurnal,
                        pr.v_nama_konferensi,
                        'N/A'
                    ) AS venue,
                    COALESCE(p.v_publisher, '') AS publisher,
                    COALESCE(a.v_volume, '') AS volume,
                    COALESCE(a.v_issue, '') AS issue,
                    COALESCE(a.v_pages, '') AS pages,
                    COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                    p.v_sumber,
                    p.t_tanggal_unduh,
                    p.v_link_url
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_jurusan pj ON p.v_id_publikasi = pj.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                WHERE pj.jurusan_names IS NOT NULL AND pj.jurusan_names != ''
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
                LIMIT %s OFFSET %s
            """
        else:
            # No filter, show all publications
            data_query = f"""
                {latest_publikasi_cte}
                SELECT
                    p.v_id_publikasi,
                    COALESCE(NULLIF(TRIM(p.v_authors), ''), 'N/A') AS authors,
                    COALESCE(pj.jurusan_names, 'N/A') AS v_nama_jurusan,
                    p.v_judul,
                    p.v_jenis AS tipe,
                    p.v_tahun_publikasi,
                    COALESCE(
                        j.v_nama_jurnal,
                        pr.v_nama_konferensi,
                        'N/A'
                    ) AS venue,
                    COALESCE(p.v_publisher, '') AS publisher,
                    COALESCE(a.v_volume, '') AS volume,
                    COALESCE(a.v_issue, '') AS issue,
                    COALESCE(a.v_pages, '') AS pages,
                    COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                    p.v_sumber,
                    p.t_tanggal_unduh,
                    p.v_link_url
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_jurusan pj ON p.v_id_publikasi = pj.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
                LIMIT %s OFFSET %s
            """
        
        final_params = cte_params + [per_page, offset]
        
        cur.execute(data_query, final_params)
        rows = cur.fetchall()
        
        # Add fakultas information to each record based on department
        for row in rows:
            jurusan_names = row.get('v_nama_jurusan', '')
            if jurusan_names and jurusan_names != 'N/A':
                # Get first jurusan for fakultas mapping
                first_jurusan = jurusan_names.split(',')[0].strip()
                fakultas = get_faculty_from_department(first_jurusan)
                row['v_nama_fakultas'] = fakultas
            else:
                row['v_nama_fakultas'] = None
        
        # Debug: Log jurusan for first few records
        if rows and len(rows) > 0:
            print(f"📤 Retrieved {len(rows)} Scholar publikasi records")
            
            for i, row in enumerate(rows[:5]):
                jurusan = row.get('v_nama_jurusan', 'N/A')
                fakultas = row.get('v_nama_fakultas', 'N/A')
                authors = row.get('authors', 'N/A')
                print(f"   Record {i+1}: {row.get('v_judul', 'N/A')[:40]}...")
                print(f"      Authors: {authors[:50]}...")
                print(f"      Fakultas: {fakultas} | Jurusan: {jurusan}")
            
            # Count total with jurusan
            total_with_jurusan = sum(1 for r in rows if r.get('v_nama_jurusan') and r.get('v_nama_jurusan') != 'N/A')
            print(f"   📊 Summary: {total_with_jurusan}/{len(rows)} records have jurusan data")
        
        # Format data untuk response
        publikasi_data = []
        if rows:
            for row in rows:
                row_dict = dict(row)
                
                # Format vol/issue
                vol = row_dict.get('volume', '').strip()
                issue = row_dict.get('issue', '').strip()
                if vol and issue:
                    row_dict['vol_issue'] = f"{vol}({issue})"
                elif vol:
                    row_dict['vol_issue'] = vol
                elif issue:
                    row_dict['vol_issue'] = f"({issue})"
                else:
                    row_dict['vol_issue'] = "-"
                
                # Format tipe publikasi
                tipe_value = row_dict.get('tipe', '').strip() if row_dict.get('tipe') else ''
                tipe_mapping = {
                    'artikel': 'Artikel',
                    'buku': 'Buku',
                    'prosiding': 'Prosiding',
                    'penelitian': 'Penelitian',
                    'lainnya': 'Lainnya'
                }
                if tipe_value:
                    row_dict['tipe'] = tipe_mapping.get(tipe_value.lower(), tipe_value.capitalize())
                else:
                    row_dict['tipe'] = 'N/A'
                
                publikasi_data.append(row_dict)
        
        # Commit the transaction after successful queries
        conn.commit()
        
        # Hitung total pages
        total_pages = 0
        if total > 0 and per_page > 0:
            total_pages = (total + per_page - 1) // per_page
        
        return jsonify({
            'success': True,  # ✅ ADDED
            'data': {
                'data': publikasi_data,
                'pagination': {
                    'page': page,
                    'per_page': per_page,
                    'total': total,
                    'pages': total_pages
                }
            }
        }), 200
        
    except psycopg2.Error as db_error:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Database error:\n", error_details)
        logger.error(f"Database error in Scholar publikasi: {db_error}\n{error_details}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({
            'success': False,
            'error': 'Database query failed',
            'details': str(db_error)
        }), 500
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Full error traceback:\n", error_details)
        logger.error(f"Get Scholar publikasi error: {e}\n{error_details}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({
            'success': False,
            'error': 'Failed to fetch Scholar publikasi data',
            'details': str(e)
        }), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


@app.route('/api/scholar/publikasi/stats', methods=['GET'])
@token_required
def get_scholar_publikasi_stats(current_user_id):
    """Get Google Scholar publikasi aggregate statistics with median and faculty/department filter"""
    conn = None
    cur = None
    
    try:
        search = request.args.get('search', '').strip()
        tipe_filter = request.args.get('tipe', '').strip().lower()
        year_start = request.args.get('year_start', '').strip()
        year_end = request.args.get('year_end', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        
        print(f"📊 Scholar Publikasi Stats - search: '{search}', tipe: '{tipe_filter}', year_start: '{year_start}', year_end: '{year_end}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # ✅ TAMBAHAN: Get latest and previous scraping dates
        cur.execute("""
            SELECT DISTINCT DATE(t_tanggal_unduh) as tanggal
            FROM stg_publikasi_tr
            WHERE t_tanggal_unduh IS NOT NULL
                AND v_sumber ILIKE '%Scholar%'
            ORDER BY tanggal DESC
            LIMIT 2
        """)
        dates = cur.fetchall()
        latest_date = dates[0]['tanggal'] if dates and len(dates) > 0 else None
        previous_date = dates[1]['tanggal'] if dates and len(dates) > 1 else None
        
        print(f"📅 Latest: {latest_date}, Previous: {previous_date}")
        
        # Build base query - filter untuk Google Scholar
        where_clause = "WHERE p.v_sumber ILIKE %s"
        params = ['%Scholar%']
        
        if tipe_filter and tipe_filter != 'all':
            where_clause += " AND LOWER(p.v_jenis) = %s"
            params.append(tipe_filter)
        
        if year_start:
            where_clause += " AND CAST(p.v_tahun_publikasi AS INTEGER) >= %s"
            params.append(int(year_start))
        
        if year_end:
            where_clause += " AND CAST(p.v_tahun_publikasi AS INTEGER) <= %s"
            params.append(int(year_end))
        
        if search:
            where_clause += """ AND (
                LOWER(p.v_judul) LIKE LOWER(%s) OR
                LOWER(p.v_authors) LIKE LOWER(%s) OR
                LOWER(p.v_publisher) LIKE LOWER(%s)
            )"""
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        # Build faculty/department filter for jurusan
        jurusan_filter = ""
        jurusan_params = []
        
        if department:
            jurusan_filter = "AND LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            jurusan_params.append(department.lower())
        elif faculty:
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    jurusan_params.append(f"%{dept.lower()}%")
                
                jurusan_filter = f"AND ({' OR '.join(like_conditions)})"
        
        # Create CTE for latest publikasi
        latest_publikasi_cte = f"""
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                {where_clause}
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            ),
            publikasi_with_jurusan AS (
                SELECT 
                    p.v_id_publikasi,
                    p.n_total_sitasi
                FROM latest_publikasi p
                CROSS JOIN LATERAL (
                    SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
                ) authors
                LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
                    AND d.v_id_googlescholar IS NOT NULL 
                    AND TRIM(d.v_id_googlescholar) <> ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs)
                    {jurusan_filter}
                WHERE dm.v_nama_homebase_unpar IS NOT NULL
                GROUP BY p.v_id_publikasi, p.n_total_sitasi
            )
        """
        
        # ✅ TAMBAHAN: CTE for previous data
        previous_publikasi_cte = f"""
            , previous_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                {where_clause}
                    AND DATE(p.t_tanggal_unduh) <= %s
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            ),
            previous_publikasi_with_jurusan AS (
                SELECT 
                    p.v_id_publikasi,
                    p.n_total_sitasi
                FROM previous_publikasi p
                CROSS JOIN LATERAL (
                    SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
                ) authors
                LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
                    AND d.v_id_googlescholar IS NOT NULL 
                    AND TRIM(d.v_id_googlescholar) <> ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs)
                    {jurusan_filter}
                WHERE dm.v_nama_homebase_unpar IS NOT NULL
                GROUP BY p.v_id_publikasi, p.n_total_sitasi
            )
        """
        
        cte_params = params + jurusan_params
        
        # Get aggregate statistics (LATEST)
        stats_query = f"""
            {latest_publikasi_cte}
            SELECT
                COUNT(*) as total_publikasi,
                COALESCE(SUM(p.n_total_sitasi), 0) as total_sitasi,
                COALESCE(AVG(p.n_total_sitasi), 0) as avg_sitasi,
                COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.n_total_sitasi), 0) as median_sitasi
            FROM latest_publikasi p
        """
        
        cur.execute(stats_query, cte_params)
        stats = cur.fetchone()
        
        print(f"📊 Stats result: {stats}")
        
        # ✅ TAMBAHAN: Get previous statistics if previous_date exists
        previous_values = {}
        if previous_date:
            previous_publikasi_cte = f"""
                , previous_publikasi AS (
                    SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                        p.*
                    FROM stg_publikasi_tr p
                    {where_clause}
                        AND DATE(p.t_tanggal_unduh) <= %s
                    ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
                ),
                previous_publikasi_with_jurusan AS (
                    SELECT 
                        p.v_id_publikasi,
                        p.n_total_sitasi
                    FROM previous_publikasi p
                    CROSS JOIN LATERAL (
                        SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
                    ) authors
                    LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
                        AND d.v_id_googlescholar IS NOT NULL 
                        AND TRIM(d.v_id_googlescholar) <> ''
                    LEFT JOIN datamaster dm ON TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs)
                        {jurusan_filter}
                    WHERE dm.v_nama_homebase_unpar IS NOT NULL
                    GROUP BY p.v_id_publikasi, p.n_total_sitasi
                )
            """
            
            previous_stats_query = f"""
                {latest_publikasi_cte}
                {previous_publikasi_cte}
                SELECT
                    COUNT(*) as total_publikasi,
                    COALESCE(SUM(p.n_total_sitasi), 0) as total_sitasi,
                    COALESCE(AVG(p.n_total_sitasi), 0) as avg_sitasi,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.n_total_sitasi), 0) as median_sitasi
                FROM previous_publikasi_with_jurusan p
            """
            
            prev_params = params + jurusan_params + params + [previous_date] + jurusan_params
    
            print(f"🔍 Previous query params count: {len(prev_params)}")
            print(f"🔍 Previous query placeholders: {previous_stats_query.count('%s')}")
            print(f"🔍 Previous query params: {prev_params}")
            
            cur.execute(previous_stats_query, prev_params)
            prev_stats = cur.fetchone()
            
            if prev_stats:
                previous_values = {
                    'totalPublikasi': prev_stats['total_publikasi'] or 0,
                    'totalSitasi': int(prev_stats['total_sitasi']) if prev_stats['total_sitasi'] else 0,
                    'avgSitasi': round(float(prev_stats['avg_sitasi']), 1) if prev_stats['avg_sitasi'] else 0,
                    'medianSitasi': round(float(prev_stats['median_sitasi']), 1) if prev_stats['median_sitasi'] else 0
                }
                print(f"📊 Previous stats: {previous_values}")
        
        return jsonify({
            'success': True,
            'data': {
                'totalPublikasi': stats['total_publikasi'] or 0,
                'totalSitasi': int(stats['total_sitasi']) if stats['total_sitasi'] else 0,
                'avgSitasi': round(float(stats['avg_sitasi']), 1) if stats['avg_sitasi'] else 0,
                'medianSitasi': round(float(stats['median_sitasi']), 1) if stats['median_sitasi'] else 0,
                'previousDate': previous_date.strftime('%d/%m/%Y') if previous_date else None,  # ✅ TAMBAHAN
                'previousValues': previous_values  # ✅ TAMBAHAN
            }
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Scholar Publikasi stats error:\n", error_details)
        logger.error(f"Get Scholar publikasi stats error: {e}\n{error_details}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({'success': False, 'error': 'Failed to fetch Scholar publikasi statistics'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

@app.route('/api/scholar/publikasi/export', methods=['GET'])
@token_required
def export_scholar_publikasi(current_user_id):
    """Export Google Scholar publikasi data to Excel"""
    conn = None
    cur = None
    
    try:
        search = request.args.get('search', '').strip()
        tipe_filter = request.args.get('tipe', '').strip().lower()
        year_start = request.args.get('year_start', '').strip()
        year_end = request.args.get('year_end', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        
        print(f"📥 Export Scholar Publikasi - search: '{search}', tipe: '{tipe_filter}', year_start: '{year_start}', year_end: '{year_end}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build base query (same as get_scholar_publikasi)
        where_clause = "WHERE p.v_sumber ILIKE %s"
        params = ['%Scholar%']
        
        if tipe_filter and tipe_filter != 'all':
            where_clause += " AND LOWER(p.v_jenis) = %s"
            params.append(tipe_filter)
        
        if year_start:
            where_clause += " AND CAST(p.v_tahun_publikasi AS INTEGER) >= %s"
            params.append(int(year_start))
        
        if year_end:
            where_clause += " AND CAST(p.v_tahun_publikasi AS INTEGER) <= %s"
            params.append(int(year_end))
        
        if search:
            where_clause += """ AND (
                LOWER(p.v_judul) LIKE LOWER(%s) OR
                LOWER(p.v_authors) LIKE LOWER(%s) OR
                LOWER(p.v_publisher) LIKE LOWER(%s)
            )"""
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        # Build faculty/department filter
        jurusan_filter = ""
        jurusan_params = []
        if department:
            jurusan_filter = "AND LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            jurusan_params.append(department.lower())
        elif faculty:
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    jurusan_params.append(f"%{dept.lower()}%")
                jurusan_filter = f"AND ({' OR '.join(like_conditions)})"
        
        # CTE (same as get_scholar_publikasi)
        latest_publikasi_cte = f"""
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                {where_clause}
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            ),
            publikasi_with_jurusan AS (
                SELECT 
                    p.v_id_publikasi,
                    p.v_authors,
                    STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar) 
                        FILTER (WHERE dm.v_nama_homebase_unpar IS NOT NULL) as jurusan_names
                FROM latest_publikasi p
                CROSS JOIN LATERAL (
                    SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
                ) authors
                LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
                    AND d.v_id_googlescholar IS NOT NULL 
                    AND TRIM(d.v_id_googlescholar) <> ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs)
                    {jurusan_filter}
                GROUP BY p.v_id_publikasi, p.v_authors
            )
        """
        
        cte_params = params + jurusan_params
        
        # Get all data without pagination
        if jurusan_filter:
            data_query = f"""
                {latest_publikasi_cte}
                SELECT
                    COALESCE(NULLIF(TRIM(p.v_authors), ''), 'N/A') AS authors,
                    COALESCE(pj.jurusan_names, 'N/A') AS v_nama_jurusan,
                    p.v_judul,
                    p.v_jenis AS tipe,
                    p.v_tahun_publikasi,
                    COALESCE(j.v_nama_jurnal, pr.v_nama_konferensi, 'N/A') AS venue,
                    COALESCE(p.v_publisher, '') AS publisher,
                    COALESCE(a.v_volume, '') AS volume,
                    COALESCE(a.v_issue, '') AS issue,
                    COALESCE(a.v_pages, '') AS pages,
                    COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                    p.t_tanggal_unduh,
                    p.v_link_url
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_jurusan pj ON p.v_id_publikasi = pj.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                WHERE pj.jurusan_names IS NOT NULL AND pj.jurusan_names != ''
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
            """
        else:
            data_query = f"""
                {latest_publikasi_cte}
                SELECT
                    COALESCE(NULLIF(TRIM(p.v_authors), ''), 'N/A') AS authors,
                    COALESCE(pj.jurusan_names, 'N/A') AS v_nama_jurusan,
                    p.v_judul,
                    p.v_jenis AS tipe,
                    p.v_tahun_publikasi,
                    COALESCE(j.v_nama_jurnal, pr.v_nama_konferensi, 'N/A') AS venue,
                    COALESCE(p.v_publisher, '') AS publisher,
                    COALESCE(a.v_volume, '') AS volume,
                    COALESCE(a.v_issue, '') AS issue,
                    COALESCE(a.v_pages, '') AS pages,
                    COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                    p.t_tanggal_unduh,
                    p.v_link_url
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_jurusan pj ON p.v_id_publikasi = pj.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
            """
        
        cur.execute(data_query, cte_params)
        publikasi_data = cur.fetchall()
        
        # Convert to DataFrame
        df = pd.DataFrame(publikasi_data)
        
        # Create vol_issue column
        if 'volume' in df.columns and 'issue' in df.columns:
            df['vol_issue'] = df.apply(
                lambda row: f"Vol {row['volume']}, Issue {row['issue']}" 
                if row['volume'] and row['issue'] 
                else (f"Vol {row['volume']}" if row['volume'] else (f"Issue {row['issue']}" if row['issue'] else '')),
                axis=1
            )
        
        # Rename columns to Indonesian
        column_mapping = {
            'authors': 'Author',
            'v_nama_jurusan': 'Jurusan',
            'v_judul': 'Judul Publikasi',
            'tipe': 'Tipe',
            'v_tahun_publikasi': 'Tahun',
            'venue': 'Venue/Jurnal',
            'publisher': 'Publisher',
            'vol_issue': 'Vol/Issue',
            'pages': 'Pages',
            'n_total_sitasi': 'Total Sitasi',
            't_tanggal_unduh': 'Tanggal Unduh',
            'v_link_url': 'Link URL'
        }
        
        # Select and rename columns
        available_columns = [col for col in column_mapping.keys() if col in df.columns]
        df_export = df[available_columns].rename(columns=column_mapping)
        
        # Format tanggal
        if 'Tanggal Unduh' in df_export.columns:
            df_export['Tanggal Unduh'] = pd.to_datetime(df_export['Tanggal Unduh'], errors='coerce').dt.strftime('%Y-%m-%d')
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_export.to_excel(writer, index=False, sheet_name='Google Scholar Publikasi')
        
        output.seek(0)
        
        # Create response
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response.headers['Content-Disposition'] = f'attachment; filename=scholar_publikasi_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        
        return response
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Export Scholar Publikasi error:\n", error_details)
        logger.error(f"Export Scholar publikasi error: {e}\n{error_details}")
        return jsonify({'error': 'Failed to export Scholar publikasi data'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# Scraping Routes
@app.route('/api/scraping/sinta', methods=['POST'])
@token_required
def scrape_sinta(current_user_id):
    """Run SINTA scraping"""
    try:
        data = request.get_json()
        if not data or not data.get('username') or not data.get('password'):
            return jsonify({'error': 'SINTA credentials required'}), 400
        
        username = data['username']
        password = data['password']
        scraping_type = data.get('type', 'dosen')
        
        logger.info(f"Starting SINTA scraping - Type: {scraping_type}, User: {current_user_id}")
        
        # Import and run appropriate scraper
        if scraping_type == 'dosen':
            # Run Sinta_Dosen.py
            result = run_scraper_script('scrapers/sinta_dosen.py', {
                'username': username,
                'password': password
            })
        elif scraping_type == 'publikasi':
            # Run publication scrapers sequentially
            scrapers = [
                'scrapers/sinta_garuda.py',
                'scrapers/sinta_googlescholar.py',
                'scrapers/sinta_scopus.py'
            ]
            results = []
            for scraper in scrapers:
                result = run_scraper_script(scraper, {
                    'username': username,
                    'password': password
                })
                results.append({
                    'scraper': scraper.split('/')[-1],
                    'result': result
                })
            
            return jsonify({
                'message': 'SINTA publikasi scraping completed',
                'results': results
            }), 200
        
        return jsonify({
            'message': f'SINTA {scraping_type} scraping completed',
            'result': result
        }), 200
        
    except Exception as e:
        logger.error(f"SINTA scraping error: {e}")
        return jsonify({'error': f'Scraping failed: {str(e)}'}), 500

@app.route('/api/scraping/scholar', methods=['POST'])
@token_required
def scrape_scholar(current_user_id):
    """Run Google Scholar scraping"""
    try:
        data = request.get_json() or {}
        scraping_type = data.get('type', 'dosen')
        
        logger.info(f"Starting Scholar scraping - Type: {scraping_type}, User: {current_user_id}")
        
        if scraping_type == 'dosen':
            # Run dosen_unpar.py
            result = run_scraper_script('scrapers/dosen_unpar.py')
        elif scraping_type == 'publikasi':
            # Run scrapingGS.py
            result = run_scraper_script('scrapers/scraping_gs.py')
        
        return jsonify({
            'message': f'Google Scholar {scraping_type} scraping completed',
            'result': result
        }), 200
        
    except Exception as e:
        logger.error(f"Scholar scraping error: {e}")
        return jsonify({'error': f'Scraping failed: {str(e)}'}), 500

def run_scraper_script(script_path, params=None):
    """Run a scraper script as subprocess"""
    try:
        # Check if script exists
        if not os.path.exists(script_path):
            return {
                'success': False,
                'error': f'Scraper script not found: {script_path}'
            }
        
        # Prepare environment variables for the script
        env = os.environ.copy()
        if params:
            env.update({
                'SINTA_USERNAME': params.get('username', ''),
                'SINTA_PASSWORD': params.get('password', '')
            })
        
        # Run the script
        result = subprocess.run([
            sys.executable, script_path
        ], capture_output=True, text=True, timeout=3600, env=env)  # 1 hour timeout
        
        return {
            'success': result.returncode == 0,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        }
        
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Scraping timeout (exceeded 1 hour)',
            'timeout': True
        }
    except Exception as e:
        logger.error(f"Error running scraper {script_path}: {e}")
        return {
            'success': False,
            'error': str(e)
        }


# Health check endpoint
@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        if conn:
            conn.close()
            return jsonify({'status': 'healthy', 'database': 'connected'}), 200
        else:
            return jsonify({'status': 'unhealthy', 'database': 'disconnected'}), 503
    except Exception as e:
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 503

# Database info endpoint
@app.route('/api/database/info', methods=['GET'])
@token_required
def database_info(current_user_id):
    """Get database information"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get table information
        tables_info = []
        tables = [
            ('users', 'Users'),
            ('tmp_dosen_dt', 'Dosen'),
            ('stg_jurusan_mt', 'Jurusan'),
            ('stg_publikasi_tr', 'Publikasi'),
            ('stg_publikasi_dosen_dt', 'Publikasi-Dosen Relations'),
            ('stg_artikel_dr', 'Artikel Details'),
            ('stg_jurnal_mt', 'Jurnal')
        ]
        
        for table_name, display_name in tables:
            try:
                cur.execute(f"SELECT COUNT(*) as count FROM {table_name}")
                count = cur.fetchone()['count']
                tables_info.append({
                    'table': table_name,
                    'display_name': display_name,
                    'count': count
                })
            except Exception as e:
                tables_info.append({
                    'table': table_name,
                    'display_name': display_name,
                    'count': 0,
                    'error': str(e)
                })
        
        return jsonify({
            'database': DB_CONFIG['dbname'],
            'tables': tables_info
        }), 200
        
    except Exception as e:
        logger.error(f"Database info error: {e}")
        return jsonify({'error': 'Failed to get database info'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

# Error handlers
@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Endpoint not found'}), 404

@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({'error': 'Method not allowed'}), 405

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({'error': 'Internal server error'}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    logger.error(f"Unhandled exception: {e}")
    return jsonify({'error': 'An unexpected error occurred'}), 500

# Initialize database tables if they don't exist
def init_database():
    """Initialize database tables"""
    try:
        conn = get_db_connection()
        if not conn:
            logger.error("Cannot initialize database - connection failed")
            return False
        
        cur = conn.cursor()
        
        # Check if users table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'users'
            );
        """)
        
        if not cur.fetchone()[0]:
            logger.info("Creating users table...")
            cur.execute("""
                CREATE TABLE users (
                    v_id_user SERIAL PRIMARY KEY,
                    v_username VARCHAR(64) NOT NULL,
                    v_email VARCHAR(120) NOT NULL,
                    v_password_hash VARCHAR(256) NOT NULL,
                    f_is_admin BOOLEAN DEFAULT FALSE,
                    t_tanggal_bikin TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE UNIQUE INDEX idx_users_email ON users(v_email);
                CREATE UNIQUE INDEX idx_users_username ON users(v_username);
            """)
            conn.commit()
            logger.info("Users table created successfully")
        
        # Check if temp_dosenGS_scraping table exists
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_name = 'temp_dosengs_scraping'
            );
        """)
        
        if not cur.fetchone()[0]:
            logger.info("Creating temp_dosenGS_scraping table...")
            cur.execute("""
                CREATE TABLE temp_dosenGS_scraping (
                    v_id_dosen SERIAL PRIMARY KEY,
                    v_nama VARCHAR(255) NOT NULL,
                    v_link TEXT,
                    v_status VARCHAR(50) DEFAULT 'pending',
                    v_error_message TEXT,
                    t_last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX idx_dosengs_status ON temp_dosenGS_scraping(v_status);
                CREATE INDEX idx_dosengs_nama ON temp_dosenGS_scraping(v_nama);
            """)
            conn.commit()
            logger.info("temp_dosenGS_scraping table created successfully")
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False

if __name__ == '__main__':
    # Initialize database
    init_database()
    
    # Create scrapers directory if it doesn't exist
    os.makedirs('scrapers', exist_ok=True)
    
    # Log startup information
    logger.info("Starting ProDS Flask Application with SocketIO")
    logger.info(f"Database: {DB_CONFIG['dbname']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    logger.info(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    
    # Run with SocketIO
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    
    socketio.run(
        app,
        debug=debug_mode,
        host='0.0.0.0',
        port=int(os.environ.get('PORT', 5002)),
        allow_unsafe_werkzeug=True
    )