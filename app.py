from http.server import BaseHTTPRequestHandler, HTTPServer
from email.parser import BytesParser
from email.policy import default
from pathlib import Path
from urllib.parse import unquote
import io, json, os, re, uuid, zipfile

from grant_engine import process_bundle, _validation_grants

ROOT = Path(__file__).resolve().parent
RESULTS = {}
MAX_UPLOAD = 50 * 1024 * 1024

class Handler(BaseHTTPRequestHandler):
    def send_bytes(self, data, mime, name=None):
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(len(data)))
        if name:
            self.send_header('Content-Disposition', f'attachment; filename="{name}"')
        self.end_headers(); self.wfile.write(data)

    def do_GET(self):
        path = unquote(self.path.split('?', 1)[0])
        if path == '/':
            return self.send_bytes((ROOT / 'templates' / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        if path == '/tour':
            return self.send_bytes((ROOT / 'templates' / 'tour.html').read_bytes(), 'text/html; charset=utf-8')
        if path == '/download/tidepath-grant-webapp.zip':
            package = io.BytesIO()
            with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as bundle:
                for candidate in ROOT.rglob('*'):
                    if not candidate.is_file() or '__pycache__' in candidate.parts or '.git' in candidate.parts:
                        continue
                    bundle.write(candidate, candidate.relative_to(ROOT).as_posix())
            return self.send_bytes(package.getvalue(), 'application/zip', 'tidepath-grant-webapp.zip')
        if path == '/validation-grants':
            data = json.dumps(_validation_grants(include_documents=True), ensure_ascii=False).encode('utf-8')
            return self.send_bytes(data, 'application/json; charset=utf-8')
        bits = path.strip('/').split('/')
        if len(bits) == 3 and bits[0] == 'validation-documents' and re.fullmatch(r'VAL-(AP|OK|DN)-\d{2}', bits[1]) and re.fullmatch(r'[A-Za-z0-9_.-]+', bits[2]):
            group = {'AP':'applying','OK':'approved','DN':'completed'}[bits[1].split('-')[1]]
            base = (ROOT / 'validation_documents' / group / bits[1]).resolve()
            target = (base / bits[2]).resolve()
            if target.parent == base and target.is_file():
                mime = 'text/csv; charset=utf-8' if target.suffix.lower() == '.csv' else 'text/markdown; charset=utf-8'
                return self.send_bytes(target.read_bytes(), mime, target.name)
        if path in ('/static/app.css', '/static/app.js', '/static/tour.css', '/static/tour.js'):
            f = ROOT / path.lstrip('/')
            return self.send_bytes(f.read_bytes(), 'text/css; charset=utf-8' if f.suffix == '.css' else 'text/javascript; charset=utf-8')
        bits = path.strip('/').split('/')
        if len(bits) == 3 and bits[0] == 'download' and bits[1] in RESULTS:
            result = RESULTS[bits[1]]
            key = 'workbook' if bits[2] == 'workbook' else 'package' if bits[2] == 'package' else 'ics' if bits[2] == 'calendar' else None
            if key:
                mime={'workbook':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','package':'application/zip','ics':'text/calendar; charset=utf-8'}[key]
                name={'workbook':'grant-summary.xlsx','package':'grant-analysis-output.zip','ics':'grant-bookkeeper-reminders.ics'}[key]
                return self.send_bytes(result[key], mime, name)
        self.send_error(404)

    def do_POST(self):
        if self.path != '/analyze':
            return self.send_error(404)
        length = int(self.headers.get('Content-Length', '0'))
        if length <= 0 or length > MAX_UPLOAD:
            return self.send_error(413, 'Upload must be a ZIP file up to 50 MB')
        raw = self.rfile.read(length)
        message = BytesParser(policy=default).parsebytes((f'Content-Type: {self.headers.get("Content-Type")}\r\nMIME-Version: 1.0\r\n\r\n').encode() + raw)
        fields = {}
        for part in message.iter_parts():
            name = part.get_param('name', header='content-disposition')
            if not name: continue
            payload = part.get_payload(decode=True) or b''
            if part.get_filename(): fields[name] = (part.get_filename(), payload)
            else: fields[name] = payload.decode('utf-8', 'replace')
        upload = fields.get('bundle')
        if not upload or not upload[0].lower().endswith('.zip'):
            return self.json_error('Choose a ZIP package to upload.', 400)
        try:
            result = process_bundle(upload[1], fields.get('as_of', ''), float(fields.get('threshold', '85')), fields.get('use_openai') == 'on', fields.get('openai_api_key',''), fields.get('openai_model','gpt-4.1-mini'), fields.get('facts_approved') == 'on')
        except Exception as exc:
            return self.json_error(str(exc), 400)
        key = str(uuid.uuid4())
        RESULTS[key] = result
        while len(RESULTS) > 5: RESULTS.pop(next(iter(RESULTS)))
        return self.send_bytes(json.dumps({'id': key, 'summary': result['summary'], 'warnings': result['warnings'], 'previews': result['previews'], 'operations': result['operations']}, ensure_ascii=False).encode(), 'application/json; charset=utf-8')

    def json_error(self, message, status):
        data = json.dumps({'error': message}, ensure_ascii=False).encode()
        self.send_response(status); self.send_header('Content-Type', 'application/json; charset=utf-8'); self.send_header('Content-Length', str(len(data))); self.end_headers(); self.wfile.write(data)

    def log_message(self, fmt, *args):
        print('%s - %s' % (self.address_string(), fmt % args))

if __name__ == '__main__':
    port = int(os.environ.get('TIDEPATH_PORT', '8765'))
    print(f'Grant workbook app: http://127.0.0.1:{port}')
    HTTPServer(('127.0.0.1', port), Handler).serve_forever()
