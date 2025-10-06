from flask import Flask, request, jsonify, session
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash
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
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Konfigurasi CORS yang benar
CORS(app, 
     resources={r"/*": {
         "origins": ["http://localhost:5173"],
         "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
         "allow_headers": ["Content-Type", "Authorization"],
         "supports_credentials": True,
         "expose_headers": ["Content-Type", "Authorization"],
         "max_age": 600
     }},
     allow_credentials=True)  # Tambahkan ini

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-change-this')

# Database configuration
DB_CONFIG = {
    'dbname': os.environ.get('DB_NAME', 'SKM_PUBLIKASI'),
    'user': os.environ.get('DB_USER', 'rayhanadjisantoso'), 
    'password': os.environ.get('DB_PASSWORD', 'rayhan123'),
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
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
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
            # Remove 'Bearer ' prefix
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
app.register_blueprint(auth_bp, url_prefix='/auth')  # Changed from '/api' to '/auth'

# Authentication Routes (These have been moved to auth.py and are now removed from app.py)

# Dashboard Routes
@app.route('/api/dashboard/stats', methods=['GET'])
@token_required
def dashboard_stats(current_user_id):
    """Get dashboard statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get total dosen
        cur.execute("SELECT COUNT(*) as total FROM tmp_dosen_dt")
        total_dosen = cur.fetchone()['total']
        
        # Get total publikasi
        cur.execute("SELECT COUNT(*) as total FROM stg_publikasi_tr")
        total_publikasi = cur.fetchone()['total']
        
        # Get total sitasi
        cur.execute("SELECT COALESCE(SUM(n_total_sitasi_gs), 0) as total FROM tmp_dosen_dt")
        total_sitasi = cur.fetchone()['total']
        
        # Get publikasi by year
        cur.execute("""
            SELECT v_tahun_publikasi, COUNT(*) as count 
            FROM stg_publikasi_tr 
            WHERE v_tahun_publikasi IS NOT NULL 
            GROUP BY v_tahun_publikasi 
            ORDER BY v_tahun_publikasi DESC
            LIMIT 10
        """)
        publikasi_by_year = [dict(row) for row in cur.fetchall()]
        
        # Get top authors by citations
        cur.execute("""
            SELECT v_nama_dosen, COALESCE(n_total_sitasi_gs, 0) as n_total_sitasi_gs
            FROM tmp_dosen_dt 
            ORDER BY n_total_sitasi_gs DESC 
            LIMIT 10
        """)
        top_authors = [dict(row) for row in cur.fetchall()]
        
        # Get publication by type
        cur.execute("""
            SELECT v_jenis, COUNT(*) as count
            FROM stg_publikasi_tr
            GROUP BY v_jenis
            ORDER BY count DESC
        """)
        publikasi_by_type = [dict(row) for row in cur.fetchall()]
        
        # Get recent activities (publications added in last 30 days)
        cur.execute("""
            SELECT COUNT(*) as count
            FROM stg_publikasi_tr
            WHERE t_tanggal_unduh >= CURRENT_DATE - INTERVAL '30 days'
        """)
        recent_publications = cur.fetchone()['count']
        
        return jsonify({
            'total_dosen': total_dosen,
            'total_publikasi': total_publikasi,
            'total_sitasi': total_sitasi,
            'publikasi_by_year': publikasi_by_year,
            'top_authors': top_authors,
            'publikasi_by_type': publikasi_by_type,
            'recent_publications': recent_publications
        }), 200
        
    except Exception as e:
        logger.error(f"Dashboard stats error: {e}")
        return jsonify({'error': 'Failed to fetch dashboard stats'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

# SINTA Routes
@app.route('/api/sinta/dosen', methods=['GET'])
@token_required
def get_sinta_dosen(current_user_id):
    """Get SINTA dosen data with pagination and search"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query with proper table names
        where_clause = "WHERE d.v_sumber = 'SINTA' OR d.v_sumber IS NULL"
        params = []
        
        if search:
            where_clause += " AND LOWER(d.v_nama_dosen) LIKE LOWER(%s)"
            params.append(f'%{search}%')
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total 
            FROM tmp_dosen_dt d
            LEFT JOIN stg_jurusan_mt j ON d.v_id_jurusan = j.v_id_jurusan
            {where_clause}
        """
        cur.execute(count_query, params)
        total = cur.fetchone()['total']
        
        # Get data
        data_query = f"""
            SELECT 
                d.v_id_dosen, d.v_nama_dosen, d.v_id_sinta, d.v_id_googleScholar,
                d.n_total_publikasi, d.n_total_sitasi_gs, d.n_h_index_gs, 
                d.n_i10_index_gs, d.n_skor_sinta, d.n_skor_sinta_3yr,
                j.v_nama_jurusan, d.t_tanggal_unduh, d.v_link_url
            FROM tmp_dosen_dt d
            LEFT JOIN stg_jurusan_mt j ON d.v_id_jurusan = j.v_id_jurusan
            {where_clause}
            ORDER BY d.n_total_sitasi_gs DESC NULLS LAST
            LIMIT %s OFFSET %s
        """
        
        params.extend([per_page, offset])
        cur.execute(data_query, params)
        dosen_data = [dict(row) for row in cur.fetchall()]
        
        return jsonify({
            'data': dosen_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get SINTA dosen error: {e}")
        return jsonify({'error': 'Failed to fetch SINTA dosen data'}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/api/sinta/publikasi', methods=['GET'])
@token_required
def get_sinta_publikasi(current_user_id):
    """Get SINTA publikasi data with pagination and search"""
    conn = None
    cur = None
    
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query - filter untuk SINTA
        where_clause = "WHERE (p.v_sumber ILIKE %s OR p.v_sumber IS NULL)"
        params = ['%SINTA%']
        
        if search:
            where_clause += """ AND (
                LOWER(p.v_judul) LIKE LOWER(%s) OR
                LOWER(p.v_authors) LIKE LOWER(%s) OR
                LOWER(p.v_publisher) LIKE LOWER(%s)
            )"""
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total
            FROM stg_publikasi_tr p
            {where_clause}
        """
        
        cur.execute(count_query, params)
        total = cur.fetchone()['total']
        
        # Get data - gunakan p.v_publisher bukan b.v_penerbit
        data_query = f"""
            SELECT
                p.v_id_publikasi,
                COALESCE(
                    NULLIF(p.v_authors, ''),
                    STRING_AGG(DISTINCT d.v_nama_dosen, ', ')
                ) AS authors,
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
                p.n_total_sitasi,
                p.v_sumber,
                p.t_tanggal_unduh,
                p.v_link_url
            FROM stg_publikasi_tr p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
            LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
            LEFT JOIN stg_buku_dr b ON p.v_id_publikasi = b.v_id_publikasi
            LEFT JOIN stg_penelitian_dr pn ON p.v_id_publikasi = pn.v_id_publikasi
            LEFT JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
            LEFT JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
            {where_clause}
            GROUP BY 
                p.v_id_publikasi, p.v_judul, p.v_jenis, p.v_tahun_publikasi,
                p.n_total_sitasi, p.v_sumber, p.t_tanggal_unduh, p.v_link_url,
                p.v_authors, p.v_publisher,
                j.v_nama_jurnal, pr.v_nama_konferensi,
                a.v_volume, a.v_issue, a.v_pages
            ORDER BY p.n_total_sitasi DESC NULLS LAST
            LIMIT %s OFFSET %s
        """
        
        params.extend([per_page, offset])
        cur.execute(data_query, params)
        rows = cur.fetchall()
        
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
                    'penelitian': 'Penelitian'
                }
                
                if tipe_value:
                    row_dict['tipe'] = tipe_mapping.get(tipe_value.lower(), tipe_value.capitalize())
                else:
                    row_dict['tipe'] = 'N/A'
                
                publikasi_data.append(row_dict)
        
        return jsonify({
            'data': publikasi_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page if total > 0 else 0
            }
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Full error traceback:\n", error_details)
        logger.error(f"Get SINTA publikasi error: {e}\n{error_details}")
        return jsonify({
            'error': 'Failed to fetch SINTA publikasi data',
            'details': str(e)
        }), 500
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# Google Scholar Routes
@app.route('/api/scholar/dosen', methods=['GET'])
@token_required
def get_scholar_dosen(current_user_id):
    """Get Google Scholar dosen data"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query for Google Scholar data
        where_clause = "WHERE d.v_sumber = 'Google Scholar' OR d.v_id_googleScholar IS NOT NULL"
        params = []
        
        if search:
            where_clause += " AND LOWER(d.v_nama_dosen) LIKE LOWER(%s)"
            params.append(f'%{search}%')
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total 
            FROM tmp_dosen_dt d
            {where_clause}
        """
        cur.execute(count_query, params)
        total = cur.fetchone()['total']
        
        # Get data
        data_query = f"""
            SELECT 
                d.v_id_dosen, d.v_nama_dosen, d.v_id_googleScholar,
                d.n_total_publikasi, d.n_total_sitasi_gs, d.n_h_index_gs, 
                d.n_i10_index_gs, d.v_link_url, d.t_tanggal_unduh
            FROM tmp_dosen_dt d
            {where_clause}
            ORDER BY d.n_total_sitasi_gs DESC NULLS LAST
            LIMIT %s OFFSET %s
        """
        
        params.extend([per_page, offset])
        cur.execute(data_query, params)
        scholar_data = [dict(row) for row in cur.fetchall()]
        
        return jsonify({
            'data': scholar_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Get Scholar dosen error: {e}")
        return jsonify({'error': 'Failed to fetch Scholar dosen data'}), 500

@app.route('/api/scholar/publikasi', methods=['GET'])
@token_required
def get_scholar_publikasi(current_user_id):
    """Get Google Scholar publikasi data"""
    conn = None
    cur = None
    
    print(f"🔑 Authenticated user ID: {current_user_id}")
    
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        offset = (page - 1) * per_page
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build base query
        where_clause = "WHERE p.v_sumber ILIKE %s"
        params = ['%Scholar%']
        
        # Expand search to include author, title, and publisher
        if search:
            where_clause += """ AND (
                LOWER(p.v_judul) LIKE LOWER(%s) OR
                LOWER(p.v_authors) LIKE LOWER(%s) OR
                LOWER(p.v_publisher) LIKE LOWER(%s)
            )"""
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param])
        
        # ======== Hitung total data ========
        count_query = f"""
            SELECT COUNT(*) AS total
            FROM stg_publikasi_tr p
            {where_clause}
        """
        
        cur.execute(count_query, params)
        count_result = cur.fetchone()
        
        total = 0
        if count_result:
            total = count_result.get('total', 0) or 0
        
        # ======== Ambil data publikasi ========
        data_query = f"""
            SELECT
                p.v_id_publikasi,
                COALESCE(
                    NULLIF(p.v_authors, ''),
                    STRING_AGG(DISTINCT d.v_nama_dosen, ', ')
                ) AS authors,
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
                p.n_total_sitasi,
                p.v_sumber,
                p.t_tanggal_unduh,
                p.v_link_url
            FROM stg_publikasi_tr p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
            LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
            LEFT JOIN stg_buku_dr b ON p.v_id_publikasi = b.v_id_publikasi
            LEFT JOIN stg_penelitian_dr pn ON p.v_id_publikasi = pn.v_id_publikasi
            LEFT JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
            LEFT JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
            {where_clause}
            GROUP BY 
                p.v_id_publikasi, p.v_judul, p.v_jenis, p.v_tahun_publikasi,
                p.n_total_sitasi, p.v_sumber, p.t_tanggal_unduh, p.v_link_url,
                p.v_authors, p.v_publisher,
                j.v_nama_jurnal, pr.v_nama_konferensi,
                a.v_volume, a.v_issue, a.v_pages
            ORDER BY p.n_total_sitasi DESC NULLS LAST
            LIMIT %s OFFSET %s
        """
        
        final_params = params + [per_page, offset]
        
        cur.execute(data_query, final_params)
        rows = cur.fetchall()
        
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
                    'penelitian': 'Penelitian'
                }
                
                if tipe_value:
                    row_dict['tipe'] = tipe_mapping.get(tipe_value.lower(), tipe_value.capitalize())
                else:
                    row_dict['tipe'] = 'N/A'
                
                publikasi_data.append(row_dict)
        
        # Hitung total pages
        total_pages = 0
        if total > 0 and per_page > 0:
            total_pages = (total + per_page - 1) // per_page
        
        response_data = {
            "data": publikasi_data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": total_pages
            }
        }
        
        return jsonify(response_data), 200
        
    except psycopg2.Error as db_error:
        error_details = traceback.format_exc()
        print("❌ Database error:\n", error_details)
        logger.error(f"Database error in Scholar publikasi: {db_error}\n{error_details}")
        return jsonify({
            "error": "Database query failed",
            "details": str(db_error)
        }), 500
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Full error traceback:\n", error_details)
        logger.error(f"Get Scholar publikasi error: {e}\n{error_details}")
        return jsonify({
            "error": "Failed to fetch Scholar publikasi data",
            "details": str(e)
        }), 500
        
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
        
        # Check if users table exists, create if not
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
    logger.info("Starting ProDS Flask Application")
    logger.info(f"Database: {DB_CONFIG['dbname']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}")
    logger.info(f"Environment: {os.environ.get('FLASK_ENV', 'development')}")
    
    # Run the Flask app
    debug_mode = os.environ.get('FLASK_ENV') == 'development'
    app.run(
        debug=debug_mode, 
        host='0.0.0.0', 
        port=int(os.environ.get('PORT', 5000))
    )