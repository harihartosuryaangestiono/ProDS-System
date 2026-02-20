from flask import Blueprint, request, jsonify, current_app
from flask_socketio import emit
import sys
import os
from datetime import datetime
import threading
import traceback

# Add scrapers directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'scrapers'))
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.database import DB_CONFIG
from task.scraping_tasks import (
    scrape_sinta_dosen_task,
    scrape_sinta_scopus_task,
    scrape_sinta_googlescholar_task,
    scrape_sinta_garuda_task
)
from flask_cors import cross_origin

scraping_bp = Blueprint('scraping', __name__)

# Store active jobs
active_jobs = {}

def emit_progress(job_id, progress_data):
    """Emit progress update via SocketIO"""
    try:
        from app import socketio
        socketio.emit('scraping_progress', {
            'job_id': job_id,
            'progress': progress_data
        })
        print(f"✅ Progress emitted for job {job_id}: {progress_data.get('message', 'N/A')}")
    except Exception as e:
        print(f"⚠️ Error emitting progress: {e}")

def run_scraping_task(job_id, task_func, task_kwargs):
    """Run scraping task in background thread"""
    try:
        print(f"\n🚀 Starting scraping task - Job ID: {job_id}")
        print(f"📝 Task function: {task_func.__name__}")
        print(f"📋 Task kwargs: {list(task_kwargs.keys())}")

        active_jobs[job_id] = {
            'status': 'running',
            'started_at': datetime.now().isoformat(),
            'progress': 0,
            'current': 0,
            'total': task_kwargs.get('target_dosen', 100),
            'message': 'Starting scraping task...'
        }

        emit_progress(job_id, active_jobs[job_id])

        task_kwargs['job_id'] = job_id
        print(f"🔄 Executing task function...")
        result = task_func(**task_kwargs)

        active_jobs[job_id].update({
            'status': 'completed',
            'completed_at': datetime.now().isoformat(),
            'result': result,
            'message': result.get('message', 'Scraping completed successfully!')
        })

        print(f"✅ Task completed successfully - Job ID: {job_id}")

        emit_progress(job_id, {
            'status': 'completed',
            'message': result.get('message', 'Scraping completed!'),
            'result': result
        })

    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()

        print(f"\n❌ Task failed - Job ID: {job_id}")
        print(f"Error: {error_msg}")
        print(f"Traceback:\n{traceback_msg}")

        active_jobs[job_id].update({
            'status': 'failed',
            'error': error_msg,
            'traceback': traceback_msg,
            'failed_at': datetime.now().isoformat(),
            'message': f'Scraping failed: {error_msg}'
        })

        emit_progress(job_id, {
            'status': 'failed',
            'error': error_msg,
            'message': f'Scraping failed: {error_msg}'
        })

# ============================================================================
# SINTA ROUTES
# ============================================================================

