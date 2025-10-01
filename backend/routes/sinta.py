# file: backend/routes/sinta.py

from flask import Blueprint, jsonify, request
from utils.database import get_db_connection
import psycopg2
import psycopg2.extras
from utils.auth_utils import token_required
import logging
from datetime import datetime
import traceback

# Setup logger
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sinta_bp = Blueprint('sinta', __name__, url_prefix='/api/sinta')

# ==========================================
# MAIN ENDPOINTS
# ==========================================

@sinta_bp.route('/publikasi', methods=['GET'])
@token_required
def get_sinta_publikasi(current_user_id):
    """Get SINTA publications data with pagination and search."""
    conn = None
    cur = None
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()

        if page < 1 or per_page < 1 or per_page > 100:
            return jsonify({'success': False, 'error': 'Invalid page or per_page value'}), 400

        offset = (page - 1) * per_page

        logger.info(f"Fetching publications: page={page}, per_page={per_page}, search='{search}'")

        conn = get_db_connection()
        if not conn:
            logger.error("Database connection could not be established.")
            return jsonify({'success': False, 'error': 'Database connection failed'}), 500

        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # Base query and where clause
        base_query = "FROM stg_publikasi_tr"
        where_clause = "WHERE v_sumber IN ('Sinta_Scopus', 'Sinta_GoogleScholar', 'SINTA_Garuda')"
        params = []

        if search:
            where_clause += " AND LOWER(v_judul) LIKE LOWER(%s)"
            params.append(f'%{search}%')

        # Get total count
        count_query = f"SELECT COUNT(*) as total {base_query} {where_clause}"
        cur.execute(count_query, tuple(params))
        total_records = cur.fetchone()['total']

        # Get publications data
        data_query = f"""
            SELECT 
                v_id_publikasi, v_judul, v_jenis, v_tahun_publikasi,
                n_total_sitasi, v_sumber, v_link_url
            {base_query}
            {where_clause}
            ORDER BY v_tahun_publikasi DESC NULLS LAST, v_judul
            LIMIT %s OFFSET %s
        """
        data_params = tuple(params + [per_page, offset])
        cur.execute(data_query, data_params)
        publications = cur.fetchall()

        logger.info(f"Found {total_records} records, returning {len(publications)} for this page.")

        # Serialize datetime objects if any (good practice)
        for pub in publications:
            for key, value in pub.items():
                if isinstance(value, datetime):
                    pub[key] = value.isoformat()
        
        total_pages = (total_records + per_page - 1) // per_page if total_records > 0 else 1

        return jsonify({
            'success': True,
            'data': publications,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total_records,
                'total_pages': total_pages
            }
        }), 200

    except (ValueError, TypeError):
        logger.warning(f"Invalid parameter type received: {request.args}")
        return jsonify({'success': False, 'error': 'Invalid query parameters. page and per_page must be integers.'}), 400
    
    except psycopg2.Error as db_error:
        logger.error(f"Database error in get_sinta_publikasi: {db_error}", exc_info=True)
        return jsonify({'success': False, 'error': 'A database error occurred.'}), 500

    except Exception as e:
        logger.error(f"Unexpected error in get_sinta_publikasi: {e}", exc_info=True)
        # Di sinilah error 'list index out of range' dari scraper Anda akan tertangkap
        return jsonify({
            'success': False, 
            'error': 'An internal server error occurred.',
            'message': 'The error might be due to an issue with data scraping.'
        }), 500

    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

# Letakkan endpoint /dosen dan endpoint /test Anda yang lain di sini jika masih diperlukan
# ...


@sinta_bp.route('/dosen', methods=['GET'])
@token_required
def get_sinta_dosen(current_user_id):
    """Get SINTA dosen data"""
    conn = None
    cur = None
    try:
        logger.info("=== GET SINTA DOSEN CALLED ===")
        
        # Parse parameters
        try:
            page = max(1, int(request.args.get('page', 1)))
            per_page = max(1, min(100, int(request.args.get('per_page', 20))))
        except (ValueError, TypeError):
            return jsonify({
                'success': False,
                'error': 'Invalid page or per_page parameter'
            }), 400
        
        search = request.args.get('search', '').strip()
        offset = (page - 1) * per_page
        
        logger.info(f"Params - page: {page}, per_page: {per_page}, search: '{search}'")
        
        conn = get_db_connection()
        if not conn:
            logger.error("Database connection failed")
            return jsonify({
                'success': False,
                'error': 'Database connection failed'
            }), 500
        
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        where_clause = "WHERE d.v_sumber = 'SINTA' OR d.v_sumber IS NULL"
        params = []
        
        if search:
            where_clause += """ AND (
                LOWER(d.v_nama_dosen) LIKE LOWER(%s) OR 
                LOWER(j.v_nama_jurusan) LIKE LOWER(%s)
            )"""
            params.extend([f'%{search}%', f'%{search}%'])
        
        # Get total count
        count_query = f"""
            SELECT COUNT(*) as total 
            FROM tmp_dosen_dt d
            LEFT JOIN stg_jurusan_mt j ON d.v_id_jurusan = j.v_id_jurusan
            {where_clause}
        """
        cur.execute(count_query, params)
        total = cur.fetchone()['total']
        
        logger.info(f"Total dosen found: {total}")
        
        # Get data
        data_query = f"""
            SELECT 
                d.v_id_dosen,
                d.v_nama_dosen,
                d.v_id_sinta,
                d.v_id_googleScholar,
                d.n_total_publikasi,
                d.n_total_sitasi_gs,
                d.n_h_index_gs,
                d.n_i10_index_gs,
                d.v_id_jurusan,
                j.v_nama_jurusan,
                d.v_sumber,
                d.t_tanggal_unduh
            FROM tmp_dosen_dt d
            LEFT JOIN stg_jurusan_mt j ON d.v_id_jurusan = j.v_id_jurusan
            {where_clause}
            ORDER BY d.v_nama_dosen
            LIMIT %s OFFSET %s
        """
        params.extend([per_page, offset])
        cur.execute(data_query, params)
        dosen_data = cur.fetchall()
        
        logger.info(f"Retrieved {len(dosen_data)} dosen records")
        
        # Convert datetime
        for dosen in dosen_data:
            for key, value in dosen.items():
                if isinstance(value, datetime):
                    dosen[key] = value.isoformat()
        
        total_pages = (total + per_page - 1) // per_page if total > 0 else 1
        
        return jsonify({
            'success': True,
            'data': dosen_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': total,
                'total_pages': total_pages
            }
        }), 200
        
    except Exception as e:
        logger.error(f"Error in get_sinta_dosen: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500
    finally:
        if cur:
            try:
                cur.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass