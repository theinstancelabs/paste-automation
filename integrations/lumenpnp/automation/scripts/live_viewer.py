#!/usr/bin/env python3
"""LAN snapshots of OpenPnP/webcam plus a visible conversation and reply panel.

Run with uv run --with python-xlib --with pillow python automation/scripts/live_viewer.py
--bind LAN_IP. Token lives outside tracked files. No keyboard/mouse or filesystem endpoints.
"""
import argparse
import hashlib
import hmac
import html
import io
import json
import mimetypes
import os
from pathlib import Path
import secrets
import re
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, unquote, urlsplit
from html.parser import HTMLParser
from PIL import Image
from Xlib import X, display
from chat_mirror import ChatMirror
from message_outbox import MessageOutbox

REPOSITORY = Path(__file__).resolve().parents[2]
INSPECTION_DIR = (REPOSITORY / 'automation/evidence/2026-09-23/placement-review-1790317888491').resolve()
EVIDENCE_ROOT = (REPOSITORY / 'automation/evidence').resolve()
_ASSET_MAP_LOCK = threading.Lock()
_ASSET_MAP_SIGNATURE = None
_ASSET_MAP = {}
PASTE_STATUS_PATH = REPOSITORY / 'automation/paste/run-status.json'
PASTE_STATUSES = {'pending', 'running', 'blocked', 'completed'}


def paste_status():
    """Read the coordinator's public progress fields; never trigger any work."""
    try:
        value = json.loads(PASTE_STATUS_PATH.read_text(encoding='utf-8'))
        if not isinstance(value, dict):
            raise ValueError('status must be an object')
        status = value.get('status')
        if status not in PASTE_STATUSES:
            raise ValueError('invalid status')
        return {
            'phase': str(value.get('phase') or ''),
            'currentPad': value.get('currentPad'),
            'completedPads': value.get('completedPads', 0),
            'totalPads': value.get('totalPads', 0),
            'message': str(value.get('message') or ''),
            'updatedAt': str(value.get('updatedAt') or ''),
            'status': status,
        }
    except FileNotFoundError:
        return {'phase': 'waiting', 'currentPad': None, 'completedPads': 0,
                'totalPads': 0, 'message': 'Paste run has not started.',
                'updatedAt': '', 'status': 'pending'}


