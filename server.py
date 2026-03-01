# © সাংখ্য চক্রবর্তী (Sankhya Chakravarty). All rights reserved.
"""
Dictionary Server — serves static files + API to save edits to edits.json
The original all_entries.json is NEVER modified.
Edits are stored separately in abhidhan/ParsedJSON_Merged/edits.json
Usage:  python server.py [port]        (default port: 8080)
"""
import http.server, json, os, sys, threading
from datetime import datetime

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EDITS_PATH = os.path.join(BASE_DIR, 'abhidhan', 'ParsedJSON_Merged', 'edits.json')
BHASHA_EDITS_DIR = os.path.join(BASE_DIR, 'bhashatattwa', 'EditedHTML')
BHASHA_IMAGES_DIR = os.path.join(BASE_DIR, 'bhashatattwa', 'EditImages')
os.makedirs(BHASHA_EDITS_DIR, exist_ok=True)
os.makedirs(BHASHA_IMAGES_DIR, exist_ok=True)

# Thread lock for safe concurrent writes
write_lock = threading.Lock()


def load_edits():
    if os.path.exists(EDITS_PATH):
        with open(EDITS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_edits_file(edits):
    print(f'[SAVE] Writing to: {EDITS_PATH}', flush=True)
    with open(EDITS_PATH, 'w', encoding='utf-8') as f:
        json.dump(edits, f, ensure_ascii=False, indent=2)
    print(f'[SAVE] Done. File size: {os.path.getsize(EDITS_PATH)}', flush=True)


class DictHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    def do_POST(self):
        if self.path == '/api/save-entry':
            self._handle_save_entry()
        elif self.path == '/api/revert-entry':
            self._handle_revert_entry()
        elif self.path == '/api/bhasha-save':
            self._handle_bhasha_save()
        elif self.path == '/api/bhasha-upload-image':
            self._handle_bhasha_upload_image()
        else:
            self.send_error(404, 'Not Found')

    def _read_body(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        return json.loads(body.decode('utf-8'))

    def _json_response(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _handle_save_entry(self):
        try:
            payload = self._read_body()
            # Key = originalHeadword|source_page
            orig_hw = payload.get('originalHeadword', '')
            source_page = payload.get('source_page', '')
            new_data = payload.get('data', {})
            user = payload.get('user', 'Anonymous')
            key = f"{orig_hw}|{source_page}"

            with write_lock:
                edits = load_edits()

                if key not in edits:
                    edits[key] = {
                        'originalHeadword': orig_hw,
                        'source_page': source_page,
                        'versions': []
                    }

                edits[key]['versions'].append({
                    'date': datetime.now().isoformat(),
                    'user': user,
                    'data': {k: v for k, v in new_data.items()
                             if k in ('headword', 'transliteration', 'phonetics',
                                      'etymology', 'notes', 'senses')}
                })
                # Also store latest snapshot for easy merging
                edits[key]['latest'] = {k: v for k, v in new_data.items()
                                        if k in ('headword', 'transliteration', 'phonetics',
                                                 'etymology', 'notes', 'senses')}

                save_edits_file(edits)

            self._json_response({'ok': True, 'message': 'Edit saved'})

        except Exception as ex:
            import traceback
            traceback.print_exc()
            self._json_response({'ok': False, 'message': str(ex)}, 500)

    def _handle_revert_entry(self):
        try:
            payload = self._read_body()
            orig_hw = payload.get('headword', '')
            source_page = payload.get('source_page', '')
            key = f"{orig_hw}|{source_page}"

            with write_lock:
                edits = load_edits()
                if key in edits:
                    del edits[key]
                    save_edits_file(edits)
                    self._json_response({'ok': True, 'message': 'Edit reverted'})
                else:
                    self._json_response({'ok': True, 'message': 'No edit found (already clean)'})

        except Exception as ex:
            self._json_response({'ok': False, 'message': str(ex)}, 500)

    def _handle_bhasha_save(self):
        """Save edited HTML for a bhashatattwa page."""
        try:
            payload = self._read_body()
            page_num = payload.get('page')
            html_content = payload.get('html', '')
            user = payload.get('user', 'Anonymous')

            if not page_num:
                self._json_response({'ok': False, 'message': 'Missing page number'}, 400)
                return

            fname = f'page_{int(page_num):04d}.html'
            fpath = os.path.join(BHASHA_EDITS_DIR, fname)

            with write_lock:
                with open(fpath, 'w', encoding='utf-8') as f:
                    f.write(html_content)

            print(f'[BHASHA] Saved page {page_num} by {user} ({len(html_content)} chars)', flush=True)
            self._json_response({'ok': True, 'message': f'Page {page_num} saved'})

        except Exception as ex:
            import traceback
            traceback.print_exc()
            self._json_response({'ok': False, 'message': str(ex)}, 500)

    def _handle_bhasha_upload_image(self):
        """Upload an image for a bhashatattwa page edit."""
        import base64
        try:
            payload = self._read_body()
            page_num = payload.get('page')
            b64_data = payload.get('data', '')
            ext = payload.get('ext', 'png').lower()
            orig_name = payload.get('filename', 'image')

            if not page_num or not b64_data:
                self._json_response({'ok': False, 'message': 'Missing page or data'}, 400)
                return

            # Sanitise extension
            if ext not in ('png', 'jpg', 'jpeg', 'gif', 'webp', 'svg'):
                ext = 'png'

            # Generate unique filename
            ts = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
            fname = f'page{int(page_num):04d}_{ts}.{ext}'
            fpath = os.path.join(BHASHA_IMAGES_DIR, fname)

            img_bytes = base64.b64decode(b64_data)
            with write_lock:
                with open(fpath, 'wb') as f:
                    f.write(img_bytes)

            # Return the URL relative to server root so it can be used in <img src>
            rel_url = f'bhashatattwa/EditImages/{fname}'
            print(f'[BHASHA-IMG] Saved {fname} ({len(img_bytes)} bytes)', flush=True)
            self._json_response({'ok': True, 'url': rel_url, 'filename': fname})

        except Exception as ex:
            import traceback
            traceback.print_exc()
            self._json_response({'ok': False, 'message': str(ex)}, 500)

    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()


print(f'Dictionary server starting on http://localhost:{PORT}')
print(f'Edits file: {EDITS_PATH}')
print(f'Serving from: {BASE_DIR}')
httpd = http.server.ThreadingHTTPServer(('', PORT), DictHandler)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    print('\nServer stopped.')
