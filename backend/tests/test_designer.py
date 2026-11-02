"""AI budget designer: the model chooses, the estimator enforces the budget."""

import pytest

from app.catalog import get_catalog
from app.services.designer import AiDesign, AiPick, _price_options, suggest_design

catalog = get_catalog()


class FakeDesigner:
    """Proposes a fixed choice per round; records the prompts it was given."""

    def __init__(self, choose):
        self.choose = choose  # (options) -> list[AiPick]
        self.prompts: list[str] = []
        self.options = {}

    def generate(self, schema, contents, temperature=0.2):
        self.prompts.append(contents[-1])
        return AiDesign(name="Test design", concept="A test.", picks=self.choose(self.options)), "fake-model"


def designer(project, choose):
    fake = FakeDesigner(choose)
    fake.options = _price_options(project, catalog, None)
    return fake


def most_expensive(options):
    return [AiPick(region_id=rid, material_id=opts[-1].material.id, shade="", reason="luxury") for rid, opts in options.items()]


def floor_total(project, fake):
    cheap = [AiPick(region_id=rid, material_id=opts[0].material.id) for rid, opts in fake.options.items()]
    return suggest_design(project, catalog, 1e9, "", FakeDesigner(lambda _: cheap), None).total


def test_over_budget_proposals_are_repaired_to_fit(project):
    fake = designer(project, most_expensive)
    budget = floor_total(project, fake) * 1.5
    result = suggest_design(project, catalog, budget, "luxury", fake, None)
    assert result.within_budget and result.total <= budget
    assert len(fake.prompts) == 3  # three AI rounds, each told it was over budget
    assert "OVER the budget" in fake.prompts[1]
    assert result.steps[-1].label.startswith("Budget repair")


def test_a_budget_below_the_minimum_skips_the_ai(project):
    fake = designer(project, most_expensive)
    result = suggest_design(project, catalog, 1000, "", fake, None)
    assert not fake.prompts
    assert not result.within_budget
    assert "below the minimum" in result.warnings[0]


def test_invalid_picks_are_replaced_and_shades_validated(project):
    def choose(options):
        return [
            AiPick(region_id="wall-1", material_id="ap_apex", shade="Sage Green"),
            AiPick(region_id="wall-1", material_id="rail_ss_glass"),  # duplicate and unsuitable
            AiPick(region_id="ghost", material_id="ap_apex"),  # no such surface
        ]

    fake = designer(project, choose)
    result = suggest_design(project, catalog, 1e9, "", fake, None)
    a = result.design.assignments["wall-1"]
    assert a.material_id == "ap_apex"
    assert a.color == next(s.hex for s in catalog.palettes["exterior"] if s.name == "Sage Green")
    assert "2 invalid picks replaced" in result.steps[0].label


def test_an_underspent_proposal_gets_one_upgrade_round(project):
    fake = designer(project, lambda options: [AiPick(region_id=rid, material_id=o[0].material.id) for rid, o in options.items()])
    result = suggest_design(project, catalog, 1e9, "", fake, None)
    assert len(fake.prompts) == 2 and "only Rs" in fake.prompts[1]
    assert result.within_budget


def test_suggest_endpoint(project):
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as client:
        fake = designer(project, most_expensive)
        app.state.analyzer = fake
        body = {"data": project.model_dump(mode="json"), "budget": 5_000_000, "style": "modern"}
        assert client.post("/api/designs/suggest", json=body).status_code == 401
        r = client.post("/api/designs/suggest", json=body, headers={"X-Workspace-Id": "test-workspace-0003"})
        assert r.status_code == 200
        assert r.json()["within_budget"] and r.json()["model"] == "fake-model"
        empty = {**body, "data": {**body["data"], "views": []}}
        assert client.post("/api/designs/suggest", json=empty, headers={"X-Workspace-Id": "test-workspace-0003"}).status_code == 422


def test_a_failed_revision_keeps_the_earlier_proposal(project):
    from app.services.gemini import GeminiUnavailable

    fake = designer(project, most_expensive)
    calls = {"n": 0}
    real = fake.generate

    def flaky(schema, contents, temperature=0.2):
        calls["n"] += 1
        if calls["n"] > 1:
            raise GeminiUnavailable("busy")
        return real(schema, contents, temperature)

    fake.generate = flaky
    budget = floor_total(project, fake) * 1.5
    result = suggest_design(project, catalog, budget, "", fake, None)
    assert result.within_budget  # the over-budget first proposal was repaired, not lost
    assert any("unavailable" in s.label for s in result.steps)
