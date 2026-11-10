import json
import random

from voice_core.config import Settings
from voice_core.gnani.stt_stream import SttEvent

from pukaar.data import load_gazetteer
from pukaar.domain import Facts
from pukaar.drill import RetryLLM, cer, run_drill, score_case, summarise


def test_cer():
    assert cer("Velachery la irukom", "velachery la irukom!") == 0.0
    assert cer("abcd", "abxd") == 0.25
    assert cer("abc", "") == 1.0


def test_score_case():
    ref = Facts(locality="Velachery", hazard="flood", people_count=4, water_level="chest", vulnerable=["elderly", "infant"])
    got = Facts(locality="velachery", hazard="flood", people_count=4, water_level="waist", vulnerable=["elderly"])
    s = score_case(ref, got)
    assert s["locality"] and s["people"] and not s["water_level"]
    assert abs(s["vulnerable_f1"] - 2 / 3) < 1e-9
    assert s["severity_level"] is False  # 20+30+6+20 = 76 critical vs 20+18+6+8 = 52 high


def test_summarise_by_snr():
    rows = [{"snr": None, "lang": "ta-IN", "cer": 0.1, "locality": True, "people": True, "water_level": True,
             "vulnerable_f1": 1.0, "severity_level": True},
            {"snr": 0, "lang": "ta-IN", "cer": 0.5, "locality": False, "people": True, "water_level": False,
             "vulnerable_f1": 0.0, "severity_level": False}]
    s = summarise(rows)
    assert s["by_snr"]["clean"]["locality"] == 1.0 and s["by_snr"]["0"]["cer"] == 0.5 and s["by_snr"]["0"]["n"] == 1
    assert s["by_lang"]["ta-IN"]["people"] == 1.0


async def test_run_drill_with_fakes(tmp_path):
    facts = json.dumps({"hazard": "flood", "locality": "Velachery", "people_count": 3})

    class Flaky:  # fails once, then answers: RetryLLM must hide the failure
        def __init__(self):
            self.n = 0

        async def complete(self, messages, **kw):
            self.n += 1
            if self.n == 2:
                raise RuntimeError("429")
            return "Velachery la thanni" if messages[0]["content"].startswith("You write") else facts

    async def tts(key, text, **kw):
        return b"\x10\x00" * 8000

    heard = []

    async def stt(key, wav, **kw):
        heard.append(kw["language_code"])
        return SttEvent("transcript", text="Velachery la thanni")

    rows = []

    async def emit(m):
        rows.append(m)

    out = await run_drill(1, (None, 0), Settings(cache_dir=tmp_path, gnani_api_key="k"), RetryLLM(Flaky(), wait=0),
                          emit, random.Random(0), load_gazetteer(), tts_fn=tts, stt_fn=stt)
    assert len(out["rows"]) == 2 and all(r["locality"] for r in out["rows"]) and heard == ["indic-auto"] * 2
    assert out["rows"][0]["cer"] == 0.0 and set(out["summary"]["by_snr"]) == {"clean", "0"}
    assert sum(m["type"] == "drill_row" for m in rows) == 2


def test_locality_scoring_tolerates_spelling():
    places = load_gazetteer()
    assert score_case(Facts(locality="Velachery"), Facts(locality="Velacheri"), places)["locality"]
    assert score_case(Facts(locality="வேளச்சேரி"), Facts(locality="Velachery"), places)["locality"]
    assert not score_case(Facts(locality="Velachery"), Facts(locality="Tambaram"), places)["locality"]


async def test_rescore_uses_llm_only():
    from voice_core.testing import FakeLLM

    from pukaar.drill import rescore
    rows = [{"case": 0, "lang": "ta-IN", "snr": None, "ref": "Velachery la thanni", "hyp": "Velacheri la thanni", "cer": 0.05},
            {"case": 0, "lang": "ta-IN", "snr": 0, "ref": "Velachery la thanni", "hyp": "", "cer": 1.0}]
    llm = FakeLLM(['{"locality": "Velachery"}', '{"locality": "Velacheri"}', '{}'])
    out = await rescore(rows, llm, load_gazetteer())
    assert [r["locality"] for r in out["rows"]] == [True, False] and len(llm.calls) == 3  # ref extracted once per case
    assert out["rows"][0]["got_facts"] == {"locality": "Velachery"}


def test_cer_skips_cross_script_pairs():
    assert cer("Pallikaranai mein paani", "पालीकरणाई में पानी") is None
    assert cer("சோலினல்லூரில் நான்கு", "சோழிநல்லூரில் நான்கு") < 0.2
    s = summarise([{"snr": None, "lang": "hi-IN", "cer": None, "locality": True, "people": True, "water_level": True,
                    "vulnerable_f1": 1.0, "severity_level": True}])
    assert s["by_snr"]["clean"]["cer"] is None and s["by_snr"]["clean"]["n_cer"] == 0
