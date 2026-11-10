"""Generate docs/design/wireframe.svg (low-fidelity) for Pukaar.

Usage: python scripts/make_wireframe.py docs/design/wireframe.svg
"""
import sys
from xml.sax.saxutils import escape

W, H = 1600, 1240
INK, INK2, MUTED = "#0f172a", "#475569", "#94a3b8"
LINE, FILL, FILL2 = "#94a3b8", "#f8fafc", "#e2e8f0"
TEAL, AMBER = "#0e7490", "#b45309"
F = "font-family=\"'Segoe UI', Inter, Arial, sans-serif\""
out = []


def a(s):
    out.append(s)


def rect(x, y, w, h, rx=8, fill=FILL, stroke=LINE, sw=1.5, dash=None, extra=""):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d} {extra}/>')


def text(x, y, s, size=13, weight=400, fill=INK, anchor="start", extra=""):
    a(f'<text x="{x}" y="{y}" {F} font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}" {extra}>{escape(s)}</text>')


def bar(x, y, w, h=8, fill=FILL2):
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{h/2}" fill="{fill}"/>')


def button(x, y, w, h, label, primary=False, color=TEAL):
    if primary:
        rect(x, y, w, h, rx=10, fill=color, stroke=color)
        text(x + w / 2, y + h / 2 + 5, label, 13, 700, "#ffffff", "middle")
    else:
        rect(x, y, w, h, rx=10, fill="#ffffff", stroke=LINE)
        text(x + w / 2, y + h / 2 + 5, label, 13, 600, INK, "middle")


def card(x, y, w, h, title, right=None):
    rect(x, y, w, h, rx=14, fill="#ffffff", stroke=LINE)
    text(x + 16, y + 26, title, 15, 700)
    if right:
        text(x + w - 16, y + 26, right, 11.5, 600, INK2, "end")


def badge(n, x, y, color=TEAL):
    a(f'<circle cx="{x}" cy="{y}" r="13" fill="{color}"/>')
    text(x, y + 5, str(n), 13, 800, "#ffffff", "middle")


