from flask import Flask, request, jsonify, session, make_response
from io import BytesIO
import pandas as pd
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
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

def _sanitize_excel_value(v):
    """
    openpyxl raises IllegalCharacterError if a cell contains control chars.
    Remove illegal characters from strings to keep export robust.
    """
    if v is None:
        return v
    if isinstance(v, str):
        # Replace illegal control characters with empty string
        return ILLEGAL_CHARACTERS_RE.sub("", v)
    return v

def sanitize_df_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """Apply Excel-safe sanitization across all object columns."""
    if df is None or df.empty:
        return df
    df = df.copy()
    obj_cols = df.select_dtypes(include=["object"]).columns
    for c in obj_cols:
        df[c] = df[c].map(_sanitize_excel_value)
    return df

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
             "origins": ["http://10.211.1.188:3000"],
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
    cors_allowed_origins=["http://10.211.1.188:3000"],
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

# Mapping Hardcode untuk Fallback (Jika API mapping DB gagal atau untuk query logika backend)
# Mapping disesuaikan dengan database, dari atribut fakultas dan v_nama_homebase_unpar
FACULTY_DEPT_MAP = {
    'Ekonomi': [
        'Akuntansi',
        'Doktor Ekonomi',
        'Ekonomi Pembangunan',
        'Magister Manajemen',
        'Manajemen'
    ],
    'Filsafat': [
        'Filsafat',
        'Magister Teologi',
        'Studi Humanitas'
    ],
    'Hukum': [
        'Doktor Hukum',
        'Hukum',
        'Magister Hukum'
    ],
    'Ilmu Sosial dan Ilmu Politik': [
        'Administrasi Bisnis',
        'Administrasi Publik',
        'Hubungan Internasional',
        'Magister Administrasi Bisnis',
        'Magister Hubungan Internasional',
        'Magister Ilmu Sosial'
    ],
    'Kedokteran': [
        'Kedokteran - Pendidikan Dokter',
        'Kedokteran - Pendidikan Profesi Dokter'
    ],
    'Keguruan dan Ilmu Pendidikan': [
        'Magister Pendidikan Ilmu Pengetahuan Alam',
        'Pendidikan Bahasa Inggris',
        'Pendidikan Fisika',
        'Pendidikan Guru Sekolah Dasar',
        'Pendidikan Kimia', # TRIM() di backend akan menangani spasi di database
        'Pendidikan Matematika',
        'Pendidikan TIK'
    ],
    'Sains': [
        'Fisika',
        'Informatika',
        'Matematika'
    ],
    'Teknik': [
        'Arsitektur',
        'Doktor Arsitektur',
        'Doktor Teknik Sipil',
        'Magister Arsitektur',
        'Magister Teknik Sipil',
        'Program Profesi Insinyur',
        'Teknik Sipil'
    ],
    'Teknologi Rekayasa': [
        'Magister Teknik Industri',
        'Magister Teknik Kimia',
        'Teknik Elektro Konsentrasi Mekatronika',
        'Teknik Industri',
        'Teknik Kimia'
    ],
    'Vokasi': [
        'D3 Manajemen',
        'Program Studi Agribisnis Pangan',
        'Sarjana Terapan Bisnis Kreatif',
        'Sarjana Terapan Teknologi Rekayasa Pangan'
    ]
}

