"""Seeds the read-only demo project (a real house photo with pre-computed AI analysis).

The demo works even if the AI quota is exhausted, so every visitor can explore a complete
example. Its regions were produced by the real pipeline (scripts/build_demo.py).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.db import ImageRow, ProjectRow, utcnow
from app.schemas import ProjectData
from app.services.images import decode_jpeg
from app.services.quality import assess_quality

DEMO_DIR = Path(__file__).resolve().parent.parent / "demo"
DEMO_PROJECT_ID = "demo"
DEMO_IMAGE_ID = "demo-house"
DEMO_OWNER = "demo"


def seed_demo(db: Session) -> None:
    project_file = DEMO_DIR / "project.json"
    image_file = DEMO_DIR / "house.jpg"
    if not project_file.exists() or not image_file.exists():
        return

    if db.get(ImageRow, DEMO_IMAGE_ID) is None:
        jpeg = image_file.read_bytes()
        rgb = decode_jpeg(jpeg)
        db.add(ImageRow(
            id=DEMO_IMAGE_ID,
            owner_id=DEMO_OWNER,
            sha256=hashlib.sha256(jpeg).hexdigest(),
            width=rgb.shape[1],
            height=rgb.shape[0],
            jpeg=jpeg,
            quality=assess_quality(rgb).model_dump_json(),
        ))

    spec = json.loads(project_file.read_text(encoding="utf-8"))
    data = ProjectData.model_validate(spec["data"]).model_dump_json()
    row = db.get(ProjectRow, DEMO_PROJECT_ID)
    if row is None:
        now = utcnow()
        db.add(ProjectRow(id=DEMO_PROJECT_ID, owner_id=DEMO_OWNER, name=spec["name"], is_demo=True,
                          data=data, created_at=now, updated_at=now))
    else:  # keep the stored demo in sync with the file shipped in the repo
        row.name, row.data, row.is_demo = spec["name"], data, True
    db.commit()