@scraping_bp.route('/api/scraping/sinta/dosen', methods=['POST', 'OPTIONS'])
@cross_origin(origins=['http://10.211.1.188:3000'], supports_credentials=True)
def scrape_sinta_dosen():
    """Endpoint untuk scraping SINTA Dosen"""
    print("\n" + "="*60)
    print("📥 Received request to /api/scraping/sinta/dosen")
    print("="*60)

    if request.method == 'OPTIONS':
        return '', 204

    try:
        data = request.get_json()
        print(f"📋 Request data: {data}")

        required_fields = ['username', 'password']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Field {field} is required'}), 400

        affiliation_id = data.get('affiliation_id') or '1397'
        max_cycles = int(data.get('max_cycles') or 20)
        max_pages = data.get('max_pages')
        target_dosen = data.get('target_dosen')

        job_id = f"sinta_dosen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        print(f"🆔 Generated job ID: {job_id}")

        active_jobs[job_id] = {
            'status': 'starting',
            'current': 0,
            'total': target_dosen or 0,
            'message': 'Initializing SINTA Dosen scraping...',
            'started_at': datetime.now().isoformat()
        }

        task_kwargs = {
            'username': data['username'],
            'password': data['password'],
            'affiliation_id': affiliation_id,
            'target_dosen': target_dosen,
            'max_pages': max_pages,
            'max_cycles': max_cycles
        }

        thread = threading.Thread(
            target=run_scraping_task,
            args=(job_id, scrape_sinta_dosen_task, task_kwargs)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'SINTA Dosen scraping started',
            'job_id': job_id
        }), 200

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scraping_bp.route('/api/scraping/sinta/scopus', methods=['POST'])
def scrape_sinta_scopus():
    try:
        data = request.get_json()
        for field in ['username', 'password']:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Field {field} is required'}), 400

        job_id = f"sinta_scopus_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_jobs[job_id] = {'status': 'starting', 'message': 'Initializing Scopus scraping...', 'started_at': datetime.now().isoformat()}

        thread = threading.Thread(target=run_scraping_task, args=(job_id, scrape_sinta_scopus_task, {'username': data['username'], 'password': data['password']}))
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Scopus scraping job started', 'job_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scraping_bp.route('/api/scraping/sinta/googlescholar', methods=['POST'])
def scrape_sinta_googlescholar():
    try:
        data = request.get_json()
        for field in ['username', 'password']:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Field {field} is required'}), 400

        job_id = f"sinta_gs_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_jobs[job_id] = {'status': 'starting', 'message': 'Initializing Google Scholar scraping...', 'started_at': datetime.now().isoformat()}

        thread = threading.Thread(target=run_scraping_task, args=(job_id, scrape_sinta_googlescholar_task, {'username': data['username'], 'password': data['password']}))
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Google Scholar scraping job started', 'job_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scraping_bp.route('/api/scraping/sinta/garuda', methods=['POST'])
def scrape_sinta_garuda():
    try:
        data = request.get_json()
        for field in ['username', 'password']:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Field {field} is required'}), 400

        job_id = f"sinta_garuda_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        active_jobs[job_id] = {'status': 'starting', 'message': 'Initializing Garuda scraping...', 'started_at': datetime.now().isoformat()}

        thread = threading.Thread(target=run_scraping_task, args=(job_id, scrape_sinta_garuda_task, {'username': data['username'], 'password': data['password']}))
        thread.daemon = True
        thread.start()

        return jsonify({'success': True, 'message': 'Garuda scraping job started', 'job_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# CANCEL ENDPOINT
# ============================================================================
@scraping_bp.route('/api/scraping/jobs/<job_id>/cancel', methods=['POST'])
def cancel_job(job_id):
    try:
        job = active_jobs.get(job_id)
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404

        job['cancel_requested'] = True
        job['status'] = 'cancelling'
        job['message'] = 'Cancellation requested by user'

        emit_progress(job_id, job)
        return jsonify({'success': True, 'message': 'Cancellation requested', 'job_id': job_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# GOOGLE SCHOLAR - GS PUBLIKASI (menggunakan GoogleScholarScraper dari gs_scraper.py)
# ============================================================================

def run_google_scholar_scraping(job_id, max_authors, scrape_from_beginning):
    """Run Google Scholar scraping in background thread"""
    try:
        from gs_scraper import GoogleScholarScraper

        active_jobs[job_id] = {
            'status': 'running',
            'current': 0,
            'total': max_authors,
            'message': 'Initializing scraper...',
            'started_at': datetime.now().isoformat()
        }

        emit_progress(job_id, active_jobs[job_id])

        scraper = GoogleScholarScraper(
            db_config=DB_CONFIG,
            job_id=job_id,
            progress_callback=lambda data: emit_progress(job_id, data)
        )

        result = scraper.run(max_authors=max_authors, scrape_from_beginning=scrape_from_beginning)

        active_jobs[job_id].update({
            'status': 'completed',
            'message': 'Scraping completed successfully!',
            'completed_at': datetime.now().isoformat(),
            'result': result
        })

        emit_progress(job_id, {
            'status': 'completed',
            'message': result.get('message', 'Scraping completed'),
            'summary': result.get('summary', {})
        })

    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()

        print(f"\n❌ ERROR: {error_msg}")
        print(f"Traceback:\n{traceback_msg}")

        active_jobs[job_id].update({
            'status': 'failed',
            'message': error_msg,
            'error': error_msg,
            'traceback': traceback_msg,
            'failed_at': datetime.now().isoformat()
        })

        emit_progress(job_id, {
            'status': 'failed',
            'error': error_msg,
            'traceback': traceback_msg
        })


@scraping_bp.route('/api/scraping/googlescholar/scrape', methods=['POST'])
def scrape_google_scholar():
    """Endpoint untuk scraping publikasi Google Scholar langsung (GS Publikasi)"""
    try:
        data = request.get_json() or {}
        max_authors = data.get('max_authors', 10)
        scrape_from_beginning = data.get('scrape_from_beginning', False)

        if not isinstance(max_authors, int) or max_authors <= 0:
            return jsonify({'success': False, 'error': 'max_authors must be a positive integer'}), 400

        job_id = f"gs_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        active_jobs[job_id] = {
            'status': 'starting',
            'current': 0,
            'total': max_authors,
            'message': 'Initializing Google Scholar scraping...',
            'started_at': datetime.now().isoformat()
        }

        thread = threading.Thread(
            target=run_google_scholar_scraping,
            args=(job_id, max_authors, scrape_from_beginning)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Google Scholar scraping started with auto-login.',
            'job_id': job_id
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ============================================================================
# GOOGLE SCHOLAR - GS DOSEN
# FIX: Sebelumnya memakai dosen_unpar.get_all_unpar_scholars yang tidak ada.
#      Sekarang menggunakan GoogleScholarScraper yang sudah ada di gs_scraper.py
#      dengan mode khusus untuk scraping profil dosen dari halaman pencarian GS.
# ============================================================================

def run_google_scholar_dosen_scraping(job_id, max_pages, search_query):
    """
    Run Google Scholar dosen profile scraping in background thread.

    Pendekatan:
    - Gunakan GoogleScholarScraper (gs_scraper.py) yang sudah punya auto-login.
    - Ambil daftar dosen dari temp_dosenGS_scraping (query ke DB).
    - max_pages dikonversi menjadi max_authors (estimasi 1 dosen per baris di DB).
    """
    try:
        from gs_scraper import GoogleScholarScraper

        # Update status awal
        active_jobs[job_id].update({
            'status': 'running',
            'message': 'Initializing Google Scholar Dosen scraper with auto-login...'
        })
        emit_progress(job_id, active_jobs[job_id])

        # Konversi max_pages ke max_authors
        # Jika user memberi max_pages, kita gunakan itu sebagai batas jumlah dosen
        max_authors = max_pages  # 1 halaman ≈ 1 dosen dalam konteks DB kita

        print(f"\n🔍 GS Dosen scraping started")
        print(f"   max_authors (from max_pages): {max_authors}")
        print(f"   search_query (not used for DB mode): {search_query}")

        # Progress callback yang update active_jobs sekaligus
        def progress_callback(data):
            active_jobs[job_id].update(data)
            emit_progress(job_id, data)

        scraper = GoogleScholarScraper(
            db_config=DB_CONFIG,
            job_id=job_id,
            progress_callback=progress_callback
        )

        # Jalankan scraping (ambil daftar dosen dari DB, bukan dari pencarian GS)
        result = scraper.run(
            max_authors=max_authors,
            scrape_from_beginning=False  # Lanjutkan dari yang belum selesai
        )

        # Pastikan result tidak None
        if result is None:
            result = {
                'success': False,
                'message': 'Scraper returned no result. Check logs for details.',
                'summary': {}
            }

        active_jobs[job_id].update({
            'status': 'completed',
            'message': result.get('message', 'Scraping selesai!'),
            'completed_at': datetime.now().isoformat(),
            'result': result
        })

        emit_progress(job_id, {
            'status': 'completed',
            'message': result.get('message', 'Scraping selesai!'),
            'summary': result.get('summary', {})
        })

        print(f"✅ GS Dosen scraping completed: {result}")

    except Exception as e:
        error_msg = str(e)
        traceback_msg = traceback.format_exc()

        print(f"\n❌ GS Dosen ERROR: {error_msg}")
        print(f"Traceback:\n{traceback_msg}")

        active_jobs[job_id].update({
            'status': 'failed',
            'message': error_msg,
            'error': error_msg,
            'traceback': traceback_msg,
            'failed_at': datetime.now().isoformat()
        })

        emit_progress(job_id, {
            'status': 'failed',
            'error': error_msg,
            'traceback': traceback_msg,
            'message': f'Scraping gagal: {error_msg}'
        })


@scraping_bp.route('/api/scraping/googlescholar/dosen', methods=['POST'])
def scrape_google_scholar_dosen():
    """
    Endpoint untuk scraping profil dosen dari Google Scholar dengan auto-login.

    Request Body:
    {
        "max_pages": 20,        // jumlah dosen yang akan di-scrape (default: 20)
        "search_query": "..."   // tidak digunakan dalam mode DB, disimpan untuk kompatibilitas
    }
    """
    try:
        data = request.get_json() or {}
        max_pages = data.get('max_pages', 20)
        search_query = data.get(
            'search_query',
            '"Universitas Katolik Parahyangan" OR "Parahyangan Catholic University" OR "unpar"'
        )

        if not isinstance(max_pages, int) or max_pages <= 0:
            return jsonify({'success': False, 'error': 'max_pages must be a positive integer'}), 400

        if max_pages > 500:
            return jsonify({'success': False, 'error': 'max_pages cannot exceed 500'}), 400

        job_id = f"gs_dosen_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        active_jobs[job_id] = {
            'status': 'starting',
            'current': 0,
            'total': max_pages,
            'message': 'Initializing Google Scholar dosen scraping with auto-login...',
            'started_at': datetime.now().isoformat()
        }

        thread = threading.Thread(
            target=run_google_scholar_dosen_scraping,
            args=(job_id, max_pages, search_query)
        )
        thread.daemon = True
        thread.start()

        return jsonify({
            'success': True,
            'message': 'Google Scholar dosen scraping started with auto-login.',
            'job_id': job_id,
            'instructions': 'The scraper will automatically login using the configured accounts. No manual action required.',
            'max_pages': max_pages,
            'search_query': search_query
        }), 200

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e),
            'traceback': traceback.format_exc()
        }), 500