@app.route('/api/dashboard/mapping', methods=['GET'])
@token_required
def get_dashboard_mapping(current_user_id):
    """
    Mengambil mapping Fakultas -> Prodi langsung dari tabel datamaster.
    """
    try:
        conn = get_db_connection()
        # Pastikan menggunakan psycopg2.extras
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Query dengan ORDER BY berdasarkan kode_fakultas dan kode_prodi
        # Gunakan GROUP BY untuk menghindari masalah DISTINCT dengan ORDER BY
        query = """
            SELECT 
                TRIM(fakultas) as faculty, 
                TRIM(v_nama_homebase_unpar) as department
            FROM datamaster
            WHERE fakultas IS NOT NULL 
              AND fakultas != ''
              AND v_nama_homebase_unpar IS NOT NULL 
              AND v_nama_homebase_unpar != ''
            GROUP BY TRIM(fakultas), TRIM(v_nama_homebase_unpar), kode_fakultas, kode_prodi
            ORDER BY 
                COALESCE(NULLIF(TRIM(kode_fakultas), ''), 'ZZZ'),
                COALESCE(NULLIF(TRIM(kode_prodi), ''), 'ZZZ'),
                TRIM(fakultas),
                TRIM(v_nama_homebase_unpar);
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        # Build mapping dengan urutan berdasarkan kode_fakultas dan kode_prodi
        # Gunakan OrderedDict atau dict biasa (ES6+ object mempertahankan insertion order)
        mapping = {}
        for row in rows:
            fac = row['faculty']
            dept = row['department']
            
            if fac not in mapping:
                mapping[fac] = []
            
            # Append department (sudah terurut berdasarkan kode_prodi dari query)
            mapping[fac].append(dept)
            
        return jsonify({
            'success': True,
            'data': mapping
        }), 200

    except Exception as e:
        print("❌ Error fetching mapping:", e)
        import traceback
        error_details = traceback.format_exc()
        print(f"❌ Traceback: {error_details}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'cur' in locals() and cur:
            try:
                cur.close()
            except:
                pass
        if 'conn' in locals() and conn:
            try:
                conn.close()
            except:
                pass

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
        
        # Get database connection first (needed for mapping query if filtering by faculties)
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        faculty_filter = ""
        ORIGINAL_FACULTY_PARAMS = []

        has_departments_selected = selected_departments and len(selected_departments) > 0
        has_faculties_selected = selected_faculties and len(selected_faculties) > 0

        if has_departments_selected:
            placeholders = ', '.join(['%s'] * len(selected_departments))
            faculty_filter = f" AND LOWER(TRIM(dm.v_nama_homebase_unpar)) IN ({placeholders}) "
            ORIGINAL_FACULTY_PARAMS = [d.lower() for d in selected_departments]

        elif has_faculties_selected:
            # Priority 2: User memilih Fakultas -> Expand ke semua Jurusan
            print(f"🔍 [FILTER] User selected {len(selected_faculties)} faculties: {selected_faculties}")
            print(f"🔍 [FILTER] Expanding faculties to all departments...")
            all_target_depts = []
            
            # Ambil mapping dari database (dengan urutan berdasarkan kode_fakultas dan kode_prodi)
            # Gunakan subquery untuk menghindari masalah DISTINCT dengan ORDER BY
            mapping_query = """
                SELECT 
                    faculty, 
                    department
                FROM (
                    SELECT DISTINCT 
                        TRIM(fakultas) as faculty, 
                        TRIM(v_nama_homebase_unpar) as department,
                        COALESCE(NULLIF(TRIM(kode_fakultas), ''), 'ZZZ') as kode_fakultas_sort,
                        COALESCE(NULLIF(TRIM(kode_prodi), ''), 'ZZZ') as kode_prodi_sort
                    FROM datamaster
                    WHERE fakultas IS NOT NULL 
                      AND fakultas != ''
                      AND v_nama_homebase_unpar IS NOT NULL 
                      AND v_nama_homebase_unpar != ''
                ) subquery
                ORDER BY 
                    kode_fakultas_sort,
                    kode_prodi_sort,
                    faculty,
                    department
            """
            temp_cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            temp_cur.execute(mapping_query)
            mapping_rows = temp_cur.fetchall()
            temp_cur.close()
            
            # Build mapping dict dari database
            db_faculty_dept_map = {}
            for row in mapping_rows:
                fac = row['faculty']
                dept = row['department']
                if fac not in db_faculty_dept_map:
                    db_faculty_dept_map[fac] = []
                db_faculty_dept_map[fac].append(dept)
            
            print(f"🔍 [FILTER] Loaded {len(db_faculty_dept_map)} faculties from database")
            print(f"🔍 [FILTER] Available faculties: {list(db_faculty_dept_map.keys())[:5]}")
            
            # Gunakan mapping dari database, fallback ke hardcoded jika perlu
            for faculty in selected_faculties:
                print(f"🔍 [FILTER] Processing faculty: '{faculty}'")
                depts = None
                
                # 1. Coba ambil dari database mapping (Exact Match - case sensitive)
                depts = db_faculty_dept_map.get(faculty)
                if depts:
                    print(f"  ✅ Found exact match in DB: {len(depts)} departments")
                
                # 2. Jika tidak ketemu, coba dengan prefix "Fakultas "
                if not depts:
                    depts = db_faculty_dept_map.get(f"Fakultas {faculty}")
                    if depts:
                        print(f"  ✅ Found with 'Fakultas' prefix: {len(depts)} departments")
                
                # 3. Jika masih tidak ketemu, coba case-insensitive match
                if not depts:
                    for key, val in db_faculty_dept_map.items():
                        if key.lower() == faculty.lower() or faculty.lower() == key.lower():
                            depts = val
                            print(f"  ✅ Found case-insensitive match: '{key}' -> {len(depts)} departments")
                            break
                
                # 4. Jika masih tidak ketemu, coba partial match di database mapping
                if not depts:
                    for key, val in db_faculty_dept_map.items():
                        if faculty.lower() in key.lower() or key.lower() in faculty.lower(): 
                            depts = val
                            print(f"  ✅ Found partial match: '{key}' -> {len(depts)} departments")
                            break
                
                # 5. Fallback ke hardcoded mapping jika database tidak punya
                if not depts:
                    depts = FACULTY_DEPT_MAP.get(faculty)
                    if depts:
                        print(f"  ⚠️ Using hardcoded mapping: {len(depts)} departments")
                    if not depts:
                        depts = FACULTY_DEPT_MAP.get(f"Fakultas {faculty}")
                        if depts:
                            print(f"  ⚠️ Using hardcoded mapping with prefix: {len(depts)} departments")
                    if not depts:
                        for key, val in FACULTY_DEPT_MAP.items():
                            if faculty.lower() in key.lower(): 
                                depts = val
                                print(f"  ⚠️ Using hardcoded partial match: '{key}' -> {len(depts)} departments")
                                break
                            
                if depts:
                    all_target_depts.extend(depts)
                    print(f"  ✅ Added {len(depts)} departments for faculty '{faculty}'")
                else:
                    print(f"  ❌ Warning: Could not map faculty '{faculty}' to any departments")
                    print(f"  🔍 Available faculty keys in DB: {list(db_faculty_dept_map.keys())}")
            
            # Hapus duplikat jurusan (preserve order)
            seen = set()
            unique_depts = []
            for dept in all_target_depts:
                if dept not in seen:
                    seen.add(dept)
                    unique_depts.append(dept)
            all_target_depts = unique_depts
            
            if all_target_depts:
                placeholders = ', '.join(['%s'] * len(all_target_depts))
                faculty_filter = f" AND LOWER(TRIM(dm.v_nama_homebase_unpar)) IN ({placeholders}) "
                ORIGINAL_FACULTY_PARAMS = [d.lower() for d in all_target_depts]
                print(f"✅ [FILTER] Successfully mapped {len(selected_faculties)} faculties to {len(all_target_depts)} unique departments")
                print(f"🔍 [FILTER] Sample departments: {all_target_depts[:5]}")
            else:
                faculty_filter = ""
                ORIGINAL_FACULTY_PARAMS = []
                print(f"⚠️ [FILTER] No departments found for selected faculties, filter will not be applied")
        
        has_filter = bool(faculty_filter)

        print(f"📊 Dashboard Stats - Raw faculty param: {request.args.get('faculty', '')}")
        print(f"📊 Dashboard Stats - Decoded faculty param: {faculty_param}")
        print(f"📊 Dashboard Stats - faculties: {selected_faculties}, departments: {selected_departments}")
        print(f"📊 Has filter: {bool(selected_departments or selected_faculties)}")
        
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
        
        # Get total dosen aktif (dosen yang punya fakultas/jurusan mapping)
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
                        AND TRIM(dm.v_nama_homebase_unpar) != ''
                        AND dm.fakultas IS NOT NULL
                        AND TRIM(dm.fakultas) != '' {faculty_filter}
                """
                print(f"🔍 [DEBUG] Total Dosen Aktif Query: {query}")
                print(f"🔍 [DEBUG] Total Dosen Aktif Params: {list(ORIGINAL_FACULTY_PARAMS)}")
                
                # Validate parameter count
                placeholder_count = query.count('%s')
                params_list = list(ORIGINAL_FACULTY_PARAMS)
                if placeholder_count != len(params_list):
                    raise ValueError(f"Total Dosen Aktif: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
                
                cur.execute(query, params_list)
            except Exception as e:
                print(f"❌ Error in Total Dosen Aktif query: {e}")
                import traceback
                print(f"❌ Traceback: {traceback.format_exc()}")
                raise
        else:
            cur.execute(f"""
                {latest_dosen_all_cte}
                SELECT COUNT(DISTINCT d.v_id_dosen) as total
                FROM latest_dosen_all d
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND dm.fakultas IS NOT NULL
                    AND TRIM(dm.fakultas) != ''
            """)
        
        total_dosen_aktif = cur.fetchone()['total']
        
        # Get total publikasi tersitasi (only publikasi with citations > 0)
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
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND COALESCE(p.n_total_sitasi, 0) > 0 {faculty_filter}
            """
            print(f"🔍 [DEBUG] Total Publikasi Tersitasi Query: {query}")
            print(f"🔍 [DEBUG] Total Publikasi Tersitasi Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"Total Publikasi Tersitasi: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
        else:
            cur.execute(f"""
                {latest_publikasi_cte}
                SELECT COUNT(DISTINCT p.v_id_publikasi) as total
                FROM latest_publikasi p
                WHERE COALESCE(p.n_total_sitasi, 0) > 0
            """)
        
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
        
        # Get h-index Scopus stats (with faculty filter)
        if faculty_filter:
            query = f"""
                {latest_dosen_all_cte}
                SELECT
                    COALESCE(AVG(d.n_h_index_scopus), 0) as avg_h_scopus,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.n_h_index_scopus), 0) as median_h_scopus
                FROM latest_dosen_all d
                INNER JOIN datamaster dm ON (
                    (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                    OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                )
                WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                    AND TRIM(dm.v_nama_homebase_unpar) != ''
                    AND COALESCE(d.n_h_index_scopus, 0) > 0 {faculty_filter}
            """
            print(f"🔍 [DEBUG] H-Index Scopus Query: {query}")
            print(f"🔍 [DEBUG] H-Index Scopus Params: {list(ORIGINAL_FACULTY_PARAMS)}")
            
            # Validate parameter count
            placeholder_count = query.count('%s')
            params_list = list(ORIGINAL_FACULTY_PARAMS)
            if placeholder_count != len(params_list):
                raise ValueError(f"H-Index Scopus: Parameter count mismatch: query has {placeholder_count} placeholders but {len(params_list)} params provided")
            
            cur.execute(query, params_list)
        else:
            cur.execute(f"""
                {latest_dosen_all_cte}
                SELECT
                    COALESCE(AVG(n_h_index_scopus), 0) as avg_h_scopus,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n_h_index_scopus), 0) as median_h_scopus
                FROM latest_dosen_all
                WHERE COALESCE(n_h_index_scopus, 0) > 0
            """)
        
        h_stats_scopus = cur.fetchone()
        avg_h_index_scopus = h_stats_scopus['avg_h_scopus']
        median_h_index_scopus = h_stats_scopus['median_h_scopus']
        
        # ===================================
        # PUBLIKASI BY YEAR
        # ===================================

        # kondisi-kondisi yang ada:
        # 1. tidak memilih filter apapun, maka satu garis merepresentasikan seluruh fakultas serta seluruh jurusan dari masing-masing fakultas
        # 2. memilih satu fakultas tanpa memilih jurusan, maka satu garis merepresentasikan seluruh jurusan dari fakultas tersebut
        # 3. memilih satu fakultas dan satu jurusan, maka satu garis merepresentasikan jurusan tersebut
        # 4. memilih satu fakultas dan lebih dari satu jurusan, maka setiap garis merepresentasikan setiap jurusan
        # 5. memilih lebih dari satu fakultas tanpa memilih jurusan, maka setiap garis merepresentasikan setiap fakultas
        # 6. memilih lebih dari satu fakultas dan lebih dari satu jurusan, maka setiap garis merepresentasikan setiap jurusan

        current_year = datetime.now().year
        start_year = current_year - 15

        publikasi_by_year = []
        try:
            # -----------------------------------------------------------
            # PERBAIKAN LOGIKA BOOLEAN:
            # Ubah pengecekan dari "> 1" menjadi "> 0"
            # Agar '1 Fakultas' juga masuk ke logika Grouping by Faculty (Scenario B)
            # -----------------------------------------------------------
            has_faculties_selected = selected_faculties and len(selected_faculties) > 0
            
            # Debug info
            print(f"🔍 [LOGIC CHECK] Depts Selected: {has_departments_selected}, Faculties Selected: {has_faculties_selected}")
            
            # ---------------------------------------------------------
            # SKENARIO A: FILTER BERBASIS JURUSAN (Priority 1)
            # (Kondisi 3, 4, 6) -> Grouping per Department
            # ---------------------------------------------------------
            if has_departments_selected:
                print(f"🔍 [QUERY] Using DEPARTMENT Grouping")
                
                query = f"""
                    WITH year_range AS (
                        SELECT generate_series(%s, %s) as year_num
                    ),
                    filtered_data AS (
                        SELECT 
                            p.v_tahun_publikasi,
                            TRIM(dm.v_nama_homebase_unpar) as department,
                            p.v_sumber,
                            p.v_id_publikasi
                        FROM stg_publikasi_tr p
                        JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                        JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)) OR 
                            (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                        {faculty_filter}
                    )
                    SELECT 
                        yr.year_num::TEXT as v_tahun_publikasi,
                        fd.department, 
                        COUNT(DISTINCT CASE WHEN fd.v_sumber ILIKE '%%Sinta%%' THEN fd.v_id_publikasi END) as count_sinta,
                        COUNT(DISTINCT CASE WHEN fd.v_sumber ILIKE '%%Scholar%%' THEN fd.v_id_publikasi END) as count_gs
                    FROM year_range yr
                    LEFT JOIN filtered_data fd ON CAST(fd.v_tahun_publikasi AS TEXT) = CAST(yr.year_num AS TEXT)
                    GROUP BY yr.year_num, fd.department
                    ORDER BY yr.year_num, fd.department
                """
                query_params = [start_year, current_year] + list(ORIGINAL_FACULTY_PARAMS)

            # ---------------------------------------------------------
            # SKENARIO B: FILTER FAKULTAS (1 ATAU LEBIH) TANPA JURUSAN (Priority 2)
            # (Kondisi 2 & 5) -> Grouping per Faculty
            # ---------------------------------------------------------
            elif has_faculties_selected: # Pastikan variabel ini True jika len > 0
                print(f"🔍 [QUERY] Using FACULTY Grouping (Smart Mapping)")
                
                faculty_cases = []
                for faculty in selected_faculties:
                    # --- LOGIKA SMART LOOKUP YANG SAMA ---
                    depts = FACULTY_DEPT_MAP.get(faculty)
                    if not depts: depts = FACULTY_DEPT_MAP.get(f"Fakultas {faculty}")
                    if not depts:
                        for key, val in FACULTY_DEPT_MAP.items():
                            if faculty in key: 
                                depts = val
                                break
                    # -------------------------------------
                    
                    if depts:
                        # Mapping balik jurusan ke nama input user ('faculty')
                        dept_conditions = " OR ".join([f"LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE '%%{dept.lower()}%%'" for dept in depts])
                        faculty_cases.append(f"WHEN ({dept_conditions}) THEN '{faculty}'")
                
                faculty_case_sql = "\n".join(faculty_cases) if faculty_cases else "WHEN 1=0 THEN NULL"
                
                # Placeholder untuk CTE target_faculties
                fac_placeholders = ', '.join(['%s'] * len(selected_faculties))

                query = f"""
                    WITH year_range AS (
                        SELECT generate_series(%s, %s) as year_num
                    ),
                    target_faculties AS (
                        SELECT unnest(ARRAY[{fac_placeholders}]) as faculty_name
                    ),
                    mapped_data AS (
                        SELECT 
                            p.v_tahun_publikasi,
                            p.v_sumber,
                            p.v_id_publikasi,
                            CASE
                                {faculty_case_sql}
                                ELSE NULL
                            END as faculty
                        FROM stg_publikasi_tr p
                        JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                        JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)) OR 
                            (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL
                        {faculty_filter}
                    )
                    SELECT 
                        yr.year_num::TEXT as v_tahun_publikasi,
                        tf.faculty_name as faculty,
                        COUNT(DISTINCT CASE WHEN md.v_sumber ILIKE '%%Sinta%%' THEN md.v_id_publikasi END) as count_sinta,
                        COUNT(DISTINCT CASE WHEN md.v_sumber ILIKE '%%Scholar%%' THEN md.v_id_publikasi END) as count_gs
                    FROM year_range yr
                    CROSS JOIN target_faculties tf
                    LEFT JOIN mapped_data md ON CAST(md.v_tahun_publikasi AS TEXT) = CAST(yr.year_num AS TEXT) 
                        AND md.faculty = tf.faculty_name
                    GROUP BY yr.year_num, tf.faculty_name
                    ORDER BY yr.year_num, tf.faculty_name
                """
                
                query_params = [start_year, current_year] + list(selected_faculties) + list(ORIGINAL_FACULTY_PARAMS)

            # ---------------------------------------------------------
            # SKENARIO C: TIDAK ADA FILTER (Priority 3)
            # (Kondisi 1) -> 1 Garis Total Universitas
            # ---------------------------------------------------------
            else:
                print(f"🔍 [QUERY] Using SIMPLE AGGREGATION (Total University)")
                
                query = f"""
                    WITH year_range AS (
                        SELECT generate_series(%s, %s) as year_num
                    ),
                    filtered_data AS (
                        SELECT 
                            p.v_tahun_publikasi,
                            p.v_sumber,
                            p.v_id_publikasi
                        FROM stg_publikasi_tr p
                        JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                        JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                        JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)) OR 
                            (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL
                        {faculty_filter} 
                    )
                    SELECT 
                        yr.year_num::TEXT as v_tahun_publikasi,
                        COUNT(DISTINCT CASE WHEN fd.v_sumber ILIKE '%%Sinta%%' THEN fd.v_id_publikasi END) as count_sinta,
                        COUNT(DISTINCT CASE WHEN fd.v_sumber ILIKE '%%Scholar%%' THEN fd.v_id_publikasi END) as count_gs
                    FROM year_range yr
                    LEFT JOIN filtered_data fd ON CAST(fd.v_tahun_publikasi AS TEXT) = CAST(yr.year_num AS TEXT)
                    GROUP BY yr.year_num
                    ORDER BY yr.year_num
                """
                query_params = [start_year, current_year] + list(ORIGINAL_FACULTY_PARAMS)

            # Eksekusi Query
            cur.execute(query, query_params)
            publikasi_by_year = [dict(row) for row in cur.fetchall()]
            
            if publikasi_by_year:
                print(f"✅ Data fetched: {len(publikasi_by_year)} rows")
            else:
                print("⚠️ No data fetched")

        except Exception as e:
            print(f"❌ Error executing publikasi by year query: {e}")
            import traceback
            print(traceback.format_exc())
            publikasi_by_year = []
        
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
                
                # Get previous total dosen aktif
                if faculty_filter:
                    prev_dosen_aktif_query = f"""
                        {previous_dosen_all_cte}
                        SELECT COUNT(DISTINCT d.v_id_dosen) as total
                        FROM previous_dosen_all d
                        INNER JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                            AND TRIM(dm.v_nama_homebase_unpar) != ''
                            AND dm.fakultas IS NOT NULL
                            AND TRIM(dm.fakultas) != '' {faculty_filter}
                    """
                    cur.execute(prev_dosen_aktif_query, [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"""
                        {previous_dosen_all_cte}
                        SELECT COUNT(DISTINCT d.v_id_dosen) as total
                        FROM previous_dosen_all d
                        INNER JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                            AND TRIM(dm.v_nama_homebase_unpar) != ''
                            AND dm.fakultas IS NOT NULL
                            AND TRIM(dm.fakultas) != ''
                    """, [previous_date])
                prev_total_dosen_aktif = cur.fetchone()['total'] or 0
                
                # Get previous total publikasi tersitasi (only publikasi with citations > 0)
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
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL
                            AND COALESCE(p.n_total_sitasi, 0) > 0 {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"""
                        {previous_publikasi_cte}
                        SELECT COUNT(DISTINCT p.v_id_publikasi) as total
                        FROM previous_publikasi p
                        WHERE COALESCE(p.n_total_sitasi, 0) > 0
                    """, [previous_date])
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
                
                # Get previous h-index Scopus stats
                if faculty_filter:
                    query = f"""
                        {previous_dosen_all_cte}
                        SELECT
                            COALESCE(AVG(d.n_h_index_scopus), 0) as avg_h_scopus,
                            COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY d.n_h_index_scopus), 0) as median_h_scopus
                        FROM previous_dosen_all d
                        INNER JOIN datamaster dm ON (
                            (d.v_id_sinta IS NOT NULL AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta))
                            OR (d.v_id_googlescholar IS NOT NULL AND TRIM(d.v_id_googlescholar) = TRIM(dm.id_gs))
                        )
                        WHERE dm.v_nama_homebase_unpar IS NOT NULL 
                            AND TRIM(dm.v_nama_homebase_unpar) != ''
                            AND COALESCE(d.n_h_index_scopus, 0) > 0 {faculty_filter}
                    """
                    cur.execute(query, [previous_date] + list(ORIGINAL_FACULTY_PARAMS))
                else:
                    cur.execute(f"""
                        {previous_dosen_all_cte}
                        SELECT
                            COALESCE(AVG(n_h_index_scopus), 0) as avg_h_scopus,
                            COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n_h_index_scopus), 0) as median_h_scopus
                        FROM previous_dosen_all
                        WHERE COALESCE(n_h_index_scopus, 0) > 0
                    """, [previous_date])
                
                h_stats_scopus_prev = cur.fetchone()
                prev_avg_h_index_scopus = float(h_stats_scopus_prev['avg_h_scopus']) if h_stats_scopus_prev and h_stats_scopus_prev['avg_h_scopus'] else 0.0
                prev_median_h_index_scopus = float(h_stats_scopus_prev['median_h_scopus']) if h_stats_scopus_prev and h_stats_scopus_prev['median_h_scopus'] else 0.0
                
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
                    'total_dosen_aktif': prev_total_dosen_aktif,
                    'total_publikasi': prev_total_publikasi,
                    'total_sitasi': prev_total_sitasi,
                    'total_sitasi_gs': prev_total_sitasi_gs,
                    'total_sitasi_gs_sinta': prev_total_sitasi_gs_sinta,
                    'total_sitasi_scopus': prev_total_sitasi_scopus,
                    'avg_h_index': prev_avg_h_index,
                    'median_h_index': prev_median_h_index,
                    'avg_h_index_scopus': prev_avg_h_index_scopus,
                    'median_h_index_scopus': prev_median_h_index_scopus,
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
                'total_dosen_aktif': total_dosen_aktif or 0,
                'total_publikasi': total_publikasi or 0,
                'total_sitasi': total_sitasi or 0,
                'total_sitasi_gs': total_sitasi_gs or 0,
                'total_sitasi_gs_sinta': total_sitasi_gs_sinta or 0,
                'total_sitasi_scopus': total_sitasi_scopus or 0,
                'avg_h_index': float(avg_h_index) if avg_h_index else 0.0,
                'median_h_index': float(median_h_index) if median_h_index else 0.0,
                'avg_h_index_scopus': float(avg_h_index_scopus) if avg_h_index_scopus else 0.0,
                'median_h_index_scopus': float(median_h_index_scopus) if median_h_index_scopus else 0.0,
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
        faculties = sorted(list(FACULTY_DEPT_MAP.keys()))
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
        
        departments = FACULTY_DEPT_MAP.get(faculty, [])
        
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
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
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
                dm.v_nama_homebase_unpar AS v_nama_jurusan,
                dm.fakultas AS v_nama_fakultas
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
            
            # # Add faculty information to each record based on department
            # for dosen in sinta_data:
            #     department_name = dosen.get('v_nama_jurusan')
            #     if department_name:
            #         faculty_name = get_faculty_from_department(department_name)
            #         dosen['v_nama_fakultas'] = faculty_name
            #     else:
            #         dosen['v_nama_fakultas'] = None
            
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
            faculty_filter = "AND LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            faculty_params.append(department.lower())
        elif faculty:
            # Only faculty selected, filter by all departments in that faculty
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
            if departments_in_faculty:
                # Create LIKE conditions for each department
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    faculty_params.append(f"%{dept.lower()}%")
                
                faculty_filter = f"AND ({' OR '.join(like_conditions)})"
                print(f"🏛️ Stats filtering by faculty: {faculty} with {len(departments_in_faculty)} departments")
        else:
            faculty_filter = ""
        
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
                {faculty_filter if faculty_filter else ""}
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
                faculties = sorted(list(FACULTY_DEPT_MAP.keys()))
            
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
            faculties = sorted(list(FACULTY_DEPT_MAP.keys()))
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
        faculties = sorted(list(FACULTY_DEPT_MAP.keys()))
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
    """Get list of departments in a faculty with SINTA dosen (FIXED LOOKUP)"""
    conn = None
    cur = None
    
    try:
        faculty = request.args.get('faculty', '').strip()
        
        # ============================================================
        # 1. SMART LOOKUP: Cocokkan input frontend dengan Mapping DB
        # ============================================================
        
        # Coba 1: Exact Match (Misal frontend kirim "Ekonomi")
        valid_departments = FACULTY_DEPT_MAP.get(faculty, [])
        
        # Coba 2: Jika kosong, coba buang kata "Fakultas " (Misal frontend kirim "Fakultas Ekonomi")
        if not valid_departments:
            clean_name = faculty.replace('Fakultas ', '').strip()
            valid_departments = FACULTY_DEPT_MAP.get(clean_name, [])
            
        # Coba 3: Special Case untuk FTIS / Sains
        if not valid_departments:
            if 'Teknologi Informasi' in faculty or 'FTIS' in faculty:
                valid_departments = FACULTY_DEPT_MAP.get('Sains', [])

        print(f"🔍 Lookup Faculty: Input='{faculty}' -> Mapped to {len(valid_departments)} departments")

        if not faculty:
            return jsonify({'error': 'Faculty parameter is required'}), 400
        
        # Jika tetap tidak ketemu mappingnya, kembalikan kosong agar tidak error
        if not valid_departments:
            return jsonify({'success': True, 'data': {'departments': []}}), 200

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': True, 'data': {'departments': sorted(valid_departments)}}), 200
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # 2. Ambil jurusan yang ADA DATANYA di database (SINTA)
            # Kita filter hanya jurusan yang valid untuk fakultas tersebut
            placeholders = ', '.join(['%s'] * len(valid_departments))
            query = f"""
                SELECT DISTINCT 
                    TRIM(dm.v_nama_homebase_unpar) as jurusan
                FROM datamaster dm
                WHERE dm.id_sinta IS NOT NULL 
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    AND TRIM(dm.v_nama_homebase_unpar) IN ({placeholders})
                ORDER BY jurusan
            """
            
            cur.execute(query, tuple(valid_departments))
            results = cur.fetchall()
            
            available_departments = [row['jurusan'] for row in results if row['jurusan']]
            
            print(f"🏢 Found {len(available_departments)} active departments for {faculty}")
            
            return jsonify({
                'success': True,
                'data': {
                    'departments': sorted(available_departments)
                }
            }), 200
            
        except Exception as query_error:
            print(f"❌ Query error: {query_error}")
            # Fallback ke mapping statis jika DB error
            return jsonify({
                'success': True,
                'data': {'departments': sorted(valid_departments)}
            }), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

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
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
            if departments_in_faculty:
                # Create LIKE conditions for each department
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    faculty_params.append(f"%{dept.lower()}%")
                
                faculty_filter = f"WHERE ({' OR '.join(like_conditions)})"
                print(f"🏛️ Filtering by faculty: {faculty} (departments: {departments_in_faculty})")
        else:
            faculty_filter = ""
        
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
                dm.v_nama_homebase_unpar AS v_nama_jurusan,
                dm.fakultas AS v_nama_fakultas
            FROM latest_dosen d
            LEFT JOIN datamaster dm ON d.v_id_sinta IS NOT NULL 
                AND TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
            {faculty_filter}
            ORDER BY (COALESCE(d.n_sitasi_gs, 0) + COALESCE(d.n_sitasi_scopus, 0)) DESC, d.t_tanggal_unduh DESC
        """
        params_full = params + faculty_params
        cur.execute(data_query, params_full)
        dosen_data = [dict(row) for row in cur.fetchall()]
        
        # # Add faculty information to each record based on department (same as get_sinta_dosen)
        # for dosen in dosen_data:
        #     department_name = dosen.get('v_nama_jurusan')
        #     if department_name:
        #         faculty_name = get_faculty_from_department(department_name)
        #         dosen['v_nama_fakultas'] = faculty_name
        #     else:
        #         dosen['v_nama_fakultas'] = None
        
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

        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 1. Build Base WHERE Clause
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

        # 2. Build Faculty/Jurusan Filter
        jurusan_filter = ""
        jurusan_params = []
        if department:
            jurusan_filter = "AND LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            jurusan_params.append(department.lower())
        elif faculty:
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
            if departments_in_faculty:
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    jurusan_params.append(f"%{dept.lower()}%")
                jurusan_filter = f"AND ({' OR '.join(like_conditions)})"

        # 3. Build Terindeks Filter
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

        # 4. CTE Definition
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
                        as jurusan_names,
                    STRING_AGG(DISTINCT dm.fakultas, ', ' ORDER BY dm.fakultas) 
                        FILTER (WHERE dm.fakultas IS NOT NULL AND TRIM(dm.fakultas) != '') 
                        as fakultas_names
                FROM latest_publikasi p
                LEFT JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
                LEFT JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
                    AND (d.v_sumber = 'SINTA' OR d.v_id_sinta IS NOT NULL)
                LEFT JOIN datamaster dm ON TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
                    AND dm.v_nama_homebase_unpar IS NOT NULL
                    {jurusan_filter}
                GROUP BY p.v_id_publikasi, p.v_authors
            )
        """

        cte_params = params + jurusan_params

        # 5. Get Total Count
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
        total = count_result.get('total', 0) if count_result else 0

        # 6. Get Data (Main Query)
        # ⚠️ BAGIAN INI DIPERBAIKI: Memastikan semua kolom diambil dari tabel 'p'
        base_select = """
            SELECT
                p.v_id_publikasi,
                pm.authors,
                COALESCE(pm.jurusan_names, 'N/A') AS v_nama_jurusan,
                COALESCE(pm.fakultas_names, 'N/A') AS v_nama_fakultas,
                
                -- ✅ PERBAIKAN: Ambil kolom-kolom ini dari tabel p (stg_publikasi_tr)
                p.v_judul,
                p.v_jenis AS tipe,  -- Di-alias jadi 'tipe' agar sesuai Frontend
                COALESCE(p.v_tahun_publikasi, 0) AS v_tahun_publikasi,
                COALESCE(p.v_publisher, '') AS publisher,
                p.v_link_url,
                p.t_tanggal_unduh,
                p.v_sumber,
                COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                
                -- Data tambahan dari tabel join
                COALESCE(j.v_nama_jurnal, pr.v_nama_konferensi, 'N/A') AS venue,
                COALESCE(a.v_volume, '') AS volume,
                COALESCE(a.v_issue, '') AS issue,
                COALESCE(a.v_pages, '') AS pages,
                COALESCE(a.v_terindeks, '') AS v_terindeks,
                COALESCE(a.v_ranking, '') AS v_ranking
        """

        if jurusan_filter:
            data_query = f"""
                {latest_publikasi_cte}
                {base_select}
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
                {base_select}
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

        # 7. Format Data for Frontend
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

                # Format tipe (Backend mengembalikan key 'tipe', Frontend memprosesnya)
                # Pastikan key 'tipe' (dari SQL alias v_jenis) ada dan valid
                tipe_value = row_dict.get('tipe')
                if tipe_value:
                    tipe_value = str(tipe_value).strip()
                    tipe_mapping = {
                        'artikel': 'Artikel',
                        'buku': 'Buku',
                        'prosiding': 'Prosiding',
                        'penelitian': 'Penelitian',
                        'lainnya': 'Lainnya'
                    }
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
        if cur: cur.close()
        if conn: conn.close()

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
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
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
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
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
                    -- Aggregasi Jurusan
                    STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar) 
                        FILTER (WHERE dm.v_nama_homebase_unpar IS NOT NULL AND TRIM(dm.v_nama_homebase_unpar) != '') 
                        as jurusan_names,
                    STRING_AGG(DISTINCT dm.fakultas, ', ' ORDER BY dm.fakultas) 
                        FILTER (WHERE dm.fakultas IS NOT NULL AND TRIM(dm.fakultas) != '') 
                        as fakultas_names
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
                    COALESCE(pm.fakultas_names, 'N/A') AS v_nama_fakultas,
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
                    COALESCE(pm.fakultas_names, 'N/A') AS v_nama_fakultas,
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
            'v_nama_fakultas': 'Fakultas',
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

        # Excel safety: remove illegal characters that break openpyxl
        df_export = sanitize_df_for_excel(df_export)
        
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
                faculties = sorted(list(FACULTY_DEPT_MAP.keys()))
            
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
            faculties = sorted(list(FACULTY_DEPT_MAP.keys()))
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
        faculties = sorted(list(FACULTY_DEPT_MAP.keys()))
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
    """Get list of departments in a faculty with SINTA publikasi (FIXED LOOKUP)"""
    conn = None
    cur = None
    
    try:
        faculty = request.args.get('faculty', '').strip()
        
        # ============================================================
        # 1. SMART LOOKUP LOGIC
        # ============================================================
        valid_departments = FACULTY_DEPT_MAP.get(faculty, [])
        
        if not valid_departments:
            clean_name = faculty.replace('Fakultas ', '').strip()
            valid_departments = FACULTY_DEPT_MAP.get(clean_name, [])
            
        if not valid_departments:
            if 'Teknologi Informasi' in faculty or 'FTIS' in faculty:
                valid_departments = FACULTY_DEPT_MAP.get('Sains', [])

        print(f"🔍 Lookup Publikasi Faculty: Input='{faculty}' -> Mapped to {len(valid_departments)} departments")

        if not faculty:
            return jsonify({'error': 'Faculty parameter is required'}), 400

        if not valid_departments:
             return jsonify({'success': True, 'data': {'departments': []}}), 200

        conn = get_db_connection()
        if not conn:
            return jsonify({'success': True, 'data': {'departments': sorted(valid_departments)}}), 200
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        try:
            # 2. Query jurusan yang punya data publikasi
            placeholders = ', '.join(['%s'] * len(valid_departments))
            
            query = f"""
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
                    AND TRIM(dm.v_nama_homebase_unpar) IN ({placeholders})
                ORDER BY jurusan
            """
            
            cur.execute(query, tuple(valid_departments))
            results = cur.fetchall()
            active_departments = [row['jurusan'] for row in results if row['jurusan']]
            
            print(f"🏢 Found {len(active_departments)} active publication departments for {faculty}")
            
            return jsonify({
                'success': True,
                'data': {
                    'departments': sorted(active_departments)
                }
            }), 200
            
        except Exception as query_error:
            print(f"❌ Query error: {query_error}")
            return jsonify({
                'success': True,
                'data': {'departments': sorted(valid_departments)}
            }), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

