# Noise drill results

6 synthetic distress calls (seed 11), spoken by Gnani Timbre v3.0 in Tamil, Hindi, Telugu or English, band-limited to 8 kHz phone audio, buried in synthetic rain at each SNR, transcribed by Gnani Prisma v3.0 (REST, `indic-auto`, Pukaar keyterms), then triaged by the LLM.

Reference = facts extracted from the exact words, so the scores show only what noise and speech-to-text lose. The clean row is the baseline: differences there come from LLM extraction, not audio. CER (in brackets: rows counted) skips pairs in different scripts, e.g. romanised Hinglish vs Prisma's Devanagari. Language = the language the case asked for.

## By noise level

| SNR (dB) | n | Transcript CER ↓ | Locality | People count | Water level | Vulnerable F1 | Severity level |
|---|---|---|---|---|---|---|---|
| clean | 6 | 7.5% (3) | 67% | 100% | 50% | 100% | 67% |
| 20 dB | 6 | 21.5% (4) | 67% | 83% | 50% | 100% | 67% |
| 10 dB | 6 | 23.2% (4) | 67% | 100% | 67% | 100% | 67% |
| 5 dB | 6 | 11.3% (3) | 67% | 83% | 67% | 100% | 67% |
| 0 dB | 6 | 10.8% (3) | 67% | 83% | 67% | 100% | 67% |

## By language (all noise levels)

| Language | n | Transcript CER ↓ | Locality | People count | Water level | Vulnerable F1 | Severity level |
|---|---|---|---|---|---|---|---|
| en-IN | 15 | 28.5% (7) | 67% | 80% | 53% | 100% | 67% |
| ta-IN | 10 | 6.9% (10) | 50% | 100% | 50% | 100% | 50% |
| hi-IN | 5 | n/a | 100% | 100% | 100% | 100% | 100% |
