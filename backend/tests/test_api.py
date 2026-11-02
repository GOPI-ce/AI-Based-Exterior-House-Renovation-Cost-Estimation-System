"""End-to-end API flow with the AI services replaced by fakes (no network, no quota)."""

import base64
import io

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import app
from app.services.gemini import GeminiComponent, GeminiCue, GeminiScene, GeminiUnavailable

from .conftest import textured_image

OWNER = {"X-Workspace-Id": "test-workspace-0001"}
OTHER = {"X-Workspace-Id": "test-workspace-0002"}


class FakeAnalyzer:
    available = True
    models = ["fake"]

    def __init__(self, fail: bool = False):
        self.fail = fail
        self.calls = 0

    def analyze(self, jpeg):
        self.calls += 1
        if self.fail:
            raise GeminiUnavailable("down")
        return GeminiScene(
            is_residential_exterior=True, view_type="front", storeys=2, usable_for_renovation=True, issues=[], guidance=[],
            components=[
                GeminiComponent(type="wall", label="Front wall", box_2d=[100, 100, 900, 900]),
                GeminiComponent(type="door", label="Main door", box_2d=[500, 450, 900, 550]),
            ],
            scale_cues=[GeminiCue(kind="door", label="Main door", box_2d=[500, 450, 900, 550], confidence=0.9)],
        ), "fake-model"


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def jpeg_bytes(rgb) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(rgb).save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def upload(client, rgb, headers=OWNER):
    return client.post("/api/images", files={"file": ("house.jpg", jpeg_bytes(rgb), "image/jpeg")}, headers=headers)


def test_health_and_catalog(client):
    assert client.get("/api/health").json()["status"] == "ok"
    materials = client.get("/api/catalog").json()["materials"]
    assert {"ap_apex", "rail_glass_frameless", "gvt_600x1200"} <= {m["id"] for m in materials}


def test_upload_rejects_unusable_photos(client):
    blank = textured_image()
    blank[:] = 128
    r = upload(client, blank)
    assert r.status_code == 422
    assert r.json()["detail"]["quality"]["ok"] is False

    r = client.post("/api/images", files={"file": ("x.txt", b"hello", "text/plain")}, headers=OWNER)
    assert r.status_code == 415

    r = client.post("/api/images", files={"file": ("house.jpg", jpeg_bytes(textured_image()), "image/jpeg")})
    assert r.status_code == 401  # no workspace header


def test_full_project_flow(client):
    app.state.analyzer = FakeAnalyzer()

    image = upload(client, textured_image(seed=1)).json()
    assert image["quality"]["ok"]
    assert client.get(f"/api/images/{image['image_id']}").headers["content-type"] == "image/jpeg"

    analysis = client.post(f"/api/images/{image['image_id']}/analyze", headers=OWNER).json()
    types = {r["type"] for r in analysis["regions"]}
    assert types == {"wall", "door"}
    assert analysis["planes"][0]["references"][0]["cue"] == "door"
    assert all(r["source"] == "ai_box" for r in analysis["regions"])  # SAM disabled in tests

    # A second analysis of the same photo is served from the cache.
    client.post(f"/api/images/{image['image_id']}/analyze", headers=OWNER)
    assert app.state.analyzer.calls == 1

    view = {
        "id": "v1", "name": "Front", "image_id": image["image_id"], "width": image["width"], "height": image["height"],
        "regions": analysis["regions"], "planes": analysis["planes"],
    }
    data = {"views": [view], "designs": [{"id": "d1", "name": "Warm", "assignments": {"wall-1": {"material_id": "ap_apex", "color": "#B4643F"}}}], "active_design_id": "d1"}
    project = client.post("/api/projects", json={"name": "Test house", "data": data}, headers=OWNER).json()
    assert project["can_edit"] is True

    # Shared link: others can view but not edit.
    assert client.get(f"/api/projects/{project['id']}", headers=OTHER).json()["can_edit"] is False
    assert client.put(f"/api/projects/{project['id']}", json={"name": "x", "data": data}, headers=OTHER).status_code == 403

    renamed = client.put(f"/api/projects/{project['id']}", json={"name": "Renamed", "data": data}, headers=OWNER).json()
    assert renamed["name"] == "Renamed"
    assert [p["id"] for p in client.get("/api/projects", headers=OWNER).json()] == [project["id"]]

    estimate = client.post("/api/estimate", json={"data": data}).json()
    assert estimate["lines"][0]["material_id"] == "ap_apex"
    assert estimate["lines"][0]["deductions"] > 0  # the door was deducted
    assert estimate["grand_total"] > 0

    render = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes(textured_image(seed=2))).decode()
    pdf = client.post("/api/report", json={"name": "Test house", "data": data, "renders": {"v1": render}})
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    copy = client.post(f"/api/projects/{project['id']}/copy", headers=OTHER).json()
    assert copy["can_edit"] is True and copy["id"] != project["id"]

    assert client.delete(f"/api/projects/{project['id']}", headers=OWNER).status_code == 204
    assert client.get(f"/api/projects/{project['id']}").status_code == 404


