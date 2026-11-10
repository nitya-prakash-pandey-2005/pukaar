import json

from voice_core.testing import FakeLLM

from pukaar.broadcast import make_broadcast


async def test_broadcast_translates_in_one_call_and_speaks_each_language():
    llm = FakeLLM([json.dumps({"ta-IN": "அடையாறு ஆற்றில் நீர் உயர்கிறது.", "hi-IN": "अड्यार नदी का पानी बढ़ रहा है।"})])
    spoken = []

    async def tts(text, lang):
        spoken.append((text, lang))
        return f"k-{lang}"

    items = await make_broadcast("Adyar river is rising.", ["en-IN", "ta-IN", "hi-IN", "te-IN"], llm, tts)
    assert len(llm.calls) == 1
    assert [i["lang"] for i in items] == ["en-IN", "ta-IN", "hi-IN"]  # te-IN missing from the reply: skipped
    assert items[0]["text"] == "Adyar river is rising." and items[1]["audio"] == "k-ta-IN"
    assert spoken[1] == ("அடையாறு ஆற்றில் நீர் உயர்கிறது.", "ta-IN")


async def test_broadcast_survives_bad_translation_json():
    async def tts(text, lang):
        return "k"
    items = await make_broadcast("Move to the relief camp.", ["en-IN", "ta-IN"], FakeLLM(["not json"]), tts)
    assert [i["lang"] for i in items] == ["en-IN"]


async def test_broadcast_skips_a_translation_that_lost_a_place_name():
    from pukaar.data import load_gazetteer
    llm = FakeLLM([json.dumps({"ta-IN": "ஆற்றில் நீர் உயர்கிறது, {P2} மக்கள் வெளியேறுங்கள்",  # {P1} (Adyar) dropped
                               "hi-IN": "{P1} नदी बढ़ रही है, {P 2} के लोग",                  # {P2} mangled
                               "te-IN": "{P1} నది, {P2} ప్రజలు"})])

    async def tts(text, lang):
        return "k"
    items = await make_broadcast("The Adyar river is rising near Kotturpuram.", ["en-IN", "ta-IN", "hi-IN", "te-IN"],
                                 llm, tts, places=load_gazetteer())
    assert [i["lang"] for i in items] == ["en-IN", "te-IN"]


async def test_broadcast_place_names_use_gazetteer_spelling_per_script():
    from pukaar.data import load_gazetteer
    llm = FakeLLM([json.dumps({"ta-IN": "{P1} ஆற்றில் நீர், {P2} மக்கள்", "hi-IN": "{P1} नदी, {P2} के लोग", "te-IN": "{P1} నది, {P2} ప్రజలు"})])
    seen = []

    async def tts(text, lang):
        seen.append(text)
        return "k"
    items = await make_broadcast("The Adyar river is rising near Kotturpuram.", ["ta-IN", "hi-IN", "te-IN"], llm, tts,
                                 places=load_gazetteer())
    assert "Adyar" not in llm.calls[0][-1]["content"] and "{P1}" in llm.calls[0][-1]["content"]
    assert items[0]["text"] == "அடையாறு ஆற்றில் நீர், கோட்டூர்புரம் மக்கள்"
    assert items[1]["text"] == "Adyar नदी, Kotturpuram के लोग"  # no Devanagari alias: English name
    assert items[2]["text"] == "Adyar నది, Kotturpuram ప్రజలు" and "{" not in "".join(seen)
