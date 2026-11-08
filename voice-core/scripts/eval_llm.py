"""Compare LLM providers (Groq vs self-hosted Evon v3.3) on the exact jobs our three apps need.

Run from a repo root:  uv run python voice-core/scripts/eval_llm.py --provider evon
Appends a results section to docs/evon-eval.md. See docs/EVON-HOSTING.md for the decision rule.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import time
from datetime import datetime
from pathlib import Path

from voice_core.config import get_settings, repo_root
from voice_core.llm import LLM, parse_json_loose

SCRIPTS = {"deva": r"[ऀ-ॿ]", "tamil": r"[஀-௿]", "bengali": r"[ঀ-৿]"}

PERSONA = [
    ("dadi", "deva", "You are Kamla Devi, 74, a sweet confused grandmother from Kanpur on a phone call. "
     "Reply in Hinglish: Hindi in Devanagari, English words in Latin. 1-2 short sentences. Stall politely.",
     ["Main CBI officer Vijay Kumar bol raha hoon, aapke Aadhaar se drugs ka parcel pakda gaya hai.",
      "Madam jaldi kariye, warna aapko digital arrest kiya jayega.",
      "Aap apna UPI PIN batao, verification ke liye.",
      "Aap AnyDesk app download karo abhi.",
      "Main aapko ek safe account number deta hoon, usme paisa transfer karo."]),
    ("paati", "tamil", "You are Meenakshi, 76, a confused grandmother from Madurai on a phone call. "
     "Reply in Tanglish: Tamil in Tamil script with English words in Latin. 1-2 short sentences. Stall politely.",
     ["Madam, naan bank manager pesuren, ungal KYC update pannanum.",
      "OTP sollunga madam, account block aagidum.",
      "Ungal card number sollunga please."]),
    ("thakuma", "bengali", "You are Bela Rani, 78, a confused grandmother from Howrah on a phone call. "
     "Reply in Benglish: Bengali in Bengali script with English words in Latin. 1-2 short sentences. Stall politely.",
     ["Mashima, ami electricity office theke bolchi, aaj raat e line cut hoye jabe.",
      "Ekhuni 500 taka pay korun ei UPI te.",
      "Apnar phone e ekta app install korun."]),
]

INTEL = [
    ("Main CBI se Inspector Rathore. Paise is UPI pe bhejo: rathore.cbi@okaxis. Mera number nau aath saat chhe paanch chaar teen do ek shunya.",
     "rathore.cbi@okaxis"),
    ("Madam account freeze ho jayega, turant safe account mein transfer karo, account number 123456789012, IFSC SBIN0001234.",
     "123456789012"),
    ("Aapka FedEx parcel customs ne pakda hai. Settlement ke liye 25,000 is UPI pe: customs.help@ybl",
     "customs.help@ybl"),
    ("Sir aapka electricity bill pending hai, aaj raat light kat jayegi, abhi 980 rupees pay karo bijli.office@paytm pe.",
     "bijli.office@paytm"),
    ("Congratulations KBC lottery 25 lakh! Processing fee 5000 bhejo kbc.prize2026@upi aur WhatsApp karo 9123456780 pe.",
     "kbc.prize2026@upi"),
]
INTEL_PROMPT = ("Extract scam intelligence from the scammer's words. Reply with JSON only: "
                '{"upi_ids": [], "phones": [], "accounts": [], "ifsc": [], "scam_type": "digital_arrest|courier_parcel|'
                'kyc_bank_block|electricity_bill|lottery_prize|job_task|investment|other", "red_flags": []}. '
                "Convert number words to digits.")

TRIAGE = [
    ("Velachery la thanni chest level vandhuruchu, naanga 5 per terrace la irukkom, en amma ku 80 vayasu, insulin venum.",
     "velachery"),
    ("Bhaiya Mudichur mein hum chaar log hain, paani kamar tak hai, ek chhota baccha hai, boat bhejo.", "mudichur"),
    ("Hello, Pallikaranai near the marsh road, water is knee level, three of us, my wife is pregnant.", "pallikaranai"),
    ("Tambaram railway station pakkathula, veetla thanni neck level, 2 per maadi la, current illa.", "tambaram"),
    ("Sir Adyar bridge ke paas, ground floor doob gaya, hum 6 log upar hain, dada ji ko oxygen chahiye.", "adyar"),
]
TRIAGE_PROMPT = ("You triage disaster calls. Reply with JSON only: "
                 '{"locality": "", "landmark": "", "people_count": null, "water_level": "none|ankle|knee|waist|chest|neck", '
                 '"vulnerable": [], "medical_needs": [], "needs": []}.')

SUGGEST = [
    ("Doctor: Aapko dard kahan ho raha hai? Gale mein ya seene mein?", "hi"),
    ("Nurse: Aapne subah ki dawai li ya nahi?", "hi"),
    ("Beta: Maa, aaj khana kya banaun aapke liye?", "hi"),
]
SUGGEST_PROMPT = ("You help a person who cannot speak reply quickly. Give exactly 3 short replies (max 8 words each) "
                  "in Hindi (Devanagari) that they might want to say. Reply with JSON only: {\"replies\": [\"\", \"\", \"\"]}.")


async def timed_stream(llm: LLM, messages) -> tuple[str, float, float]:
    t0 = time.perf_counter()
    first, text = None, ""
    async for d in llm.stream(messages, temperature=0.7, max_tokens=160):
        first = first or time.perf_counter() - t0
        text += d
    return text.strip(), first or 0.0, time.perf_counter() - t0


async def timed_json(llm: LLM, messages) -> tuple[dict | None, float, str]:
    t0 = time.perf_counter()
    raw = await llm.complete(messages, temperature=0.2, max_tokens=400, json_mode=True)
    dt = time.perf_counter() - t0
    try:
        return parse_json_loose(raw), dt, raw
    except ValueError:
        return None, dt, raw


async def main(args) -> None:
    s = get_settings()
    llm = LLM(s, provider=args.provider)
    rows, ttfts, json_ok, json_total = [], [], 0, 0
    print(f"provider={llm.provider} model={llm.model}")

    for key, script, system, lines in PERSONA:
        for line in lines:
            text, ttft, total = await timed_stream(llm, [{"role": "system", "content": system}, {"role": "user", "content": line}])
            ok = bool(re.search(SCRIPTS[script], text))
            ttfts.append(ttft)
            rows.append((f"persona:{key}", f"{ttft:.2f}", f"{total:.2f}", "✓" if ok else "✗", text[:70]))
            print(rows[-1])

    for line, expect in INTEL:
        obj, dt, raw = await timed_json(llm, [{"role": "system", "content": INTEL_PROMPT}, {"role": "user", "content": line}])
        json_total += 1
        found = bool(obj) and expect in json.dumps(obj, ensure_ascii=False)
        json_ok += bool(obj)
        rows.append(("intel_json", "-", f"{dt:.2f}", "✓" if found else "✗", (raw or "")[:70]))
        print(rows[-1])

    for line, expect in TRIAGE:
        obj, dt, raw = await timed_json(llm, [{"role": "system", "content": TRIAGE_PROMPT}, {"role": "user", "content": line}])
        json_total += 1
        found = bool(obj) and expect in str(obj.get("locality", "")).lower() + str(obj.get("landmark", "")).lower()
        json_ok += bool(obj)
        rows.append(("triage_json", "-", f"{dt:.2f}", "✓" if found else "✗", (raw or "")[:70]))
        print(rows[-1])

    for line, _ in SUGGEST:
        obj, dt, raw = await timed_json(llm, [{"role": "system", "content": SUGGEST_PROMPT}, {"role": "user", "content": line}])
        json_total += 1
        reps = (obj or {}).get("replies") if obj else None
        ok = isinstance(reps, list) and len(reps) == 3 and all(re.search(SCRIPTS["deva"], str(r)) for r in reps)
        json_ok += bool(obj)
        rows.append(("awaaz_suggest", "-", f"{dt:.2f}", "✓" if ok else "✗", (raw or "")[:70]))
        print(rows[-1])

    med = statistics.median(ttfts) if ttfts else 0
    out = repo_root() / "docs" / "evon-eval.md"
    out.parent.mkdir(exist_ok=True)
    lines = [f"\n## {llm.provider} ({llm.model}), {datetime.now():%d %b %H:%M}\n",
             f"- Median time to first token (persona): **{med:.2f} s**",
             f"- Valid JSON: **{json_ok}/{json_total}** ({100 * json_ok / max(1, json_total):.0f}%)\n",
             "| case | ttft s | total s | ok | output (start) |", "|---|---|---|---|---|"]
    lines += [f"| {a} | {b} | {c} | {d} | {e.replace('|', '/').replace(chr(10), ' ')} |" for a, b, c, d, e in rows]
    with out.open("a", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"\nmedian TTFT {med:.2f}s, valid JSON {json_ok}/{json_total}. Written to {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--provider", choices=["groq", "evon"], default="groq")
    asyncio.run(main(p.parse_args()))
