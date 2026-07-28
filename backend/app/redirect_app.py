from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse

from app.core.certs import ensure_certificates
from app.core.config import settings

app = FastAPI(title="AutoStock CA 下载")


@app.get("/ca.crt")
def download_ca() -> FileResponse:
    bundle = ensure_certificates()
    return FileResponse(
        bundle.ca_cert,
        media_type="application/x-x509-ca-cert",
        filename="ca.crt",
    )


@app.api_route("/{path:path}", methods=["GET", "HEAD"])
def redirect_to_https(request: Request, path: str) -> RedirectResponse:
    host = request.url.hostname or "127.0.0.1"
    if ":" in host:
        host = f"[{host}]"
    target = f"https://{host}:{settings.port_https}/{path}"
    if request.url.query:
        target += f"?{request.url.query}"
    return RedirectResponse(target, status_code=301)