class _InspectionRefs(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []

    def handle_starttag(self, tag, attrs):
        self.urls.extend(value for key, value in attrs if key.lower() in ('href', 'src') and value)


def inspection_asset_map():
    """Cache references from the generated page, admitting only files within evidence trees."""
    global _ASSET_MAP_SIGNATURE, _ASSET_MAP
    report_path = INSPECTION_DIR / 'index.html'
    stat = report_path.stat()
    signature = (stat.st_mtime_ns, stat.st_size)
    with _ASSET_MAP_LOCK:
        if signature == _ASSET_MAP_SIGNATURE:
            return _ASSET_MAP
        report = report_path.read_text(encoding='utf-8')
        refs = _InspectionRefs()
        refs.feed(report)
        allowed = {}
        for reference in refs.urls:
            parts = urlsplit(html.unescape(reference))
            path = unquote(parts.path)
            if parts.scheme or parts.netloc or not path or path.startswith('/') or '\\' in path or '\x00' in path:
                continue
            try:
                source = (INSPECTION_DIR / path).resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if source.is_file() and (source.is_relative_to(INSPECTION_DIR) or source.is_relative_to(EVIDENCE_ROOT)):
                allowed[path] = source
        _ASSET_MAP_SIGNATURE, _ASSET_MAP = signature, allowed
        return _ASSET_MAP


def resolve_inspection_asset(name):
    """Resolve only a local reference present in the generated page."""
    if not isinstance(name, str) or not name or len(name) > 2048 or '\x00' in name or '\\' in name:
        return None
    name = unquote(name)
    if name.startswith('/') or name not in inspection_asset_map():
        return None
    return inspection_asset_map()[name]


def inspection_html():
    """Serve the fixed report with local references routed through its authenticated asset endpoint."""
    source = (INSPECTION_DIR / 'index.html').read_text(encoding='utf-8')
    pattern = re.compile(r'(?P<prefix>\b(?:href|src)\s*=\s*)(?P<quote>["\'])(?P<url>[^"\']*)(?P=quote)', re.I)

    def replace(match):
        url = html.unescape(match.group('url'))
        parts = urlsplit(url)
        path = unquote(parts.path)
        if parts.scheme or parts.netloc or not path:
            return match.group(0)
        if resolve_inspection_asset(path) is None:
            return match.group(0)
        routed = '/inspection/asset?file=' + quote(path, safe='')
        return f'{match.group("prefix")}{match.group("quote")}{routed}{match.group("quote")}'

    return pattern.sub(replace, source).encode('utf-8')


def validate_public_origin(value):
    """Accept only a bare HTTP(S) origin; it is compared literally to Origin."""
    if value is None:
        return None
    try:
        parsed = urlsplit(value)
        # Accessing .port validates that the port is numeric and in range.
        port = parsed.port
    except (TypeError, ValueError) as exc:
        raise argparse.ArgumentTypeError(f'invalid public origin: {exc}') from exc
    if (parsed.scheme not in ('http', 'https') or not parsed.netloc or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path or parsed.query or parsed.fragment
            or any(character.isspace() for character in value)
            or parsed.netloc.endswith(':') or port == 0):
        raise argparse.ArgumentTypeError('public origin must be only an http:// or https:// origin (no path, query, fragment, or user info)')
    return value


def expected_request_origin(public_origin, host_header):
    """Use the configured external origin, or preserve direct-LAN behavior."""
    return public_origin or ('http://' + host_header)

PAGE = '''<!doctype html><meta name="viewport" content="width=device-width"><title>LumenPnP live view</title>
<style>body{background:#101720;color:#e6edf3;font:16px system-ui;margin:20px}header{display:flex;justify-content:space-between}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(450px,1fr));gap:16px}article{background:#1d2733;padding:12px;border-radius:10px}img{width:100%;cursor:zoom-in}small{color:#9bb1c8}h2{font-size:18px}#status{color:#9bb1c8}#paste-progress{margin:12px 0;max-width:900px}#paste-progress p{margin:6px 0}@media(max-width:500px){main{display:block}}</style>
<header><h1>LumenPnP live view</h1><p>Private viewer · 1 frame/sec</p><p><a id="inspection-report" href="/inspection">Placement inspection report</a></p></header>
<style>#layout{display:grid;grid-template-columns:minmax(420px,1fr) minmax(360px,500px);gap:20px}main{display:block}main article{margin-bottom:16px}#chat{background:#1d2733;border-radius:10px;padding:16px;position:sticky;top:12px;height:calc(100vh - 165px);display:flex;flex-direction:column}#messages{overflow:auto;flex:1;min-height:200px}.message{padding:12px;margin:12px 0;background:#101720;border-radius:8px;border-left:3px solid #79b8ff}.message.user{border-color:#8be0b2}.message.progress{opacity:.85}.message p{white-space:pre-wrap;overflow-wrap:anywhere;margin:8px 0 0;line-height:1.5}.message small{font-size:12px}button{background:#324b66;color:white;border:0;padding:8px;border-radius:5px;cursor:pointer}button:disabled{opacity:.55;cursor:not-allowed}textarea{box-sizing:border-box;width:100%;min-height:84px;resize:vertical;background:#101720;color:#e6edf3;border:1px solid #49647d;border-radius:5px;padding:8px;font:inherit}#chat h2{margin:0 0 8px}#chat-status{padding:8px 0}.chat-controls{display:flex;gap:10px;align-items:center;font-size:13px}.composer{border-top:1px solid #49647d;margin-top:10px;padding-top:10px}.composer-row{display:flex;justify-content:space-between;gap:10px;align-items:center;margin-top:6px}.composer-row small{flex:1}@media(max-width:900px){#layout{display:block}#chat{position:static;height:70vh}}</style>
<p id="status">Connecting…</p><article id="paste-progress" aria-live="polite"><h2>Paste run</h2><strong id="paste-state">Loading…</strong><p id="paste-phase"></p><p id="paste-count"></p><p id="paste-message"></p><small id="paste-updated"></small></article><div id="layout"><main></main><aside id="chat"><h2>Our conversation</h2><small>Live mirror · replies are sent to this Codex task</small><div class="chat-controls"><label><input id="progress" type="checkbox" checked>Progress updates</label><button id="latest">Jump to latest</button></div><small id="chat-status">Loading conversation…</small><div id="messages" aria-label="Conversation"></div><form id="composer" class="composer"><label for="reply">Reply to Codex</label><textarea id="reply" maxlength="4000" placeholder="Send a message to this task" required></textarea><div class="composer-row"><small id="send-status">Messages are delivered to the Codex task queue.</small><button id="send" type="submit">Send</button></div></form></aside></div>
<script>
const token=location.hash.slice(1)||sessionStorage.getItem('viewerToken');
if(token)sessionStorage.setItem('viewerToken',token);history.replaceState(null,'',location.pathname);
const authHeaders=()=>({Authorization:'Bearer '+token});let csrfToken=null;
async function pasteTick(){const el=id=>document.querySelector('#paste-'+id);try{const r=await fetch('/paste-status',{headers:authHeaders(),cache:'no-store'});if(!r.ok)throw Error('Progress unavailable.');const s=await r.json();el('state').textContent=s.status.toUpperCase();el('phase').textContent=s.phase?'Phase: '+s.phase:'';el('count').textContent=`Pads: ${s.completedPads}/${s.totalPads}`+(s.currentPad?' · current: '+s.currentPad:'');el('message').textContent=s.message||'';const time=Date.parse(s.updatedAt);if(!Number.isFinite(time)){el('updated').textContent='No update timestamp';}else{const age=Math.max(0,Math.floor((Date.now()-time)/1000));const ago=age<60?age+'s':Math.floor(age/60)+'m';el('updated').textContent=(age>60?'STALE · ':'Updated ')+ago+' ago · '+new Date(time).toLocaleString();}}catch(e){el('state').textContent='UNAVAILABLE';el('message').textContent=e.message;}setTimeout(pasteTick,2000);}pasteTick();
document.querySelector('#inspection-report').onclick=async event=>{event.preventDefault();const link=event.currentTarget;try{const r=await fetch('/inspection/session',{method:'POST',headers:authHeaders(),cache:'no-store'});if(!r.ok)throw Error('Private viewer authorization is required.');location.href='/inspection';}catch(error){link.textContent='Placement inspection report unavailable.';}};
const names={openpnp:'OpenPnP · top and bottom cameras',webcam:'Machine USB camera'};
const main=document.querySelector('main');let urls={};
let chatRevision=-1,chatMessages=[];
const messages=document.querySelector('#messages');
function renderChat(force=false){const bottom=messages.scrollHeight-messages.scrollTop-messages.clientHeight<90;const old=messages.scrollTop;messages.replaceChildren();for(const m of chatMessages){if(!document.querySelector('#progress').checked&&m.phase==='commentary')continue;const a=document.createElement('div');a.className='message '+m.role+(m.phase==='commentary'?' progress':'');const label=document.createElement('small');label.textContent=(m.role==='user'?'You':m.phase==='commentary'?'Codex · progress':'Codex')+' · '+new Date(m.timestamp).toLocaleString();const p=document.createElement('p');p.textContent=m.text;a.append(label,p);messages.append(a);}if(bottom||force)messages.scrollTop=messages.scrollHeight;else messages.scrollTop=old;}
document.querySelector('#progress').onchange=()=>renderChat();document.querySelector('#latest').onclick=()=>{messages.scrollTop=messages.scrollHeight;};
async function chatTick(){try{const r=await fetch('/chat',{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!r.ok)throw Error('Open the complete private viewer link to read chat.');const c=await r.json();if(c.revision!==chatRevision){const first=chatRevision<0;chatRevision=c.revision;chatMessages=c.messages;renderChat(first);}document.querySelector('#chat-status').textContent=c.error||'Connected · '+c.messages.length+' messages';}catch(e){document.querySelector('#chat-status').textContent=e.message;}setTimeout(chatTick,2000);}
async function csrf(){if(csrfToken)return csrfToken;const r=await fetch('/csrf',{headers:authHeaders(),cache:'no-store'});if(!r.ok)throw Error('Private viewer authorization is required.');csrfToken=(await r.json()).token;return csrfToken;}
function messageKey(text){try{const prior=JSON.parse(sessionStorage.getItem('viewerPendingReply')||'null');if(prior?.text===text&&prior?.key)return prior.key;const key=self.crypto?.randomUUID?.()||('message-'+Date.now()+'-'+Math.random().toString(36).slice(2));sessionStorage.setItem('viewerPendingReply',JSON.stringify({text,key}));return key;}catch{return self.crypto?.randomUUID?.()||('message-'+Date.now()+'-'+Math.random().toString(36).slice(2));}}
document.querySelector('#composer').onsubmit=async event=>{event.preventDefault();const reply=document.querySelector('#reply'),send=document.querySelector('#send'),status=document.querySelector('#send-status');const text=reply.value;send.disabled=true;status.textContent='Sending to Codex…';try{const r=await fetch('/messages',{method:'POST',headers:{...authHeaders(),'Content-Type':'application/json','X-Viewer-CSRF':await csrf(),'Idempotency-Key':messageKey(text)},body:JSON.stringify({message:text})});const body=await r.json();if(!r.ok)throw Error(body.error||'Message could not be sent.');if(body.status==='delivered'){reply.value='';sessionStorage.removeItem('viewerPendingReply');status.textContent='Delivered to the Codex task queue.';}else if(body.status==='unknown'){status.textContent='Delivery outcome is unknown. Check Codex before sending again.';}else{status.textContent=body.error||'Delivery failed. Keep this text and retry only after checking Codex.';}}catch(error){status.textContent=error.message;}finally{send.disabled=false;}};
for(const [id,name] of Object.entries(names)){let a=document.createElement('article');a.innerHTML=`<h2>${name}</h2><small id="s-${id}"></small><img id="${id}" alt="Waiting for ${name}">`;main.append(a);a.querySelector('img').onclick=()=>a.requestFullscreen();}
async function tick(){
 try{const r=await fetch('/status',{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!r.ok)throw Error('Access denied. Open the complete private link.');const s=await r.json();
 document.querySelector('#status').textContent='Latest capture: '+new Date(s.time*1000).toLocaleTimeString()+' · '+(Date.now()/1000-s.time<5?'live':'STALE');
 await Promise.all(Object.keys(names).map(async id=>{document.querySelector('#s-'+id).textContent=s.errors[id]||'';if(s.errors[id])return;let r=await fetch('/frame/'+id,{headers:{Authorization:'Bearer '+token},cache:'no-store'});if(!r.ok)return;let u=URL.createObjectURL(await r.blob());document.getElementById(id).src=u;if(urls[id])URL.revokeObjectURL(urls[id]);urls[id]=u;}));
 }catch(e){document.querySelector('#status').textContent=e.message;}setTimeout(tick,1000);
}tick();chatTick();</script>'''.encode('utf-8')

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--bind',required=True)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--public-origin',type=validate_public_origin,
                        help='Exact external http(s) origin for HTTPS tunnel deployments; no path, query, or user info')
    parser.add_argument('--thread',help='Codex task UUID to receive web replies (overrides local config)')
    parser.add_argument('--state',help='Private viewer state directory (default: repository .local-viewer)')
    args=parser.parse_args()
    state=Path(args.state) if args.state else Path(__file__).resolve().parents[2]/'.local-viewer'
    state.mkdir(mode=0o700,exist_ok=True)
    token_file=state/'token'
    if not token_file.exists():
        token_file.write_text(secrets.token_urlsafe(32))
    os.chmod(token_file,0o600)
    token=token_file.read_text().strip()
    chat_config=state/'chat-source.json'
    mirror=ChatMirror(json.loads(chat_config.read_text())['path'] if chat_config.exists() else None)
    outbox=MessageOutbox(state/'messages.json')
    csrf_token=hmac.new(token.encode(),b'live-viewer-csrf',hashlib.sha256).hexdigest()
    cache={'frames':{},'errors':{},'time':0}
    lock=threading.Lock()
    def capture():
        d=display.Display()
        root=d.screen().root
        def windows(w):
            for c in w.query_tree().children:
                yield c
                yield from windows(c)
        while True:
            frames,errors={},{}
            targets={}
            try:
                for w in windows(root):
                    if w.get_attributes().map_state!=X.IsViewable:continue
                    title=w.get_wm_name() or ''
                    cls=' '.join(w.get_wm_class() or ()).lower()
                    if title.startswith('OpenPnP -') and 'openpnp' in cls:targets['openpnp']=w
                    elif title=='gst-launch-1.0' and 'gstreamer' in cls:targets['webcam']=w
                for key in ('openpnp','webcam'):
                    try:
                        if key not in targets:raise RuntimeError('Window unavailable or minimized')
                        w=targets[key];g=w.get_geometry()
                        raw=w.get_image(0,0,g.width,g.height,X.ZPixmap,0xffffffff)
                        im=Image.frombytes('RGB',(g.width,g.height),raw.data,'raw','BGRX')
                        im.thumbnail((1920,1080));buf=io.BytesIO();im.save(buf,'JPEG',quality=80)
                        frames[key]=buf.getvalue()
                    except Exception as e:errors[key]=str(e)
            except Exception as e:errors['desktop']=str(e)
            with lock:cache.update(frames=frames,errors=errors,time=time.time())
            time.sleep(1)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def authorized(self):
            return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token)
        def inspection_authorized(self):
            expected='inspectionAuth='+token
            cookie=self.headers.get('Cookie','')
            return self.authorized() or any(hmac.compare_digest(v.strip(),expected) for v in cookie.split(';'))
        def reply(self,status,body,kind='application/json'):
            if isinstance(body,dict):body=json.dumps(body).encode()
            self.send_response(status)
            self.send_header('Content-Type',kind);self.send_header('Content-Length',str(len(body)))
            self.send_header('Cache-Control','no-store');self.send_header('Referrer-Policy','no-referrer')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'self' blob:; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'")
            self.end_headers()
            try:self.wfile.write(body)
            except (BrokenPipeError,ConnectionResetError):pass
        def target_thread(self):
            configured=args.thread
            if not configured and chat_config.exists():
                try:configured=json.loads(chat_config.read_text()).get('thread')
                except (OSError,ValueError,TypeError):configured=None
            try:return str(uuid.UUID(configured))
            except (ValueError,TypeError,AttributeError):return None
        def dispatch(self,record):
            claimed=outbox.claim(record['id'])
            if not claimed:return outbox.get(record['id'])
            target=self.target_thread()
            if not target:
                return outbox.complete(record['id'],'failed','No Codex task is configured for replies.')
            try:
                result=subprocess.run(['codex','queue','--thread',target,'--message',claimed['message']],
                                      stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
                                      stderr=subprocess.PIPE,text=True,timeout=20,check=False)
            except subprocess.TimeoutExpired:
                return outbox.complete(record['id'],'unknown','Codex delivery timed out; it may still have been queued.')
            except OSError:
                return outbox.complete(record['id'],'failed','Codex task delivery could not start.')
            if result.returncode:
                return outbox.complete(record['id'],'failed','Codex rejected delivery. Check that the configured task is open.')
            return outbox.complete(record['id'],'delivered')
        def expected_origin(self):
            # A tunnel's public Origin differs from the loopback Host. Never
            # infer trust from X-Forwarded-* headers supplied by the client.
            return expected_request_origin(args.public_origin, self.headers.get('Host',''))
        def do_GET(self):
            path=urlsplit(self.path).path
            if path=='/':
                self.reply(200,PAGE,'text/html; charset=utf-8')
                return
            if path == '/inspection' or path.startswith('/inspection/'):
                if not self.inspection_authorized():
                    self.reply(403,{'error':'Access denied.'});return
                if path == '/inspection':
                    try: body=inspection_html()
                    except OSError: self.reply(404,{'error':'Inspection report unavailable.'});return
                    self.reply(200,body,'text/html; charset=utf-8');return
                if path == '/inspection/asset':
                    name=parse_qs(urlsplit(self.path).query,keep_blank_values=True).get('file',[''])[0]
                    target=resolve_inspection_asset(name)
                    if target is None:
                        self.reply(404,{'error':'Inspection asset not found.'});return
                    try: body=target.read_bytes()
                    except OSError:
                        self.reply(404,{'error':'Inspection asset not found.'});return
                    kind={'.md':'text/plain; charset=utf-8','.json':'application/json; charset=utf-8'}.get(target.suffix.lower())
                    self.reply(200,body,kind or mimetypes.guess_type(target.name)[0] or 'application/octet-stream');return
                self.reply(404,{'error':'Not found.'});return
            if not self.authorized():
                self.reply(403,{'error':'Access denied.'});return
            if path=='/csrf':
                self.reply(200,{'token':csrf_token});return
            if path=='/paste-status':
                self.reply(200,paste_status());return
            if path=='/chat':
                self.reply(200,mirror.snapshot());return
            with lock:
                if path=='/status':body,kind=json.dumps({'time':cache['time'],'errors':cache['errors']}).encode(),'application/json'
                elif path.startswith('/frame/') and path[7:] in cache['frames']:
                    body,kind=cache['frames'][path[7:]],'image/jpeg'
                else:self.reply(404,{'error':'Not found.'});return
            self.reply(200,body,kind)
        def do_POST(self):
            path=urlsplit(self.path).path
            expected_origin=self.expected_origin()
            if path == '/inspection/session':
                if (not self.authorized() or self.headers.get('Origin') != expected_origin
                        or self.headers.get('Content-Length','0') not in ('0','')):
                    self.reply(403,{'error':'Access denied.'});return
                self.send_response(204)
                secure='; Secure' if args.public_origin and urlsplit(args.public_origin).scheme == 'https' else ''
                self.send_header('Set-Cookie',f'inspectionAuth={token}; Path=/inspection; HttpOnly; SameSite=Strict; Max-Age=3600{secure}')
                self.send_header('Cache-Control','no-store')
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Content-Length','0')
                self.end_headers()
                return
            if (not self.authorized() or not hmac.compare_digest(self.headers.get('X-Viewer-CSRF',''),csrf_token)
                    or self.headers.get('Origin') != expected_origin):
                self.reply(403,{'error':'Access denied.'});return
            if path!='/messages':
                self.reply(404,{'error':'Not found.'});return
            try:
                length=int(self.headers.get('Content-Length','-1'))
                if length < 1 or length > 20_000:raise ValueError('Invalid request size.')
                if self.headers.get('Content-Type','').split(';',1)[0].strip() != 'application/json':
                    raise ValueError('Expected JSON.')
                payload=json.loads(self.rfile.read(length))
                if not isinstance(payload,dict):raise ValueError('Expected a JSON object.')
                record,created=outbox.submit(payload.get('message'),self.headers.get('Idempotency-Key'))
                if created:record=self.dispatch(record)
                self.reply(201 if created else 200,record)
            except (ValueError,TypeError,json.JSONDecodeError) as error:
                self.reply(400,{'error':str(error)})
    threading.Thread(target=capture,daemon=True).start()
    print(f'Viewer on {args.bind}:{args.port}',flush=True)
    ThreadingHTTPServer((args.bind,args.port),Handler).serve_forever()

if __name__=='__main__':main()