def arrow(d, color=TEAL, dash=None, sw=2.5):
    mk = "ah" if color == TEAL else "ahA"
    ds = f' stroke-dasharray="{dash}"' if dash else ""
    a(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{sw}"{ds} marker-end="url(#{mk})"/>')


a(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Pukaar wireframe: caller phone, control room and the path of one call">')
a('<title>Pukaar wireframe</title>')
a(f'<defs><marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{TEAL}"/></marker>'
  f'<marker id="ahA" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="{AMBER}"/></marker></defs>')
a(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')

# header + legend
text(40, 46, "Pukaar · wireframe", 26, 800)
text(40, 72, "Low-fidelity layout of the two screens, and the path one call takes between them (numbers = order of events).", 14, 400, INK2)
lx = 1040
a(f'<line x1="{lx}" y1="40" x2="{lx+40}" y2="40" stroke="{TEAL}" stroke-width="2.5" marker-end="url(#ah)"/>')
text(lx + 50, 45, "automated: Gnani + LLM + rules", 13, 600, INK2)
a(f'<line x1="{lx}" y1="66" x2="{lx+40}" y2="66" stroke="{AMBER}" stroke-width="2.5" marker-end="url(#ahA)"/>')
text(lx + 50, 71, "human decision (dispatcher, officer)", 13, 600, INK2)
a(f'<line x1="{lx+290}" y1="40" x2="{lx+330}" y2="40" stroke="{TEAL}" stroke-width="2.5" stroke-dasharray="6 5" marker-end="url(#ah)"/>')
text(lx + 340, 45, "fallback channel", 13, 600, INK2)

# ---------------- caller phone ----------------
px, py, pw, ph = 40, 110, 320, 730
rect(px, py, pw, ph, rx=40, fill="#ffffff", stroke=INK, sw=2.5)
rect(px + 120, py + 14, 80, 10, rx=5, fill=FILL2, stroke="none")
text(px + pw / 2, py - 10, "Caller phone (PWA, 390 px)", 14, 700, INK, "middle")
sx = px + 24  # screen content left
text(sx, py + 58, "CALLER PHONE", 11, 800, INK2, extra='letter-spacing="2"')
rect(px + pw - 104, py + 42, 80, 24, rx=12, fill=FILL, stroke=LINE)
text(px + pw - 64, py + 59, "Line idle", 11.5, 600, INK2, "middle")
a(f'<circle cx="{px+pw/2}" cy="{py+130}" r="50" fill="{FILL}" stroke="{LINE}" stroke-width="1.5"/>')
a(f'<circle cx="{px+pw/2}" cy="{py+130}" r="38" fill="{FILL2}" stroke="none"/>')
text(px + pw / 2, py + 135, "logo", 12, 600, INK2, "middle")
text(px + pw / 2, py + 208, "Pukaar helpline", 18, 800, INK, "middle")
text(px + pw / 2, py + 228, "Language: Auto · Tamil, Tanglish, Hindi, Telugu, English", 10.5, 400, INK2, "middle")
button(sx, py + 244, 272, 44, "Call Pukaar", primary=True)
button(sx, py + 298, 272, 36, "No balance? Give a missed call")
button(sx, py + 342, 272, 36, "Can't call? Send an SMS")
text(sx, py + 404, "Simulated phone location", 12, 600, INK2)
rect(sx, py + 412, 272, 32, rx=8, fill="#ffffff", stroke=LINE)
text(sx + 12, py + 433, "Velachery", 12.5, 500)
text(sx + 258, py + 433, "▾", 12.5, 500, INK2, "end")
text(sx, py + 466, "Rain and wind (SNR)", 12, 600, INK2)
rect(sx, py + 474, 272, 30, rx=8, fill=FILL, stroke=LINE)
for i, s in enumerate(["Off", "20 dB", "10 dB", "5 dB", "0 dB"]):
    cx = sx + 27 + i * 54.4
    if i == 0:
        rect(sx + 3, py + 477, 50, 24, rx=6, fill="#ffffff", stroke=LINE)
    text(cx, py + 494, s, 11, 600 if i == 0 else 400, INK if i == 0 else INK2, "middle")
# captions
rect(sx, py + 520, 272, 150, rx=10, fill=FILL, stroke=LINE)
text(sx + 12, py + 540, "Live captions", 11.5, 700, INK2)
rows = [("Caller", 190), ("Pukaar", 220), ("Caller", 150), ("Pukaar", 236)]
for i, (who, w) in enumerate(rows):
    yy = py + 560 + i * 26
    text(sx + 12, yy + 8, who, 10.5, 700, TEAL if who == "Pukaar" else INK2)
    bar(sx + 64, yy, w - 64 + 10, 10, FILL2 if who == "Caller" else "#cfe7ee")
rect(sx, py + 680, 272, 26, rx=8, fill="#ffffff", stroke=LINE, dash="4 3")
text(sx + 12, py + 697, "▶ Missed callback (play later)", 11.5, 600, INK2)
text(px + pw / 2, py + ph + 22, "Simulated emergency call: synthetic data", 11.5, 600, AMBER, "middle")

# ---------------- control room ----------------
cx0, cy0, cw, ch = 440, 110, 1120, 880
text(cx0 + cw / 2, cy0 - 10, "Control room (desktop, 1440 px)", 14, 700, INK, "middle")
rect(cx0, cy0, cw, ch, rx=14, fill="#ffffff", stroke=INK, sw=2.5)
a(f'<path d="M{cx0} {cy0+32}H{cx0+cw}" stroke="{LINE}" stroke-width="1.5"/>')
for i in range(3):
    a(f'<circle cx="{cx0+20+i*16}" cy="{cy0+16}" r="5" fill="{FILL2}" stroke="{LINE}"/>')
rect(cx0 + 90, cy0 + 7, 300, 18, rx=9, fill=FILL, stroke=LINE)
text(cx0 + 102, cy0 + 20, "pukaar · #/app", 11, 500, INK2)
# sidebar
sbx, sby = cx0, cy0 + 32
rect(sbx + 1, sby, 158, ch - 33, rx=0, fill=FILL, stroke="none")
a(f'<path d="M{sbx+160} {sby}V{cy0+ch}" stroke="{LINE}" stroke-width="1.5"/>')
rect(sbx + 16, sby + 18, 32, 32, rx=8, fill=FILL2, stroke=LINE)
text(sbx + 58, sby + 32, "Pukaar", 15, 800)
text(sbx + 58, sby + 46, "AI DISASTER HELPLINE", 7.5, 700, INK2, extra='letter-spacing="1"')
rect(sbx + 12, sby + 74, 136, 30, rx=8, fill="#ffffff", stroke=LINE)
text(sbx + 24, sby + 94, "☎  Live helpline", 12.5, 700)
text(sbx + 16, cy0 + ch - 30, "Built on Gnani AI", 10.5, 500, INK2)
text(sbx + 16, cy0 + ch - 16, "Prisma · Timbre", 10.5, 500, INK2)
# top bar
tx = cx0 + 180
text(tx, sby + 28, "Pukaar control room", 16, 800)
text(tx, sby + 46, "Flood night in Chennai · Gnani Prisma + Timbre", 11.5, 400, INK2)
rect(cx0 + cw - 190, sby + 18, 170, 26, rx=13, fill=FILL, stroke=LINE)
text(cx0 + cw - 105, sby + 36, "● Gnani live / Recorded run", 11, 600, INK2, "middle")
a(f'<path d="M{cx0+160} {sby+60}H{cx0+cw}" stroke="{LINE}" stroke-width="1"/>')
# KPIs
kx, ky, kw = tx, sby + 76, (cw - 200 - 36) / 4
for i, (v, l) in enumerate([("25", "Calls answered"), ("0.93 s", "Avg reply time"), ("5", "Critical open"), ("79", "People affected")]):
    x = kx + i * (kw + 12)
    rect(x, ky, kw, 60, rx=12, fill="#ffffff", stroke=LINE)
    text(x + 14, ky + 30, v, 20, 800)
    text(x + 14, ky + 49, l, 11.5, 500, INK2)
# left column: map
lx0, lw = tx, 470
my = ky + 76
card(lx0, my, lw, 300, "Rescue map")
button(lx0 + lw - 196, my + 9, 120, 28, "Simulate surge")
rect(lx0 + lw - 68, my + 12, 52, 22, rx=11, fill=FILL, stroke=LINE)
text(lx0 + lw - 42, my + 27, "Live", 11, 600, INK2, "middle")
rect(lx0 + 14, my + 46, lw - 28, 240, rx=10, fill=FILL, stroke=LINE)
# map scribbles: roads, coast
a(f'<path d="M{lx0+30} {my+120} C {lx0+120} {my+100}, {lx0+200} {my+150}, {lx0+330} {my+110}" fill="none" stroke="{FILL2}" stroke-width="6"/>')
a(f'<path d="M{lx0+90} {my+60} C {lx0+130} {my+150}, {lx0+170} {my+200}, {lx0+250} {my+280}" fill="none" stroke="{FILL2}" stroke-width="6"/>')
a(f'<path d="M{lx0+360} {my+50} C {lx0+340} {my+130}, {lx0+390} {my+200}, {lx0+370} {my+286}" fill="none" stroke="{LINE}" stroke-width="1.5" stroke-dasharray="5 4"/>')
text(lx0 + 420, my + 170, "sea", 11, 500, MUTED, "middle")
pins = [(160, 190, "#0f172a", "4"), (230, 230, "#0f172a", "2"), (120, 150, "#64748b", "2"), (290, 120, "#64748b", ""), (200, 260, "#0f172a", "3"), (80, 100, "#cbd5e1", "")]
for (x, y, c, n) in pins:
    a(f'<circle cx="{lx0+x}" cy="{my+y}" r="11" fill="{c}" stroke="#ffffff" stroke-width="2"/>')
    if n:
        text(lx0 + x, my + y + 4, n, 10.5, 800, "#ffffff", "middle")
a(f'<circle cx="{lx0+160}" cy="{my+190}" r="34" fill="none" stroke="{TEAL}" stroke-width="1.5" stroke-dasharray="4 4"/>')
text(lx0 + 200, my + 160, "300 m / 3 h merge", 10.5, 600, TEAL)
text(lx0 + 24, my + 278, "pin size = callers · shade = severity", 10.5, 500, INK2)
# queue
qy = my + 316
card(lx0, qy, lw, 228, "Queue by severity", "click a row → incident sheet")
qrows = [("92", "Mylapore", "Flood · 8 people · 2 callers", "new"), ("90", "Velachery", "Flood · 4 people · 4 callers · live", "live"), ("68", "Mudichur", "SMS · 5 people · pregnant woman", "dispatched"), ("57", "Saidapet", "SMS · 3 people · sick child", "new")]
for i, (s, place, sub, st) in enumerate(qrows):
    y = qy + 42 + i * 45
    rect(lx0 + 12, y, lw - 24, 40, rx=8, fill=FILL if i != 1 else "#eef7f9", stroke=LINE if i != 1 else TEAL)
    rect(lx0 + 22, y + 10, 40, 20, rx=10, fill="#0f172a" if int(s) >= 70 else "#64748b", stroke="none")
    text(lx0 + 42, y + 24, s, 11, 800, "#ffffff", "middle")
    text(lx0 + 74, y + 17, place, 12.5, 700)
    text(lx0 + 74, y + 32, sub, 10.5, 400, INK2)
    rect(lx0 + lw - 100, y + 10, 76, 20, rx=10, fill="#ffffff", stroke=LINE)
    text(lx0 + lw - 62, y + 24, st, 10.5, 600, INK2, "middle")
# drill
dy = qy + 244
card(lx0, dy, lw, ch - (dy - cy0) - 16, "Noise drill", "rain mixed into 8 kHz calls")
cols = ["", "clean", "20 dB", "10 dB", "5 dB", "0 dB"]
for j, c in enumerate(cols):
    text(lx0 + 24 + j * 76, dy + 52, c, 11, 700, INK2)
for i, r in enumerate(["Locality", "Severity"]):
    text(lx0 + 24, dy + 74 + i * 20, r, 11, 600, INK)
    for j in range(1, 6):
        bar(lx0 + 24 + j * 76, dy + 66 + i * 20, 50, 8)
# right column: incident sheet
rx0, rw = lx0 + lw + 16, cx0 + cw - (lx0 + lw + 16) - 20
iy = my
card(rx0, iy, rw, 392, "Incident sheet · Velachery", "critical 90")
text(rx0 + 16, iy + 52, "Why this severity", 11.5, 700, INK2)
drivers = [("Flood", 20), ("Chest-deep water", 30), ("On the roof", 10), ("Elderly + child", 14), ("Insulin", 10), ("4 people", 6)]
for i, (lbl, pts) in enumerate(drivers):
    y = iy + 64 + i * 19
    text(rx0 + 16, y + 9, lbl, 11, 500)
    bar(rx0 + 136, y + 1, pts * 6, 9, "#64748b")
    text(rx0 + 142 + pts * 6, y + 10, f"+{pts}", 10.5, 700, INK2)
text(rx0 + 16, iy + 196, "Facts", 11.5, 700, INK2)
for i, chip in enumerate(["water: chest", "people: 4", "vulnerable: elderly, child", "medical: insulin"]):
    x = rx0 + 16 + (i % 2) * 170
    y = iy + 206 + (i // 2) * 26
    rect(x, y, 160, 20, rx=10, fill=FILL, stroke=LINE)
    text(x + 10, y + 14, chip, 10.5, 500, INK2)
text(rx0 + 16, iy + 274, "Approved guidance given: FLD-01 (one per reply)", 11, 500, INK2)
a(f'<path d="M{rx0+12} {iy+286}H{rx0+rw-12}" stroke="{LINE}" stroke-width="1" stroke-dasharray="4 3"/>')
text(rx0 + 16, iy + 306, "Dispatch (human)", 11.5, 800, AMBER)
rect(rx0 + 16, iy + 314, 150, 28, rx=8, fill="#ffffff", stroke=LINE)
text(rx0 + 26, iy + 333, "NDRF Boat 1  ▾", 11.5, 500)
rect(rx0 + 174, iy + 314, 70, 28, rx=8, fill="#ffffff", stroke=LINE)
text(rx0 + 184, iy + 333, "ETA 40", 11.5, 500, INK2)
button(rx0 + 252, iy + 314, rw - 268, 28, "Confirm dispatch", primary=True, color=AMBER)
rect(rx0 + 16, iy + 350, rw - 100, 28, rx=8, fill="#ffffff", stroke=LINE)
text(rx0 + 26, iy + 369, "Message the caller (English)…", 11, 400, MUTED)
button(rx0 + rw - 76, iy + 350, 60, 28, "Send")
# broadcast
by = iy + 408
card(rx0, by, rw, 236, "Broadcast alert", "CAP 1.2")
rect(rx0 + 16, by + 40, rw - 32, 52, rx=8, fill="#ffffff", stroke=LINE)
text(rx0 + 26, by + 60, "Type one English alert…", 11.5, 400, MUTED)
bar(rx0 + 26, by + 72, 220, 8)
for i, l in enumerate(["ta", "hi", "te", "ml", "kn", "bn", "en"]):
    x = rx0 + 16 + i * 46
    rect(x, by + 102, 40, 22, rx=11, fill=FILL, stroke=LINE)
    text(x + 20, by + 117, l, 11, 700, INK2, "middle")
button(rx0 + 16, by + 134, 170, 30, "Translate and speak", primary=True)
button(rx0 + 196, by + 134, rw - 212, 30, "Download CAP 1.2 XML")
for i, l in enumerate(["▶ Tamil", "▶ Hindi"]):
    y = by + 174 + i * 26
    rect(rx0 + 16, y, rw - 32, 20, rx=10, fill=FILL, stroke=LINE)
    text(rx0 + 26, y + 14, l, 10.5, 600, INK2)
    bar(rx0 + 90, y + 7, rw - 130, 6)
# select arrow queue -> sheet
arrow(f"M{lx0+lw-12} {qy+42+45+20} C {lx0+lw+8} {qy+80}, {rx0-20} {iy+260}, {rx0-2} {iy+240}", color=TEAL, sw=1.8)

# ---------------- server lane ----------------
sy = 1070
rect(40, sy - 22, 1520, 142, rx=16, fill="#f8fafc", stroke=LINE, dash="6 5")
text(60, sy + 112, "Server (FastAPI) · the path of one call", 13, 800, INK2)
boxes = [
    (110, "Gnani Prisma v3.0", "8 kHz · indic-auto · codemix"),
    (350, "LLM fact extraction", "Groq qwen3.8-27b"),
    (590, "Rules · locate · dedup", "0–100 · gazetteer · 300 m"),
    (830, "Reply + guard", "approved IDs · no ETA promise"),
    (1070, "Gnani Timbre v3.0", "reply · callback · broadcast"),
    (1340, "CAP 1.2 XML", "status: Exercise"),
]
for (x, t, s) in boxes:
    w = 190 if x != 1340 else 190
    rect(x, sy + 12, w, 64, rx=12, fill="#ffffff", stroke=TEAL, sw=1.8)
    text(x + w / 2, sy + 40, t, 13.5, 800, INK, "middle")
    text(x + w / 2, sy + 60, s, 11, 500, INK2, "middle")
for i in range(4):
    x1 = boxes[i][0] + 190
    x2 = boxes[i + 1][0]
    arrow(f"M{x1+2} {sy+44}H{x2-4}")

# flows
# 1 phone -> Prisma (voice), dashed SMS -> LLM
arrow(f"M160 {py+ph+32}V{sy+8}")
badge(1, 160, 930)
text(178, 926, "speech over /ws/call", 11.5, 700, TEAL)
text(178, 942, "(missed call / SMS: /api/sms)", 11, 600, INK2)
arrow(f"M90 {py+ph+32} C 70 {py+ph+150}, 330 {sy-40}, 400 {sy+8}", dash="6 5", sw=2)
# 2 Timbre -> phone (reply)
arrow(f"M1165 {sy+78}V{sy+104}H330V{py+ph+32}")
badge(2, 330, 1020)
text(348, 1025, "reply audio in the caller's language", 11.5, 700, TEAL)
# 3 rules -> control room
arrow(f"M685 {sy+10}V{cy0+ch+4}")
badge(3, 685, 1030)
text(703, 1035, "incident upsert → /ws/control: pin + queue", 11.5, 700, TEAL)
# 4 dispatch -> Timbre (amber)
arrow(f"M{rx0+rw-16} {iy+328}H1576V1030H1200V{sy+10}", color=AMBER)
badge(4, 1240, 1030, AMBER)
text(1258, 1022, "confirmed dispatch → callback / relay", 11.5, 700, AMBER)
# 5 broadcast -> CAP (amber)
arrow(f"M{rx0+rw-16} {by+149}H1592V1054H1435V{sy+10}", color=AMBER)
badge(5, 1540, 1054, AMBER)
text(1446, 1075, "broadcast alert", 11.5, 700, AMBER)

text(W - 40, H - 14, "Pukaar · low-fidelity wireframe · synthetic data", 11, 500, MUTED, "end")
a("</svg>")
open(sys.argv[1], "w", encoding="utf-8").write("\n".join(out))
print("ok")
