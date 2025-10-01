from flask import Blueprint, jsonify, request
import pandas as pd
import os
from utils.auth_utils import token_required
import logging

logger = logging.getLogger(__name__)

scholar_bp = Blueprint('scholar', __name__)

@scholar_bp.route('/dosen', methods=['GET'])
@token_required
def get_scholar_dosen(current_user_id):
    """Get Google Scholar dosen data from CSV file"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        
        # Read CSV file
        csv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 
                               'frontend', 'dosen_unpar_gs.csv')
        df = pd.read_csv(csv_path)
        
        # Apply search filter if provided
        if search:
            search_lower = search.lower()
            df = df[
                df['Name'].str.lower().str.contains(search_lower, na=False) |
                df['Affiliation'].str.lower().str.contains(search_lower, na=False)
            ]
        
        # Calculate total and pages
        total = len(df)
        total_pages = (total + per_page - 1) // per_page
        
        # Apply pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        df_page = df.iloc[start_idx:end_idx]
        
        # Convert to list of dictionaries
        dosen_data = df_page.to_dict('records')
        
        return jsonify({
            'data': dosen_data,
            'total': total,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages
        })
        
    except Exception as e:
        logger.error(f"Error in get_scholar_dosen: {e}")
        return jsonify({'error': str(e)}), 500


@scholar_bp.route('/publikasi', methods=['GET'])
@token_required
def get_scholar_publikasi(current_user_id):
    """Get Google Scholar publikasi data from database"""
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 20))
        search = request.args.get('search', '').strip()
        
        from utils.database import get_db_connection
        conn = None
        cur = None
        
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            
            # Base query
            where_clause = "WHERE 1=1"
            if search:
                where_clause += f" AND v_judul ILIKE '%{search}%'"
            
            # Count total publikasi
            count_query = f"""
                SELECT COUNT(*) 
                FROM stg_publikasi_tr 
                {where_clause}
            """
            cur.execute(count_query)
            total = cur.fetchone()[0]
            
            # Get publikasi data with pagination
            data_query = f"""
                SELECT 
                    v_id_publikasi, 
                    v_judul, 
                    v_jenis, 
                    v_tahun_publikasi, 
                    n_total_sitasi, 
                    v_sumber, 
                    v_link_url
                FROM stg_publikasi_tr 
                {where_clause}
                ORDER BY v_tahun_publikasi DESC
                LIMIT %s OFFSET %s
            """
            
            offset = (page - 1) * per_page
            cur.execute(data_query, (per_page, offset))
            rows = cur.fetchall()
            
            publikasi_data = []
            for row in rows:
                publikasi_data.append({
                    'id': row[0],
                    'judul': row[1],
                    'jenis': row[2],
                    'tahun': row[3],
                    'sitasi': row[4],
                    'sumber': row[5],
                    'link': row[6]
                })
            
            # Calculate total pages
            total_pages = (total + per_page - 1) // per_page if total > 0 else 0
            
            return jsonify({
                'success': True,
                'data': {
                    'data': publikasi_data,
                    'pagination': {
                        'total': total,
                        'page': page,
                        'per_page': per_page,
                        'total_pages': total_pages
                    }
                }
            })
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if cur:
                cur.close()
            if conn:
                conn.close()
                
    except Exception as e:
        logger.error(f"Get Scholar publikasi error: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'error': str(e),
            'data': {
                'data': [],
                'pagination': {
                    'total': 0,
                    'page': 1,
                    'per_page': 20,
                    'total_pages': 0
                }
            }
        }), 500