def test_analysis_failure_is_reported_cleanly(client):
    app.state.analyzer = FakeAnalyzer(fail=True)
    image = upload(client, textured_image(seed=3)).json()
    r = client.post(f"/api/images/{image['image_id']}/analyze", headers=OWNER)
    assert r.status_code == 503
    assert "manually" in r.json()["detail"]["message"]


def test_report_rejects_bad_render(client):
    view = {"id": "v", "name": "Front", "image_id": "missing", "width": 100, "height": 100}
    r = client.post("/api/report", json={"name": "x", "data": {"views": [view]}, "renders": {"v": "not-a-data-url"}})
    assert r.status_code == 422


def test_only_the_uploader_can_spend_ai_quota(client):
    app.state.analyzer = FakeAnalyzer()
    image = upload(client, textured_image(seed=5)).json()
    r = client.post(f"/api/images/{image['image_id']}/analyze", headers=OTHER)
    assert r.status_code == 403
    assert app.state.analyzer.calls == 0


def test_report_ignores_renders_for_unknown_photos(client):
    render = "data:image/jpeg;base64," + base64.b64encode(jpeg_bytes(textured_image(seed=6))).decode()
    r = client.post("/api/report", json={"name": "x", "data": {"views": []}, "renders": {"not-a-view": render}})
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_outdated_cached_analysis_is_recomputed(client):
    from app.db import AnalysisCacheRow, ImageRow, SessionLocal

    app.state.analyzer = FakeAnalyzer()
    image = upload(client, textured_image(seed=7)).json()
    with SessionLocal() as db:
        sha = db.get(ImageRow, image["image_id"]).sha256
        db.merge(AnalysisCacheRow(sha256=sha, result='{"regions": [], "scales": [], "scene": {}, "pipeline": {}}'))
        db.commit()
    r = client.post(f"/api/images/{image['image_id']}/analyze", headers=OWNER)
    assert r.status_code == 200 and r.json()["planes"]
    assert app.state.analyzer.calls == 1


def test_demo_depth_map_is_served_and_used(client):
    r = client.get("/api/images/demo-house/depth")
    assert r.status_code == 200
    grid = r.json()
    assert grid["cols"] == 192 and grid["rows"] == 144

    project = client.get("/api/projects/demo", headers=OWNER).json()
    est = client.post("/api/estimate", json={"data": project["data"]}).json()
    assert all(line["distance_m"] for line in est["lines"])
    assert any(p["ref_depth_m"] for p in est["planes"])


def test_depth_is_unavailable_without_the_model(client):
    image = upload(client, textured_image(seed=11)).json()
    r = client.get(f"/api/images/{image['image_id']}/depth", headers=OWNER)
    assert r.status_code == 404 and r.json()["detail"]["depth"] == "disabled"


def test_client_ip_behind_a_trusted_proxy(monkeypatch):
    from starlette.requests import Request

    from app.api.deps import client_ip
    from app.config import get_settings

    def req(xff):
        return Request({"type": "http", "headers": [(b"x-forwarded-for", xff.encode())], "client": ("10.0.0.1", 1)})

    assert client_ip(req("1.2.3.4")) == "10.0.0.1"  # no trusted proxy: the header is ignored
    monkeypatch.setattr(get_settings(), "trusted_proxy_hops", 1)
    assert client_ip(req("6.6.6.6, 1.2.3.4")) == "1.2.3.4"  # a spoofed left entry is ignored