def get_faculty_from_department(department):
    """Get faculty name from department name"""
    if not department:
        return None
    
    department_lower = department.lower().strip()
    
    for faculty, departments in FACULTY_DEPT_MAP.items():
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
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
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
                dm.v_nama_homebase_unpar AS v_nama_jurusan,
                dm.fakultas AS v_nama_fakultas
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
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
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
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
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
                dm.v_nama_homebase_unpar AS v_nama_jurusan,
                dm.fakultas AS v_nama_fakultas
            FROM latest_dosen d
            LEFT JOIN datamaster dm ON d.v_id_googleScholar IS NOT NULL 
                AND TRIM(d.v_id_googleScholar) = TRIM(dm.id_gs)
            {faculty_filter}
            ORDER BY d.n_total_sitasi_gs DESC NULLS LAST, d.t_tanggal_unduh DESC
        """
        params_full = params + faculty_params
        cur.execute(data_query, params_full)
        dosen_data = cur.fetchall()
        
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
    """Get list of faculties directly from datamaster where Scholar ID exists"""
    conn = None
    cur = None
    
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # ✅ Query langsung ke kolom fakultas di datamaster
        # Hanya ambil fakultas yang memiliki dosen dengan ID Google Scholar
        query = """
            SELECT DISTINCT TRIM(fakultas) as fakultas
            FROM datamaster
            WHERE id_gs IS NOT NULL 
                AND fakultas IS NOT NULL 
                AND TRIM(fakultas) != ''
            ORDER BY fakultas
        """
        
        cur.execute(query)
        results = cur.fetchall()
        faculties = [row['fakultas'] for row in results]
        
        return jsonify({
            'success': True,
            'data': {'faculties': faculties}
        }), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/api/scholar/dosen/departments', methods=['GET'])
@token_required
def get_scholar_departments(current_user_id):
    """Get list of departments based on selected faculty from datamaster"""
    conn = None
    cur = None
    
    try:
        faculty = request.args.get('faculty', '').strip()
        if not faculty:
            return jsonify({'success': False, 'error': 'Faculty parameter required'}), 400
            
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # ✅ Query jurusan berdasarkan fakultas yang dipilih
        query = """
            SELECT DISTINCT TRIM(v_nama_homebase_unpar) as jurusan
            FROM datamaster
            WHERE id_gs IS NOT NULL 
                AND v_nama_homebase_unpar IS NOT NULL 
                AND TRIM(v_nama_homebase_unpar) != ''
                AND LOWER(TRIM(fakultas)) = LOWER(%s) -- Filter by Faculty column
            ORDER BY jurusan
        """
        
        cur.execute(query, (faculty,))
        results = cur.fetchall()
        departments = [row['jurusan'] for row in results]
        
        return jsonify({
            'success': True,
            'data': {'departments': departments}
        }), 200
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()

@app.route('/api/scholar/publikasi', methods=['GET'])
@token_required
def get_scholar_publikasi(current_user_id):
    """Get Google Scholar publikasi data with pagination and filters"""
    conn = None
    cur = None
    
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
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # 1. Base WHERE Clause
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
        
        # 2. Jurusan Filter
        jurusan_filter = ""
        jurusan_params = []
        if department:
            jurusan_filter = "AND LOWER(TRIM(dm.v_nama_homebase_unpar)) = LOWER(%s)"
            jurusan_params.append(department.lower())
        elif faculty:
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
            if departments_in_faculty:
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(dm.v_nama_homebase_unpar)) LIKE LOWER(%s)")
                    jurusan_params.append(f"%{dept.lower()}%")
                jurusan_filter = f"AND ({' OR '.join(like_conditions)})"
        
        # 3. CTE (Updated with Fakultas Aggregation)
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
                    p.v_authors,
                    -- Aggregasi Jurusan
                    STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar) 
                        FILTER (WHERE dm.v_nama_homebase_unpar IS NOT NULL) as jurusan_names,
                    -- ✅ [BARU] Aggregasi Fakultas langsung dari DB (Sama seperti SINTA)
                    STRING_AGG(DISTINCT dm.fakultas, ', ' ORDER BY dm.fakultas) 
                        FILTER (WHERE dm.fakultas IS NOT NULL AND TRIM(dm.fakultas) != '') 
                        as fakultas_names
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
        
        # 4. Count Query
        if jurusan_filter:
            count_query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(*) AS total
                FROM latest_publikasi p
                INNER JOIN publikasi_with_metadata pm ON p.v_id_publikasi = pm.v_id_publikasi
                WHERE pm.jurusan_names IS NOT NULL AND pm.jurusan_names != ''
            """
        else:
            count_query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(*) AS total
                FROM latest_publikasi
            """
        
        cur.execute(count_query, cte_params)
        count_result = cur.fetchone()
        total = count_result.get('total', 0) if count_result else 0
        
        # 5. Data Query
        base_select = """
            SELECT
                p.v_id_publikasi,
                COALESCE(NULLIF(TRIM(p.v_authors), ''), 'N/A') AS authors,
                COALESCE(pm.jurusan_names, 'N/A') AS v_nama_jurusan,
                COALESCE(pm.fakultas_names, 'N/A') AS v_nama_fakultas, -- ✅ [BARU]
                p.v_judul,
                p.v_jenis AS tipe,
                -- ✅ [PERBAIKAN] Handling Null/0 Year
                COALESCE(NULLIF(p.v_tahun_publikasi, 0), 0) AS v_tahun_publikasi,
                
                COALESCE(j.v_nama_jurnal, pr.v_nama_konferensi, 'N/A') AS venue,
                COALESCE(p.v_publisher, '') AS publisher,
                COALESCE(a.v_volume, '') AS volume,
                COALESCE(a.v_issue, '') AS issue,
                COALESCE(a.v_pages, '') AS pages,
                COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                p.v_sumber,
                p.t_tanggal_unduh,
                p.v_link_url
        """

        if jurusan_filter:
            data_query = f"""
                {latest_publikasi_cte}
                {base_select}
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_metadata pm ON p.v_id_publikasi = pm.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                WHERE pm.jurusan_names IS NOT NULL AND pm.jurusan_names != ''
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
                LIMIT %s OFFSET %s
            """
        else:
            data_query = f"""
                {latest_publikasi_cte}
                {base_select}
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_metadata pm ON p.v_id_publikasi = pm.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
                LIMIT %s OFFSET %s
            """
        
        final_params = cte_params + [per_page, offset]
        cur.execute(data_query, final_params)
        rows = cur.fetchall()
        
        # 6. Format Data (Loop Python untuk fakultas DIHAPUS)
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
        print("❌ Scholar Publikasi error:\n", traceback.format_exc())
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if cur: cur.close()
        if conn: conn.close()


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
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
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
            departments_in_faculty = FACULTY_DEPT_MAP.get(faculty, [])
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
            publikasi_with_metadata AS (
                SELECT 
                    p.v_id_publikasi,
                    p.v_authors,
                    STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar) 
                        FILTER (WHERE dm.v_nama_homebase_unpar IS NOT NULL AND TRIM(dm.v_nama_homebase_unpar) != '') as jurusan_names,
                    STRING_AGG(DISTINCT dm.fakultas, ', ' ORDER BY dm.fakultas)
                        FILTER (WHERE dm.fakultas IS NOT NULL AND TRIM(dm.fakultas) != '') as fakultas_names
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
        
        base_select = """
            SELECT
                COALESCE(NULLIF(TRIM(p.v_authors), ''), 'N/A') AS authors,
                COALESCE(pm.jurusan_names, 'N/A') AS v_nama_jurusan,
                COALESCE(pm.fakultas_names, 'N/A') AS v_nama_fakultas, -- ✅ [BARU]
                p.v_judul,
                p.v_jenis AS tipe,
                COALESCE(NULLIF(p.v_tahun_publikasi, 0), 0) AS v_tahun_publikasi, -- ✅ [BARU]
                COALESCE(j.v_nama_jurnal, pr.v_nama_konferensi, 'N/A') AS venue,
                COALESCE(p.v_publisher, '') AS publisher,
                COALESCE(a.v_volume, '') AS volume,
                COALESCE(a.v_issue, '') AS issue,
                COALESCE(a.v_pages, '') AS pages,
                COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                p.t_tanggal_unduh,
                p.v_link_url
        """
        
        if jurusan_filter:
            data_query = f"""
                {latest_publikasi_cte}
                {base_select}
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_metadata pm ON p.v_id_publikasi = pm.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                WHERE pm.jurusan_names IS NOT NULL AND pm.jurusan_names != ''
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
            """
        else:
            data_query = f"""
                {latest_publikasi_cte}
                {base_select}
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_metadata pm ON p.v_id_publikasi = pm.v_id_publikasi
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
            'v_nama_fakultas': 'Fakultas',
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

        # Excel safety: remove illegal characters that break openpyxl
        df_export = sanitize_df_for_excel(df_export)
        
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
        port=int(os.environ.get('PORT', 5000)),
        allow_unsafe_werkzeug=True
    )