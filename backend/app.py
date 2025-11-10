from flask import Flask, request, jsonify, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
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

# Dashboard Routes
@app.route('/api/dashboard/stats', methods=['GET'])
@token_required
def dashboard_stats(current_user_id):
    """Get dashboard statistics - only from latest data per dosen and publikasi"""
    try:
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
        
        print(f"📅 Latest scraping date: {latest_date}")
        print(f"📅 Previous scraping date: {previous_date}")
        
        # CTE 1: Latest dosen WITH Google Scholar filter (untuk sitasi GS)
        latest_dosen_gs_cte = """
            WITH latest_dosen_gs AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                WHERE (d.v_sumber = 'Google Scholar' OR d.v_id_googleScholar IS NOT NULL)
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # CTE 2: Latest dosen WITHOUT filter (untuk sitasi GS-SINTA dan Scopus)
        latest_dosen_all_cte = """
            WITH latest_dosen_all AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # CTE for latest publikasi data (unchanged)
        latest_publikasi_cte = """
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            )
        """
        
        # CTE for previous dosen data (for comparison)
        previous_dosen_gs_cte = f"""
            WITH previous_dosen_gs AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                WHERE (d.v_sumber = 'Google Scholar' OR d.v_id_googleScholar IS NOT NULL)
                  AND DATE(d.t_tanggal_unduh) = %s
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """ if previous_date else "WITH previous_dosen_gs AS (SELECT * FROM tmp_dosen_dt WHERE 1=0)"
        
        previous_dosen_all_cte = f"""
            WITH previous_dosen_all AS (
                SELECT DISTINCT ON (LOWER(TRIM(d.v_nama_dosen)))
                    d.*
                FROM tmp_dosen_dt d
                WHERE DATE(d.t_tanggal_unduh) = %s
                ORDER BY LOWER(TRIM(d.v_nama_dosen)), d.t_tanggal_unduh DESC NULLS LAST
            )
        """ if previous_date else "WITH previous_dosen_all AS (SELECT * FROM tmp_dosen_dt WHERE 1=0)"
        
        previous_publikasi_cte = f"""
            WITH previous_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                WHERE DATE(p.t_tanggal_unduh) = %s
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            )
        """ if previous_date else "WITH previous_publikasi AS (SELECT * FROM stg_publikasi_tr WHERE 1=0)"
        
        # Get total dosen from latest data (GS and SINTA)
        cur.execute(f"""
            {latest_dosen_all_cte}
            SELECT COUNT(*) as total FROM latest_dosen_all
        """)
        total_dosen = cur.fetchone()['total']
        
        print(f"📊 Total unique dosen (GS and SINTA): {total_dosen}")
        
        # Get total publikasi from latest data only
        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT COUNT(*) as total FROM latest_publikasi
        """)
        total_publikasi = cur.fetchone()['total']
        
        print(f"📊 Total unique publikasi: {total_publikasi}")
        
        # Get sitasi GS from dosen WITH Google Scholar filter
        cur.execute(f"""
            {latest_dosen_gs_cte}
            SELECT 
                COALESCE(SUM(COALESCE(n_total_sitasi_gs, 0)), 0) as total_sitasi_gs,
                COALESCE(AVG(n_h_index_gs), 0) as avg_h_index,
                COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n_h_index_gs), 0) as median_h_index
            FROM latest_dosen_gs
        """)
        gs_stats = cur.fetchone()
        total_sitasi_gs = int(gs_stats['total_sitasi_gs'] or 0)
        avg_h_index = gs_stats['avg_h_index']
        median_h_index = gs_stats['median_h_index']
        
        # Get sitasi GS-SINTA dan Scopus from ALL dosen (no filter)
        cur.execute(f"""
            {latest_dosen_all_cte}
            SELECT 
                COALESCE(SUM(COALESCE(n_sitasi_gs, 0)), 0) as total_sitasi_gs_sinta,
                COALESCE(SUM(COALESCE(n_sitasi_scopus, 0)), 0) as total_sitasi_scopus
            FROM latest_dosen_all
        """)
        other_stats = cur.fetchone()
        total_sitasi_gs_sinta = int(other_stats['total_sitasi_gs_sinta'] or 0)
        total_sitasi_scopus = int(other_stats['total_sitasi_scopus'] or 0)
        
        # Total sitasi = GS (filtered) + GS-SINTA (all) + Scopus (all)
        total_sitasi = total_sitasi_gs + total_sitasi_gs_sinta + total_sitasi_scopus
        
        print(f"📊 Total sitasi: {total_sitasi}")
        print(f"   - Google Scholar (filtered): {total_sitasi_gs}")
        print(f"   - Google Scholar SINTA (all): {total_sitasi_gs_sinta}")
        print(f"   - Scopus (all): {total_sitasi_scopus}")
        print(f"📊 Avg H-Index: {avg_h_index}, Median H-Index: {median_h_index}")
        
        # Get publikasi by year (unchanged)
        current_year = datetime.now().year
        start_year = current_year - 15

        cur.execute(f"""
            {latest_publikasi_cte},
            year_range AS (
                SELECT generate_series(%s, %s) as year_num
            )
            SELECT 
                yr.year_num::TEXT as v_tahun_publikasi, 
                COALESCE(COUNT(p.v_id_publikasi), 0) as count
            FROM year_range yr
            LEFT JOIN latest_publikasi p ON CAST(p.v_tahun_publikasi AS TEXT) = CAST(yr.year_num AS TEXT)
            GROUP BY yr.year_num
            ORDER BY yr.year_num ASC
        """, (start_year, current_year))
        publikasi_by_year = [dict(row) for row in cur.fetchall()]
        
        print(f"📊 Publikasi by year (15 years): {len(publikasi_by_year)} years")
        
        # Get top authors by h-index (Scopus) - use all dosen (GS and SINTA)
        cur.execute(f"""
            {latest_dosen_all_cte}
            SELECT
                v_nama_dosen,
                COALESCE(n_h_index_scopus, 0) AS n_h_index_scopus
            FROM latest_dosen_all
            WHERE COALESCE(n_h_index_scopus, 0) > 0
            ORDER BY n_h_index_scopus DESC NULLS LAST
            LIMIT 10
        """)
        top_authors_scopus = [dict(row) for row in cur.fetchall()]

        # Get top authors by h-index (Google Scholar) - use GS filtered CTE
        cur.execute(f"""
            {latest_dosen_gs_cte}
            SELECT
                v_nama_dosen,
                COALESCE(n_h_index_gs, 0) AS n_h_index_gs
            FROM latest_dosen_gs
            ORDER BY n_h_index_gs DESC NULLS LAST
            LIMIT 10
        """)
        top_authors_gs = [dict(row) for row in cur.fetchall()]
        
        print(f"📊 Top authors (Scopus h-index): {len(top_authors_scopus)} | (GS h-index): {len(top_authors_gs)}")
        
        # ... (sisanya tetap sama, gunakan latest_publikasi_cte untuk publikasi)
        
        # Get publikasi by type from latest publikasi data only
        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT v_jenis, COUNT(*) as count
            FROM latest_publikasi
            GROUP BY v_jenis
            ORDER BY count DESC
        """)
        publikasi_by_type = [dict(row) for row in cur.fetchall()]
        
        print(f"📊 Publikasi by type: {len(publikasi_by_type)} types")
        
        # Get recent publications (30 hari terakhir) from latest publikasi data only
        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT COUNT(*) as count
            FROM latest_publikasi
            WHERE t_tanggal_unduh >= CURRENT_DATE - INTERVAL '30 days'
        """)
        recent_publications = cur.fetchone()['count']
        
        print(f"📊 Recent publications (30 days): {recent_publications}")
        
        # International/National publication totals and breakdowns (latest publikasi only)
        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT COUNT(*) AS cnt
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
              AND COALESCE(a.v_ranking, '') IN ('Q1','Q2')
        """)
        publikasi_internasional_q12 = cur.fetchone()['cnt'] or 0

        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT COUNT(*) AS cnt
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
              AND (
                    COALESCE(a.v_ranking, '') IN ('Q3','Q4')
                 OR COALESCE(a.v_ranking, '') = ''
              )
        """)
        publikasi_internasional_q34_noq = cur.fetchone()['cnt'] or 0

        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT COUNT(*) AS cnt
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 1','sinta 2')
        """)
        publikasi_nasional_sinta12 = cur.fetchone()['cnt'] or 0

        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT COUNT(*) AS cnt
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 3','sinta 4')
        """)
        publikasi_nasional_sinta34 = cur.fetchone()['cnt'] or 0

        # New: Sinta 5 and Sinta 6 counts
        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT COUNT(*) AS cnt
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 5'
        """)
        publikasi_nasional_sinta5 = cur.fetchone()['cnt'] or 0

        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT COUNT(*) AS cnt
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 6'
        """)
        publikasi_nasional_sinta6 = cur.fetchone()['cnt'] or 0

        # Breakdown: Scopus by Q levels
        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT
                CASE
                    WHEN COALESCE(a.v_ranking,'') IN ('Q1','Q2','Q3','Q4') THEN a.v_ranking
                    ELSE 'noQ'
                END AS ranking,
                COUNT(*) AS count
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
            GROUP BY 1
            ORDER BY 1
        """)
        scopus_q_breakdown = [dict(row) for row in cur.fetchall()]

        # Breakdown: Sinta by rank
        cur.execute(f"""
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
                COUNT(*) AS count
            FROM latest_publikasi p
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            GROUP BY 1
            ORDER BY 1
        """)
        sinta_rank_breakdown = [dict(row) for row in cur.fetchall()]

        # Top dosen by international publications (Scopus any Q)
        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT 
                d.v_nama_dosen,
                COUNT(*) AS count_international
            FROM latest_publikasi p
            JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
            JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
            GROUP BY d.v_nama_dosen
            ORDER BY count_international DESC
            LIMIT 10
        """)
        top_dosen_international = [dict(row) for row in cur.fetchall()]

        # Top dosen by national publications (Sinta 1-6)
        cur.execute(f"""
            {latest_publikasi_cte}
            SELECT 
                d.v_nama_dosen,
                COUNT(*) AS count_national
            FROM latest_publikasi p
            JOIN stg_publikasi_dosen_dt pd ON p.v_id_publikasi = pd.v_id_publikasi
            JOIN tmp_dosen_dt d ON pd.v_id_dosen = d.v_id_dosen
            LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
            WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 1','sinta 2','sinta 3','sinta 4','sinta 5','sinta 6')
            GROUP BY d.v_nama_dosen
            ORDER BY count_national DESC
            LIMIT 10
        """)
        top_dosen_national = [dict(row) for row in cur.fetchall()]

        # Calculate previous values for comparison
        prev_total_dosen = 0
        prev_total_publikasi = 0
        prev_total_sitasi = 0
        prev_total_sitasi_gs = 0
        prev_total_sitasi_gs_sinta = 0
        prev_total_sitasi_scopus = 0
        prev_avg_h_index = 0
        prev_median_h_index = 0
        prev_publikasi_internasional_q12 = 0
        prev_publikasi_internasional_q34_noq = 0
        prev_publikasi_nasional_sinta12 = 0
        prev_publikasi_nasional_sinta34 = 0
        prev_publikasi_nasional_sinta5 = 0
        prev_publikasi_nasional_sinta6 = 0

        if previous_date:
            # Previous total dosen
            cur.execute(f"""
                {previous_dosen_all_cte}
                SELECT COUNT(*) as total FROM previous_dosen_all
            """, (previous_date,))
            prev_total_dosen = cur.fetchone()['total'] or 0

            # Previous total publikasi
            cur.execute(f"""
                {previous_publikasi_cte}
                SELECT COUNT(*) as total FROM previous_publikasi
            """, (previous_date,))
            prev_total_publikasi = cur.fetchone()['total'] or 0

            # Previous sitasi GS
            cur.execute(f"""
                {previous_dosen_gs_cte}
                SELECT 
                    COALESCE(SUM(COALESCE(n_total_sitasi_gs, 0)), 0) as total_sitasi_gs,
                    COALESCE(AVG(n_h_index_gs), 0) as avg_h_index,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY n_h_index_gs), 0) as median_h_index
                FROM previous_dosen_gs
            """, (previous_date,))
            prev_gs_stats = cur.fetchone()
            prev_total_sitasi_gs = int(prev_gs_stats['total_sitasi_gs'] or 0) if prev_gs_stats else 0
            prev_avg_h_index = float(prev_gs_stats['avg_h_index'] or 0) if prev_gs_stats else 0
            prev_median_h_index = float(prev_gs_stats['median_h_index'] or 0) if prev_gs_stats else 0

            # Previous sitasi GS-SINTA dan Scopus
            cur.execute(f"""
                {previous_dosen_all_cte}
                SELECT 
                    COALESCE(SUM(COALESCE(n_sitasi_gs, 0)), 0) as total_sitasi_gs_sinta,
                    COALESCE(SUM(COALESCE(n_sitasi_scopus, 0)), 0) as total_sitasi_scopus
                FROM previous_dosen_all
            """, (previous_date,))
            prev_other_stats = cur.fetchone()
            prev_total_sitasi_gs_sinta = int(prev_other_stats['total_sitasi_gs_sinta'] or 0) if prev_other_stats else 0
            prev_total_sitasi_scopus = int(prev_other_stats['total_sitasi_scopus'] or 0) if prev_other_stats else 0
            prev_total_sitasi = prev_total_sitasi_gs + prev_total_sitasi_gs_sinta + prev_total_sitasi_scopus

            # Previous publikasi internasional Q1-Q2
            cur.execute(f"""
                {previous_publikasi_cte}
                SELECT COUNT(*) AS cnt
                FROM previous_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                  AND COALESCE(a.v_ranking, '') IN ('Q1','Q2')
            """, (previous_date,))
            prev_publikasi_internasional_q12 = cur.fetchone()['cnt'] or 0

            # Previous publikasi internasional Q3-Q4/noQ
            cur.execute(f"""
                {previous_publikasi_cte}
                SELECT COUNT(*) AS cnt
                FROM previous_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_terindeks, '')) = 'scopus'
                  AND (
                        COALESCE(a.v_ranking, '') IN ('Q3','Q4')
                     OR COALESCE(a.v_ranking, '') = ''
                  )
            """, (previous_date,))
            prev_publikasi_internasional_q34_noq = cur.fetchone()['cnt'] or 0

            # Previous publikasi nasional Sinta 1-2
            cur.execute(f"""
                {previous_publikasi_cte}
                SELECT COUNT(*) AS cnt
                FROM previous_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 1','sinta 2')
            """, (previous_date,))
            prev_publikasi_nasional_sinta12 = cur.fetchone()['cnt'] or 0

            # Previous publikasi nasional Sinta 3-4
            cur.execute(f"""
                {previous_publikasi_cte}
                SELECT COUNT(*) AS cnt
                FROM previous_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_ranking, '')) IN ('sinta 3','sinta 4')
            """, (previous_date,))
            prev_publikasi_nasional_sinta34 = cur.fetchone()['cnt'] or 0

            # Previous publikasi nasional Sinta 5
            cur.execute(f"""
                {previous_publikasi_cte}
                SELECT COUNT(*) AS cnt
                FROM previous_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 5'
            """, (previous_date,))
            prev_publikasi_nasional_sinta5 = cur.fetchone()['cnt'] or 0

            # Previous publikasi nasional Sinta 6
            cur.execute(f"""
                {previous_publikasi_cte}
                SELECT COUNT(*) AS cnt
                FROM previous_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE LOWER(COALESCE(a.v_ranking, '')) = 'sinta 6'
            """, (previous_date,))
            prev_publikasi_nasional_sinta6 = cur.fetchone()['cnt'] or 0

        # Format previous date for display
        prev_date_str = previous_date.strftime('%d/%m/%Y') if previous_date else None

        return jsonify({
            'total_dosen': total_dosen,
            'total_publikasi': total_publikasi,
            'total_sitasi': int(total_sitasi) if total_sitasi else 0,
            'total_sitasi_gs': int(total_sitasi_gs) if total_sitasi_gs else 0,
            'total_sitasi_gs_sinta': int(total_sitasi_gs_sinta) if total_sitasi_gs_sinta else 0,
            'total_sitasi_scopus': int(total_sitasi_scopus) if total_sitasi_scopus else 0,
            'avg_h_index': float(avg_h_index) if avg_h_index else 0,
            'median_h_index': float(median_h_index) if median_h_index else 0,
            'publikasi_by_year': publikasi_by_year,
            'top_authors_scopus': top_authors_scopus,
            'top_authors_gs': top_authors_gs,
            'publikasi_internasional_q12': publikasi_internasional_q12,
            'publikasi_internasional_q34_noq': publikasi_internasional_q34_noq,
            'publikasi_nasional_sinta12': publikasi_nasional_sinta12,
            'publikasi_nasional_sinta34': publikasi_nasional_sinta34,
            'publikasi_nasional_sinta5': publikasi_nasional_sinta5,
            'publikasi_nasional_sinta6': publikasi_nasional_sinta6,
            'scopus_q_breakdown': scopus_q_breakdown,
            'sinta_rank_breakdown': sinta_rank_breakdown,
            'publikasi_by_type': publikasi_by_type,
            'recent_publications': recent_publications,
            'top_dosen_international': top_dosen_international,
            'top_dosen_national': top_dosen_national,
            # Comparison data
            'previous_date': prev_date_str,
            'previous_values': {
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
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Dashboard stats error:\n", error_details)
        logger.error(f"Dashboard stats error: {e}\n{error_details}")
        return jsonify({'error': 'Failed to fetch dashboard stats'}), 500
    finally:
        if 'cur' in locals():
            cur.close()
        if 'conn' in locals():
            conn.close()

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
            'data': sinta_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
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
        
        # Get aggregate statistics from CTE with median
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
        
        return jsonify({
            'totalDosen': stats['total_dosen'] or 0,
            'totalSitasiGS': int(stats['total_sitasi_gs']) if stats['total_sitasi_gs'] else 0,
            'totalSitasiScopus': int(stats['total_sitasi_scopus']) if stats['total_sitasi_scopus'] else 0,
            'avgHIndex': round(float(stats['avg_h_index']), 1) if stats['avg_h_index'] else 0,
            'medianHIndex': round(float(stats['median_h_index']), 1) if stats['median_h_index'] else 0,
            'totalPublikasi': stats['total_publikasi'] or 0
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
                'faculties': faculties
            }), 200
            
        except Exception as query_error:
            import traceback
            print(f"❌ Query error: {query_error}")
            print(traceback.format_exc())
            # Return all faculties if query fails
            faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
            print(f"⚠️ Using complete faculty list ({len(faculties)} faculties)")
            return jsonify({
                'faculties': faculties
            }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Get faculties error:\n", error_details)
        logger.error(f"Get faculties error: {e}\n{error_details}")
        
        # Return all faculties even on major error
        faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
        return jsonify({
            'faculties': faculties
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
                'departments': mapped_departments
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
                'departments': sorted(filtered_departments)
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
            'departments': mapped_departments
        }), 200
        
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
        
        # Debug logging
        print(f"📥 Request params - page: {page}, per_page: {per_page}, search: '{search}', tipe: '{tipe_filter}', terindeks: '{terindeks_filter}', year_start: '{year_start}', year_end: '{year_end}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query - filter untuk SINTA
        where_clause = "WHERE (p.v_sumber ILIKE %s OR p.v_sumber IS NULL)"
        params = ['%SINTA%']
        
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
        
        # Expand search to include author, title, and publisher
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
        
        # Create CTE to get only latest version of each publication
        # Parse authors from v_authors field and match with datamaster using SINTA ID
        latest_publikasi_cte = f"""
            WITH latest_publikasi AS (
                SELECT DISTINCT ON (LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi)
                    p.*
                FROM stg_publikasi_tr p
                {where_clause}
                ORDER BY LOWER(TRIM(p.v_judul)), p.v_tahun_publikasi, p.t_tanggal_unduh DESC NULLS LAST
            ),
            -- Parse authors from v_authors field and match with datamaster using SINTA ID
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
                    AND d.v_id_sinta IS NOT NULL 
                    AND TRIM(d.v_id_sinta) <> ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
                GROUP BY p.v_id_publikasi, p.v_authors
            )
        """
        
        # Build faculty/department filter
        faculty_filter = ""
        faculty_params = []
        
        if department:
            # Specific department selected
            faculty_filter = "WHERE LOWER(TRIM(pj.jurusan_names)) LIKE LOWER(%s)"
            faculty_params.append(f"%{department}%")
            print(f"🏢 Filtering by department: {department}")
        elif faculty:
            # Only faculty selected, filter by all departments in that faculty
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                # Create LIKE conditions for each department
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(pj.jurusan_names)) LIKE LOWER(%s)")
                    faculty_params.append(f"%{dept.lower()}%")
                
                faculty_filter = f"WHERE ({' OR '.join(like_conditions)})"
                print(f"🏛️ Filtering by faculty: {faculty} (departments: {departments_in_faculty})")
        
        # Build terindeks filter
        terindeks_filter_clause = ""
        terindeks_params = []
        if terindeks_filter and terindeks_filter != 'all':
            if terindeks_filter == 'Other':
                # Filter for terindeks that is not in the common list
                terindeks_filter_clause = "AND (a.v_terindeks IS NULL OR a.v_terindeks = '' OR LOWER(TRIM(a.v_terindeks)) NOT IN ('scopus', 'wos', 'doaj', 'garuda', 'sinta'))"
            else:
                terindeks_filter_clause = "AND LOWER(TRIM(COALESCE(a.v_terindeks, ''))) = LOWER(%s)"
                terindeks_params.append(terindeks_filter)
            print(f"🔍 Adding terindeks filter: {terindeks_filter}")
        
        # Get total count from CTE with faculty filter
        if faculty_filter:
            # If faculty filter applied, only count publications with matching jurusan
            count_query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(*) as total
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_jurusan pj ON p.v_id_publikasi = pj.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                {faculty_filter}
                {terindeks_filter_clause}
            """
        else:
            # No filter, count all publikasi
            count_query = f"""
                {latest_publikasi_cte}
                SELECT COUNT(*) as total
                FROM latest_publikasi p
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                WHERE 1=1
                {terindeks_filter_clause}
            """
        cur.execute(count_query, params + faculty_params + terindeks_params)
        count_result = cur.fetchone()
        total = count_result.get('total', 0) or 0 if count_result else 0
        
        print(f"📊 Total unique records found: {total}")
        
        # Get data from CTE with proper jurusan join and faculty filter
        if faculty_filter:
            # If faculty filter applied, only show publications with matching jurusan
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
                    COALESCE(a.v_terindeks, '') AS v_terindeks,
                    COALESCE(a.v_ranking, '') AS v_ranking,
                    COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                    p.v_sumber,
                    p.t_tanggal_unduh,
                    p.v_link_url
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_jurusan pj ON p.v_id_publikasi = pj.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                {faculty_filter}
                {terindeks_filter_clause}
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
                LIMIT %s OFFSET %s
            """
        else:
            # No filter, show all publikasi
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
                    COALESCE(a.v_terindeks, '') AS v_terindeks,
                    COALESCE(a.v_ranking, '') AS v_ranking,
                    COALESCE(p.n_total_sitasi, 0) AS n_total_sitasi,
                    p.v_sumber,
                    p.t_tanggal_unduh,
                    p.v_link_url
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_jurusan pj ON p.v_id_publikasi = pj.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                LEFT JOIN stg_jurnal_mt j ON a.v_id_jurnal = j.v_id_jurnal
                LEFT JOIN stg_prosiding_dr pr ON p.v_id_publikasi = pr.v_id_publikasi
                WHERE 1=1
                {terindeks_filter_clause}
                ORDER BY p.n_total_sitasi DESC NULLS LAST, p.t_tanggal_unduh DESC
                LIMIT %s OFFSET %s
            """
        final_params = params + faculty_params + terindeks_params + [per_page, offset]
        
        cur.execute(data_query, final_params)
        rows = cur.fetchall()
        
        # Debug: Log jurusan for first few records
        if rows and len(rows) > 0:
            print(f"📤 Retrieved {len(rows)} SINTA publikasi records")
            
            for i, row in enumerate(rows[:5]):
                jurusan = row.get('v_nama_jurusan', 'N/A')
                authors = row.get('authors', 'N/A')
                print(f"   Record {i+1}: {row.get('v_judul', 'N/A')[:40]}...")
                print(f"      Authors: {authors[:50]}...")
                print(f"      Jurusan: {jurusan}")
            
            # Count total with jurusan
            total_with_jurusan = sum(1 for r in rows if r.get('v_nama_jurusan') and r.get('v_nama_jurusan') != 'N/A')
            print(f"   📊 Summary: {total_with_jurusan}/{len(rows)} records have jurusan data")
        
        # Format data untuk response
        publikasi_data = []
        if rows:
            for row in rows:
                row_dict = dict(row)
                
                # Add faculty information based on jurusan
                jurusan_names = row_dict.get('v_nama_jurusan', 'N/A')
                if jurusan_names and jurusan_names != 'N/A':
                    # Get first jurusan if multiple
                    first_jurusan = jurusan_names.split(',')[0].strip()
                    faculty_name = get_faculty_from_department(first_jurusan)
                    row_dict['v_nama_fakultas'] = faculty_name
                else:
                    row_dict['v_nama_fakultas'] = None
                
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
            'data': publikasi_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': total_pages
            }
        }), 200
        
    except psycopg2.Error as db_error:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Database error:\n", error_details)
        logger.error(f"Database error in SINTA publikasi: {db_error}\n{error_details}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return jsonify({
            "error": "Database query failed",
            "details": str(db_error)
        }), 500
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
        year_start = request.args.get('year_start', '').strip()
        year_end = request.args.get('year_end', '').strip()
        faculty = request.args.get('faculty', '').strip()
        department = request.args.get('department', '').strip()
        
        print(f"📊 SINTA Publikasi Stats - search: '{search}', tipe: '{tipe_filter}', year_start: '{year_start}', year_end: '{year_end}', faculty: '{faculty}', department: '{department}'")
        
        conn = get_db_connection()
        if not conn:
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Build query - filter untuk SINTA
        where_clause = "WHERE (p.v_sumber ILIKE %s OR p.v_sumber IS NULL)"
        params = ['%SINTA%']
        
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
        
        # Create CTE for latest publikasi with jurusan
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
                    p.n_total_sitasi,
                    STRING_AGG(DISTINCT dm.v_nama_homebase_unpar, ', ' ORDER BY dm.v_nama_homebase_unpar) 
                        FILTER (WHERE dm.v_nama_homebase_unpar IS NOT NULL) as jurusan_names
                FROM latest_publikasi p
                CROSS JOIN LATERAL (
                    SELECT TRIM(unnest(string_to_array(p.v_authors, ','))) as author_name
                ) authors
                LEFT JOIN tmp_dosen_dt d ON LOWER(TRIM(d.v_nama_dosen)) = LOWER(TRIM(authors.author_name))
                    AND d.v_id_sinta IS NOT NULL 
                    AND TRIM(d.v_id_sinta) <> ''
                LEFT JOIN datamaster dm ON TRIM(d.v_id_sinta) = TRIM(dm.id_sinta)
                GROUP BY p.v_id_publikasi, p.n_total_sitasi
            )
        """
        
        # Build faculty/department filter
        faculty_filter = ""
        faculty_params = []
        
        if department:
            faculty_filter = "WHERE LOWER(TRIM(pj.jurusan_names)) LIKE LOWER(%s)"
            faculty_params.append(f"%{department}%")
        elif faculty:
            departments_in_faculty = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
            if departments_in_faculty:
                like_conditions = []
                for dept in departments_in_faculty:
                    like_conditions.append("LOWER(TRIM(pj.jurusan_names)) LIKE LOWER(%s)")
                    faculty_params.append(f"%{dept.lower()}%")
                
                faculty_filter = f"WHERE ({' OR '.join(like_conditions)})"
        
        # Build terindeks filter for stats
        terindeks_filter_clause = ""
        terindeks_params = []
        if terindeks_filter and terindeks_filter != 'all':
            if terindeks_filter == 'Other':
                terindeks_filter_clause = "AND (a.v_terindeks IS NULL OR a.v_terindeks = '' OR LOWER(TRIM(a.v_terindeks)) NOT IN ('scopus', 'wos', 'doaj', 'garuda', 'sinta'))"
            else:
                terindeks_filter_clause = "AND LOWER(TRIM(COALESCE(a.v_terindeks, ''))) = LOWER(%s)"
                terindeks_params.append(terindeks_filter)
        
        # Get aggregate statistics with median and faculty filter
        # Count all publikasi, not just those with jurusan
        if faculty_filter:
            # If faculty filter applied, only count publications with matching jurusan
            stats_query = f"""
                {latest_publikasi_cte}
                SELECT
                    COUNT(*) as total_publikasi,
                    COALESCE(SUM(p.n_total_sitasi), 0) as total_sitasi,
                    COALESCE(AVG(p.n_total_sitasi), 0) as avg_sitasi,
                    COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY p.n_total_sitasi), 0) as median_sitasi
                FROM latest_publikasi p
                LEFT JOIN publikasi_with_jurusan pj ON p.v_id_publikasi = pj.v_id_publikasi
                LEFT JOIN stg_artikel_dr a ON p.v_id_publikasi = a.v_id_publikasi
                {faculty_filter}
                {terindeks_filter_clause}
            """
        else:
            # No filter, count all publikasi
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
        cur.execute(stats_query, params + faculty_params + terindeks_params)
        stats = cur.fetchone()
        
        print(f"📊 Stats result: {stats}")
        
        return jsonify({
            'totalPublikasi': stats['total_publikasi'] or 0,
            'totalSitasi': int(stats['total_sitasi']) if stats['total_sitasi'] else 0,
            'avgSitasi': round(float(stats['avg_sitasi']), 1) if stats['avg_sitasi'] else 0,
            'medianSitasi': round(float(stats['median_sitasi']), 1) if stats['median_sitasi'] else 0
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
        return jsonify({'error': 'Failed to fetch SINTA publikasi statistics'}), 500
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
                'faculties': faculties
            }), 200
            
        except Exception as query_error:
            import traceback
            print(f"❌ Query error: {query_error}")
            print(traceback.format_exc())
            # Return all faculties if query fails
            faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
            print(f"⚠️ Using complete faculty list ({len(faculties)} faculties)")
            return jsonify({
                'faculties': faculties
            }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Get publikasi faculties error:\n", error_details)
        logger.error(f"Get publikasi faculties error: {e}\n{error_details}")
        
        # Return all faculties even on major error
        faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
        return jsonify({
            'faculties': faculties
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
                'departments': mapped_departments
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
                'departments': sorted(filtered_departments)
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
        print("❌ Get publikasi departments error:\n", error_details)
        logger.error(f"Get publikasi departments error: {e}\n{error_details}")
        # Return mapped departments even on major error
        mapped_departments = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
        return jsonify({
            'departments': mapped_departments
        }), 200
        
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

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
            return jsonify({'error': 'Database connection failed'}), 500
        
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
            'data': scholar_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'pages': (total + per_page - 1) // per_page
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
        return jsonify({'error': 'Failed to fetch Scholar dosen data'}), 500
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
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
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
        
        # Get aggregate statistics from CTE with median
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
        
        return jsonify({
            'totalDosen': stats['total_dosen'] or 0,
            'totalSitasi': int(stats['total_sitasi']) if stats['total_sitasi'] else 0,
            'avgHIndex': round(float(stats['avg_h_index']), 1) if stats['avg_h_index'] else 0,
            'medianHIndex': round(float(stats['median_h_index']), 1) if stats['median_h_index'] else 0,
            'totalPublikasi': stats['total_publikasi'] or 0,
            'avgI10Index': round(float(stats['avg_i10_index']), 1) if stats['avg_i10_index'] else 0,
            'avgHIndex2020': round(float(stats['avg_h_index_2020']), 1) if stats['avg_h_index_2020'] else 0,
            'avgI10Index2020': round(float(stats['avg_i10_index_2020']), 1) if stats['avg_i10_index_2020'] else 0
        }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Scholar Dosen stats error:\n", error_details)
        logger.error(f"Get Scholar dosen stats error: {e}\n{error_details}")
        return jsonify({'error': 'Failed to fetch Scholar dosen statistics'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# Faculty mapping based on department names
FACULTY_DEPARTMENT_MAPPING = {
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
            return jsonify({'error': 'Database connection failed'}), 500
        
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
                'faculties': faculties
            }), 200
            
        except Exception as query_error:
            import traceback
            print(f"❌ Query error: {query_error}")
            print(traceback.format_exc())
            # Return all faculties if query fails
            faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
            print(f"⚠️ Using complete faculty list ({len(faculties)} faculties)")
            return jsonify({
                'faculties': faculties
            }), 200
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print("❌ Get faculties error:\n", error_details)
        logger.error(f"Get faculties error: {e}\n{error_details}")
        
        # Return all faculties even on major error
        faculties = sorted(list(FACULTY_DEPARTMENT_MAPPING.keys()))
        return jsonify({
            'faculties': faculties
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
            return jsonify({'error': 'Faculty parameter is required'}), 400
        
        # Get departments from mapping first
        mapped_departments = FACULTY_DEPARTMENT_MAPPING.get(faculty, [])
        print(f"📋 Mapped departments for {faculty}: {mapped_departments}")
        
        conn = get_db_connection()
        if not conn:
            print("❌ Database connection failed, using mapped departments")
            return jsonify({
                'departments': mapped_departments
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
                'departments': sorted(filtered_departments)
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
            'departments': mapped_departments
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
            return jsonify({'error': 'Database connection failed'}), 500
        
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
            "error": "Database query failed",
            "details": str(db_error)
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
            "error": "Failed to fetch Scholar publikasi data",
            "details": str(e)
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
            return jsonify({'error': 'Database connection failed'}), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
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
        
        # Create CTE for latest publikasi with jurusan filter
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
        
        cte_params = params + jurusan_params
        
        # Get aggregate statistics with median
        # Always count all publikasi, not just those with jurusan
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
        
        return jsonify({
            'totalPublikasi': stats['total_publikasi'] or 0,
            'totalSitasi': int(stats['total_sitasi']) if stats['total_sitasi'] else 0,
            'avgSitasi': round(float(stats['avg_sitasi']), 1) if stats['avg_sitasi'] else 0,
            'medianSitasi': round(float(stats['median_sitasi']), 1) if stats['median_sitasi'] else 0
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
        return jsonify({'error': 'Failed to fetch Scholar publikasi statistics'}), 500
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
        port=int(os.environ.get('PORT', 0)),
        allow_unsafe_werkzeug=True
    )