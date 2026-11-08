"""Run the noise drill against live Gnani + LLM and save the results (spends Gnani credits; TTS is cached).

Usage: uv run python scripts/run_drill.py [--n 6] [--seed 11]
       uv run python scripts/run_drill.py --rescore   (re-score saved transcripts; LLM only, no Gnani credits)
Writes backend/data/drill_results.json (served at /api/drill) and docs/drill-results.md.
"""

import argparse
import asyncio
import json
import random
from pathlib import Path

from voice_core.config import get_settings
from voice_core.llm import LLM

from pukaar.data import DATA, load_gazetteer
from pukaar.drill import SNRS, RetryLLM, rescore, run_drill

ROOT = Path(__file__).resolve().parents[1]
COLS = [("cer", "Transcript CER ↓"), ("locality", "Locality"), ("people", "People count"),
        ("water_level", "Water level"), ("vulnerable_f1", "Vulnerable F1"), ("severity_level", "Severity level")]


def table(groups: dict, first: str) -> str:
    lines = [f"| {first} | n | " + " | ".join(c[1] for c in COLS) + " |", "|" + "---|" * (len(COLS) + 2)]
    for k, g in groups.items():
        cells = [f"{g['cer']:.1%} ({g['n_cer']})" if g["cer"] is not None else "n/a"] + [f"{g[c]:.0%}" for c, _ in COLS[1:]]
        lines.append(f"| {k if k == 'clean' or first != 'SNR (dB)' else k + ' dB'} | {g['n']} | " + " | ".join(cells) + " |")
    return "\n".join(lines)


async def main(args) -> None:
    s = get_settings()

    async def emit(m):
        print(f"case {m['case']} {m['lang']} snr={m['snr']}: cer={m['cer']:.2f} loc={m['locality']} "
              f"people={m['people']} water={m['water_level']} sev={m['severity_level']}", flush=True)

    llm = RetryLLM(LLM(s, purpose="intel"))
    if args.rescore:
        out = await rescore(json.loads((DATA / "drill_results.json").read_text(encoding="utf-8"))["rows"], llm, load_gazetteer())
        args.n = len({r["case"] for r in out["rows"]})
    else:
        out = await run_drill(args.n, SNRS, s, llm, emit, random.Random(args.seed), load_gazetteer())
    (DATA / "drill_results.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    md = (f"# Noise drill results\n\n{args.n} synthetic distress calls (seed {args.seed}), spoken by Gnani Timbre v3.0 in "
          f"Tamil, Hindi, Telugu or English, band-limited to 8 kHz phone audio, buried in synthetic rain at each SNR, "
          f"transcribed by Gnani Prisma v3.0 (REST, `indic-auto`, Pukaar keyterms), then triaged by the LLM.\n\n"
          f"Reference = facts extracted from the exact words, so the scores show only what noise and speech-to-text lose. "
          f"The clean row is the baseline: differences there come from LLM extraction, not audio. "
          f"CER (in brackets: rows counted) skips pairs in different scripts, e.g. romanised Hinglish vs Prisma's Devanagari. "
          f"Language = the language the case asked for.\n\n"
          f"## By noise level\n\n{table(out['summary']['by_snr'], 'SNR (dB)')}\n\n"
          f"## By language (all noise levels)\n\n{table(out['summary']['by_lang'], 'Language')}\n")
    (ROOT / "docs" / "drill-results.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--rescore", action="store_true")
    asyncio.run(main(ap.parse_args()))
