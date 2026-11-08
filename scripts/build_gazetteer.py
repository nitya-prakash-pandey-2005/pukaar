"""Build backend/data/gazetteer_chennai.json from OpenStreetMap Nominatim (run once; output is committed).

Usage: uv run python scripts/build_gazetteer.py
"""

import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "backend" / "data" / "gazetteer_chennai.json"

# name -> aliases (Tamil script, common spellings, Devanagari for the demo localities)
PLACES = {
    "Velachery": ["வேளச்சேரி", "Velacheri", "वेलाचेरी"],
    "Tambaram": ["தாம்பரம்", "Thambaram", "ताम्बरम"],
    "Mudichur": ["முடிச்சூர்", "Mudichoor", "मुडिचूर"],
    "Pallikaranai": ["பள்ளிக்கரணை", "Pallikkaranai", "पल्लिकरणई"],
    "Adyar": ["அடையாறு", "Adayar"],
    "Saidapet": ["சைதாப்பேட்டை", "Saidapettai"],
    "Kotturpuram": ["கோட்டூர்புரம்"],
    "Ashok Nagar": ["அசோக் நகர்", "Ashoknagar"],
    "KK Nagar": ["கே.கே. நகர்", "K K Nagar", "Kalaignar Karunanidhi Nagar"],
    "Ramapuram": ["ராமாபுரம்"],
    "Manapakkam": ["மணப்பாக்கம்"],
    "Perungudi": ["பெருங்குடி"],
    "Thoraipakkam": ["துரைப்பாக்கம்", "Thuraipakkam"],
    "Madipakkam": ["மடிப்பாக்கம்"],
    "Medavakkam": ["மேடவாக்கம்"],
    "Chromepet": ["குரோம்பேட்டை", "Chrompet"],
    "Pallavaram": ["பல்லாவரம்"],
    "Porur": ["போரூர்"],
    "Valasaravakkam": ["வளசரவாக்கம்"],
    "Virugambakkam": ["விருகம்பாக்கம்"],
    "Ekkattuthangal": ["ஈக்காட்டுத்தாங்கல்", "Ekkaduthangal"],
    "Jafferkhanpet": ["ஜாபர்கான்பேட்டை", "Jafferkhanpettai"],
    "T Nagar": ["தி. நகர்", "Thyagaraya Nagar", "T. Nagar"],
    "Mylapore": ["மயிலாப்பூர்", "Mylapur"],
    "Royapuram": ["ராயபுரம்"],
    "Vyasarpadi": ["வியாசர்பாடி"],
    "Kolathur": ["கொளத்தூர்"],
    "Perambur": ["பெரம்பூர்"],
    "Ambattur": ["அம்பத்தூர்"],
    "Avadi": ["ஆவடி"],
    "Korattur": ["கொரட்டூர்"],
    "Anna Nagar": ["அண்ணா நகர்", "Annanagar"],
    "Arumbakkam": ["அரும்பாக்கம்"],
    "Koyambedu": ["கோயம்பேடு"],
    "Guindy": ["கிண்டி", "Guindi"],
    "Nanganallur": ["நங்கநல்லூர்"],
    "Keelkattalai": ["கீழ்கட்டளை", "Keezhkattalai"],
    "Selaiyur": ["சேலையூர்"],
    "Varadharajapuram": ["வரதராஜபுரம்"],
    "Semmencherry": ["செம்மஞ்சேரி", "Semmanjeri"],
    "Sholinganallur": ["சோழிங்கநல்லூர்", "Shollinganallur"],
    "Kodambakkam": ["கோடம்பாக்கம்"],
}

# Names that the default query resolves to the wrong place (or not at all)
QUERY = {
    "Semmencherry": "Semmancheri, Chennai",
    "Varadharajapuram": "Varadarajapuram, Tambaram",
    "Medavakkam": "Medavakkam, Chengalpattu",
}


def lookup(name: str) -> tuple[float, float] | None:
    q = urllib.parse.urlencode({"format": "json", "limit": 1, "q": QUERY.get(name, f"{name}, Chennai, Tamil Nadu")})
    req = urllib.request.Request(f"https://nominatim.openstreetmap.org/search?{q}",
                                 headers={"User-Agent": "pukaar-hackathon-demo"})
    with urllib.request.urlopen(req, timeout=20) as r:
        hits = json.load(r)
    return (round(float(hits[0]["lat"]), 5), round(float(hits[0]["lon"]), 5)) if hits else None


def main() -> None:
    out = []
    for name, aliases in PLACES.items():
        ll = lookup(name)
        time.sleep(1.1)  # Nominatim policy: at most 1 request per second
        if ll is None:
            print("not found:", name)
            continue
        out.append({"name": name, "aliases": aliases, "lat": ll[0], "lon": ll[1]})
        print(name, ll)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(out)} places -> {OUT}")


if __name__ == "__main__":
    main()
