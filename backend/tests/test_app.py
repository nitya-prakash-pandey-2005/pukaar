import json
import random

import pytest
from fastapi.testclient import TestClient
from voice_core.config import Settings
from voice_core.session import VoiceAgentSession
from voice_core.testing import FakeLLM, FakeStt, ev, fake_tts

from pukaar.agent import PukaarAgent
from pukaar.app import create_app
from pukaar.data import load_gazetteer, load_guidance

FACTS = json.dumps({"hazard": "flood", "locality": "Velachery", "water_level": "chest", "people_count": 4})


@pytest.fixture
def client(tmp_path):
    settings = Settings(sample_rate=8000, cache_dir=tmp_path / "cache")

    def factory(store, send_json, send_audio, gps, call_id=None):
        agent = PukaarAgent(llm=FakeLLM(["பயப்படாதீங்க."]), intel_llm=FakeLLM([FACTS]), store=store,
                            places=load_gazetteer(), kb=load_guidance(), gps=gps, call_id=call_id)
        stt = FakeStt([ev("connected"), ev("transcript", "Velachery la irukom, thanni chest varaikkum", "ta-IN")])
        sess = VoiceAgentSession(agent, send_json=send_json, send_audio=send_audio, settings=settings,
                                 stt_factory=lambda: stt, tts_fn=fake_tts, rng=random.Random(0))
        return sess, agent

    with TestClient(create_app(settings, session_factory=factory, intel_llm=FakeLLM([]))) as c:
        yield c


def _until(ws, type_, n=60):
    for _ in range(n):
        raw = ws.receive()
        if not raw.get("text"):  # skip binary audio frames
            continue
        m = json.loads(raw["text"])
        if m.get("type") == type_:
            return m
    raise AssertionError(f"no {type_}")


def test_call_incident_dispatch_callback(client):
    with client.websocket_connect("/ws/control") as ctl:
        snap = ctl.receive_json()
        assert snap["type"] == "snapshot" and snap["incidents"] == []
        with client.websocket_connect("/ws/call") as call:
            call.send_json({"type": "start", "gps": [12.98, 80.22], "noise_snr_db": None})
            call_id = call.receive_json()["call_id"]
            assert _until(ctl, "call_started")["call_id"] == call_id
            inc = _until(ctl, "incident")["incident"]
            assert inc["severity"]["level"] == "high" and inc["loc_source"] == "both"
            call.send_json({"type": "hangup"})
            _until(call, "call_ended")
        _until(ctl, "call_ended")

        r = client.post(f"/api/incidents/{inc['id']}/dispatch", json={"team": "NDRF Boat 1", "note": "", "eta": "20 min"})
        assert r.status_code == 200 and r.json()["status"] == "dispatched"
        assert _until(ctl, "incident")["incident"]["status"] == "dispatched"

    cbs = client.get(f"/api/calls/{call_id}/callbacks").json()
    assert len(cbs) == 1
    assert client.get("/api/kpis").json()["calls"] == 1
    assert client.post(f"/api/incidents/{inc['id']}/resolve").json()["status"] == "resolved"
    assert client.get("/api/incidents?status=resolved").json()[0]["id"] == inc["id"]


def test_rest_basics_and_404s(client):
    assert client.get("/api/health").json()["fake"] is False
    assert len(client.get("/api/places").json()) >= 35
    assert client.get("/api/incidents/nope").status_code == 404
    assert client.post("/api/incidents/nope/dispatch", json={"team": "x"}).status_code == 404
    assert client.post("/api/incidents/nope/resolve").status_code == 404
    assert client.get("/api/calls/nope/callbacks").status_code == 404
    assert client.get("/api/calls/nope").status_code == 404


def test_fake_mode_boots(tmp_path, monkeypatch):
    monkeypatch.setenv("PUKAAR_FAKE", "1")
    with TestClient(create_app(Settings(sample_rate=8000, cache_dir=tmp_path / "c"))) as c:
        assert c.get("/api/health").json()["fake"] is True


def test_guidance_and_callback_audio_fake(tmp_path, monkeypatch):
    monkeypatch.setenv("PUKAAR_FAKE", "1")
    app = create_app(Settings(sample_rate=8000, cache_dir=tmp_path / "c"))
    store = app.state.store
    cid = store.create_call("ta-IN")
    cb = store.queue_callback(cid, "படகு வருகிறது.", "ta-IN")
    with TestClient(app) as c:
        assert any(g["id"] == "FLD-01" for g in c.get("/api/guidance").json())
        r = c.get(f"/api/calls/{cid}/callbacks/{cb}/audio")
        assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content[:4] == b"RIFF"
        assert c.get(f"/api/calls/{cid}/callbacks/nope/audio").status_code == 404


def test_surge_fake_mode_replays_the_committed_recording(tmp_path, monkeypatch):
    # the fake LLM only knows the 4 facts of the scripted call, so generating gave empty pins and minutes of retries
    import time
    from pukaar.data import DATA
    monkeypatch.setenv("PUKAAR_FAKE", "1")
    first = json.loads((DATA / "surge_demo.json").read_text(encoding="utf-8"))[0]
    (tmp_path / "c").mkdir()
    (tmp_path / "c" / "surge_fake.json").write_text("[]", encoding="utf-8")  # an old junk recording is ignored
    with TestClient(create_app(Settings(sample_rate=8000, cache_dir=tmp_path / "c"))) as c:
        assert c.post("/api/surge", json={"n": 2}).json() == {"started": 2, "mode": "replay"}
        assert c.post("/api/surge", json={"n": 2}).status_code == 409
        for _ in range(100):
            if c.get("/api/incidents").json():
                break
            time.sleep(0.05)
        assert c.get("/api/incidents").json()[0]["facts"]["locality"] == first["facts"]["locality"]


def test_missed_call_then_callback_reuses_call_and_incident(client):
    r = client.post("/api/missed-call", json={"gps": [12.98, 80.22]}).json()
    cid, inc = r["call_id"], r["incident"]
    assert inc["channel"] == "missed_call" and inc["lat"] == 12.98 and inc["call_ids"] == [cid]
    with client.websocket_connect("/ws/call") as call:
        call.send_json({"type": "start", "gps": [12.98, 80.22], "callback_for": cid})
        assert call.receive_json()["call_id"] == cid
        seen = [_until(call, "turn") for _ in range(2)]
        assert any(m["speaker"] == "pukaar" and "missed call" in m["text"] for m in seen)
        assert _until(call, "incident")["incident"]["id"] == inc["id"]
        call.send_json({"type": "hangup"})
        _until(call, "call_ended")
    assert len(client.get("/api/incidents").json()) == 1


def test_broadcast_fake_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("PUKAAR_FAKE", "1")
    with TestClient(create_app(Settings(sample_rate=8000, cache_dir=tmp_path / "c"))) as c:
        items = c.post("/api/broadcast", json={"text_en": "Move to the relief camp.", "langs": ["en-IN", "ta-IN"]}).json()
        assert [i["lang"] for i in items] == ["en-IN", "ta-IN"]
        r = c.get(items[1]["audio_url"])
        assert r.status_code == 200 and r.content[:4] == b"RIFF"
        assert c.get("/api/broadcast/audio/../../etc/passwd").status_code == 404
        assert c.get("/api/broadcast/audio/" + "0" * 40).status_code == 404
        assert c.post("/api/broadcast", json={"text_en": " ", "langs": ["en-IN"]}).status_code == 400
