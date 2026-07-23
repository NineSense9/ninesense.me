from pathlib import Path

from argon2 import PasswordHasher
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from ninesense_guestbook.app import create_app
from ninesense_guestbook.config import Settings
from ninesense_guestbook.db import Base
from ninesense_guestbook.models import Admin


ROOT = Path(__file__).resolve().parents[1]
ADMIN_DIST = ROOT / "admin-app" / "dist"
DATABASE = ROOT / "tests" / ".e2e.sqlite3"
DATABASE.unlink(missing_ok=True)

settings = Settings(
    database_url=f"sqlite:///{DATABASE}",
    contact_key="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    security_key="AQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQEBAQE=",
    session_pepper="e2e-session-pepper",
    rate_limit_key="e2e-rate-limit-key",
    cookie_secure=False,
    testing=True,
)
app = create_app(settings)
Base.metadata.create_all(app.state.engine)
with app.state.session_factory() as session:
    session.add(
        Admin(
            username="ninesense",
            password_hash=PasswordHasher().hash("E2E-secure-password-2026"),
            active=True,
        )
    )
    session.commit()

app.mount(
    "/admin/assets",
    StaticFiles(directory=ADMIN_DIST / "assets"),
    name="admin-assets",
)


@app.get("/admin/{path:path}", include_in_schema=False)
def admin_spa(path: str):
    return FileResponse(ADMIN_DIST / "index.html")


app.mount("/", StaticFiles(directory=ROOT / "site", html=True), name="site")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8123, log_level="warning", access_log=False)
