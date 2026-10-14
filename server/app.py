from __future__ import annotations
import logging
import uuid
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import sessionmaker
from starlette.middleware.trustedhost import TrustedHostMiddleware
from .config import ROOT, Settings
from .db import get_db, make_engine
from .errors import DomainError
from .i18n import catalog, translate
from .routes import activities, auth, classrooms, files, groups, library, progress, realtime, work, training, codeforces

logger = logging.getLogger('olympiados')


def request_locale(request: Request) -> str:
    locale = request.headers.get('X-Locale', '')
    if locale not in ('ru', 'en'):
        locale = getattr(getattr(request.state, 'user', None), 'locale', 'ru')
    return locale


def error_response(request: Request, code: str, status: int, data: dict | None = None):
    return JSONResponse({'error': {'code': code, 'message': translate('error.' + code, request_locale(request)), 'data': data or {}}}, status_code=status)


class BodyLimitMiddleware:
    """Bound actual bytes, not just Content-Length (also handles chunked uploads)."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        limit = 9 * 1024 * 1024 if scope['path'] == '/api/files' else 1024 * 1024
        headers = dict(scope['headers'])
        try:
            declared = int(headers.get(b'content-length', b'0'))
        except ValueError:
            declared = limit + 1
        if declared > limit:
            return await error_response(Request(scope), 'file_too_large', 413)(scope, receive, send)
        total = 0
        async def bounded_receive():
            nonlocal total
            message = await receive()
            if message['type'] == 'http.request':
                total += len(message.get('body', b''))
                if total > limit:
                    from starlette.exceptions import HTTPException
                    raise HTTPException(status_code=413, detail='file_too_large')
            return message
        await self.app(scope, bounded_receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    application = FastAPI(title='Adolat Olympic Club', version='2.0.0-m1.1', docs_url=None if settings.production else '/api/docs', redoc_url=None)
    from .services.codeforces import CodeforcesClient
    application.state.codeforces = CodeforcesClient()
    from .services.event_feed import EventFeed
    application.state.event_feed = EventFeed()
    from .services.storage import build_storage
    application.state.storage = build_storage(settings)
    application.state.settings = settings
    application.state.engine = make_engine(settings)
    application.state.sessions = sessionmaker(application.state.engine, expire_on_commit=False)
    application.add_middleware(BodyLimitMiddleware)
    if settings.production:
        from urllib.parse import urlparse
        application.add_middleware(TrustedHostMiddleware, allowed_hosts=[urlparse(settings.origin).hostname, 'localhost', '127.0.0.1'])

    @application.middleware('http')
    async def security_headers(request: Request, call_next):
        request_id = uuid.uuid4().hex[:16]
        # Origin checks also cover login, invitation redemption and multipart forms.
        origin = request.headers.get('origin')
        allowed = {settings.origin}
        if not settings.production:
            allowed.add(str(request.base_url).rstrip('/'))
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and origin and origin not in allowed:
            response = error_response(request, 'csrf', 403)
        else:
            response = await call_next(request)
        response.headers['X-Request-ID'] = request_id
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Referrer-Policy'] = 'no-referrer'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'
        response.headers.setdefault('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' blob: data:; font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if request.url.path.startswith('/api'):
            response.headers.setdefault('Cache-Control', 'private, no-store')
        if settings.production:
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response

    @application.exception_handler(DomainError)
    async def domain_error(request: Request, exc: DomainError):
        return error_response(request, exc.code, exc.status, exc.data)

    @application.exception_handler(RequestValidationError)
    async def invalid_input(request: Request, exc: RequestValidationError):
        fields = [{'field': '.'.join(map(str, item['loc'][1:])), 'rule': item['type']} for item in exc.errors()]
        return error_response(request, 'invalid_input', 422, {'fields': fields})

    @application.exception_handler(IntegrityError)
    async def integrity_error(request: Request, exc: IntegrityError):
        logger.warning('Database constraint rejected request (%s)', type(exc).__name__)
        return error_response(request, 'conflict', 409)

    @application.exception_handler(OperationalError)
    async def database_error(request: Request, exc: OperationalError):
        logger.error('Database unavailable (%s)', type(exc).__name__)
        return error_response(request, 'unavailable', 503)

    from starlette.exceptions import HTTPException
    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        code = 'file_too_large' if exc.status_code == 413 else 'not_found' if exc.status_code == 404 else 'invalid_input'
        return error_response(request, code, exc.status_code)

    for module in (auth, classrooms, library, activities, work, groups, files, progress, realtime, training, codeforces):
        application.include_router(module.router)

    @application.get('/api/health', tags=['Operations'])
    def health():
        return {'status': 'ok'}

    @application.get('/api/ready', tags=['Operations'])
    def readiness():
        from .services.readiness import check_ready
        try:
            return check_ready(application.state.engine, settings)
        except Exception:
            return JSONResponse({'status':'unavailable'}, status_code=503)

    @application.get('/locales/{locale}.json', include_in_schema=False)
    def locale_catalog(locale: str):
        if locale not in ('ru', 'en'):
            raise DomainError('not_found', 404)
        return JSONResponse(catalog(locale))

    @application.get('/', include_in_schema=False)
    def index():
        return FileResponse(ROOT / 'static' / 'index.html', headers={'Cache-Control': 'no-cache'})

    application.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')
    return application

app = create_app()