# ============================================================================
# JOB STATUS ROUTES
# ============================================================================

@scraping_bp.route('/api/scraping/googlescholar/dosen/status/<job_id>', methods=['GET'])
def get_scraping_status(job_id):
    try:
        if job_id not in active_jobs:
            return jsonify({'success': False, 'error': f'Job {job_id} not found'}), 404
        return jsonify({'success': True, 'job_id': job_id, **active_jobs[job_id]}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scraping_bp.route('/api/scraping/googlescholar/dosen/jobs', methods=['GET'])
def list_scraping_jobs():
    try:
        jobs_list = [{'job_id': jid, **jdata} for jid, jdata in active_jobs.items()]
        jobs_list.sort(key=lambda x: x.get('started_at', ''), reverse=True)
        return jsonify({'success': True, 'jobs': jobs_list, 'total': len(jobs_list)}), 200
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@scraping_bp.route('/api/scraping/jobs/<job_id>', methods=['GET'])
def get_job_status(job_id):
    print(f"\n📊 Job status requested for: {job_id}")
    if job_id in active_jobs:
        return jsonify({'success': True, 'job': active_jobs[job_id]}), 200
    return jsonify({'success': False, 'error': 'Job not found'}), 404


@scraping_bp.route('/api/scraping/jobs', methods=['GET'])
def list_jobs():
    return jsonify({'success': True, 'jobs': active_jobs, 'total_jobs': len(active_jobs)}), 200


@scraping_bp.route('/api/scraping/jobs/<job_id>', methods=['DELETE'])
def delete_job(job_id):
    if job_id in active_jobs:
        del active_jobs[job_id]
        return jsonify({'success': True, 'message': f'Job {job_id} deleted'}), 200
    return jsonify({'success': False, 'error': 'Job not found'}), 404


@scraping_bp.route('/api/scraping/health', methods=['GET'])
def scraping_health():
    running_jobs = len([j for j in active_jobs.values() if j.get('status') == 'running'])
    return jsonify({
        'success': True,
        'status': 'healthy',
        'active_jobs_count': running_jobs,
        'total_jobs': len(active_jobs),
        'jobs': list(active_jobs.keys())
    }), 200