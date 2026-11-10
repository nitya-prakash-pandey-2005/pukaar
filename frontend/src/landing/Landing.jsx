import { Fragment, useEffect, useRef } from "react";
import { animate, createTimeline, stagger, svg } from "animejs";
import {
  ArrowRight, AudioLines, BellRing, Github, Languages, MapPinned, MessageSquareText, PhoneIncoming, PlayCircle,
  ShieldCheck, Siren, SlidersHorizontal, Truck, Waves, FileText, Radar, Check,
} from "lucide-react";
import "../landing.css";

// Links the lead can change after deployment
export const VIDEO_URL = "https://github.com/nitya-prakash-pandey-2005/pukaar#readme";
export const REPO_URL = "https://github.com/nitya-prakash-pandey-2005/pukaar";
export const PUKAAR_URL = "https://pukaar-snowy.vercel.app/";
export const DADI_URL = "https://dadi-vs-scammers.vercel.app/";
export const AWAAZ_URL = "https://apni-awaaz-kappa.vercel.app/";
const DADI_REPO = "https://github.com/nitya-prakash-pandey-2005/dadi-vs-scammers";
const AWAAZ_REPO = "https://github.com/nitya-prakash-pandey-2005/apni-awaaz";
const APP_HREF = "#/app";

const reduceMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const scrollToId = (id) => document.getElementById(id)?.scrollIntoView({ behavior: reduceMotion() ? "auto" : "smooth", block: "start" });

const HEADLINE = ["When", "every", "line", "is", "busy,", "Pukaar", "picks", "up."];

const DRIVERS = [
  ["Flood", 20], ["Chest-deep water", 30], ["On the roof", 10], ["Elderly and a child", 14], ["Needs insulin", 10], ["4 people", 6],
];

const FEATURES = [
  {
    icon: Languages, kicker: "01 · Voice", title: "Answers in the caller's language",
    body: "Gnani Prisma v3.0 transcribes code-mixed 8 kHz phone audio with automatic Indic language detection. Timbre v3.0 replies in the same language: one line of reassurance, at most one approved safety instruction, one question.",
    points: ["Tamil, Tanglish, Hindi, Telugu, English", "Where → how many → hurt → water level → vulnerable people", "Greeting and fillers pre-rendered, so no dead air"],
    img: "desktop-live-call", alt: "A live Tamil call with captions on the caller phone and the incident marked live in the queue",
  },
  {
    icon: SlidersHorizontal, kicker: "02 · Triage", title: "Severity you can explain, point by point",
    body: "The LLM only extracts facts. A fixed rule table turns them into a 0–100 score and shows every point, so a dispatcher can see exactly why one rooftop outranks another.",
    points: ["Critical at 70, high at 45", "Every driver shown as a bar", "The rules rank; a human decides"],
    severity: true,
  },
  {
    icon: MapPinned, kicker: "03 · Map", title: "Landmarks become pins. Five calls, one rescue.",
    body: "\"Near the Vijayanagar bus stop\" is matched against a Chennai gazetteer of 42 localities with Tamil aliases. Reports within 300 m and 3 hours about the same hazard merge into one incident with a caller count.",
    points: ["Phone location plus spoken landmarks", "300 m · 3 h · same hazard", "A merged report can raise the water level, never lower it"],
    img: "desktop-control-room", alt: "Control room after a surge: KPIs, merged pins and the severity queue",
  },
];

const GRID = [
  { icon: ShieldCheck, title: "Never false reassurance", body: "A guard blocks \"you are safe\" and any arrival time in four languages until a dispatcher confirms an ETA. A blocked reply becomes a safe fallback line.", img: "mobile-guard-fallback", tall: true, alt: "Live call: Tamil caller lines, then Pukaar's safe fallback line" },
  { icon: Truck, title: "Dispatch recommender, human confirms", body: "Ranks free teams out of 100 by kind, capacity and ETA, and says why. \"Dispatch this team\" only fills the form.", img: "desktop-recommended-teams", alt: "Recommended teams with scores and reasons" },
  { icon: FileText, title: "District SitRep", body: "Calls, incidents by severity, people affected, vulnerable households and critical waits on one page. Prints to PDF.", img: "desktop-sitrep", alt: "District situation report" },
  { icon: Radar, title: "Hotspots", body: "Open incidents within 500 m are grouped and ringed on the map, sized by people and coloured by the worst severity.", img: "desktop-overview", alt: "Rescue map with severity-coloured pins and hotspot rings" },
  { icon: BellRing, title: "Broadcast in 7 languages + CAP 1.2", body: "One English alert, spoken by Timbre in Tamil, Hindi, Telugu, Malayalam, Kannada, Bengali and English, exported as CAP 1.2 XML.", img: "desktop-broadcast", alt: "Broadcast alert with audio in several languages" },
  { icon: MessageSquareText, title: "SMS intake", body: "No voice, weak network? One text goes through the same triage, lands on the same map and gets the next question back.", img: "desktop-sms-reply", alt: "A Tamil SMS triaged with a Tamil reply" },
  { icon: Waves, title: "Noise drill, built in", body: "Synthetic calls buried in rain at 0–20 dB, transcribed by Prisma and triaged. Triage accuracy stayed flat down to 0 dB.", img: "desktop-noise-drill", alt: "Noise drill results by language and SNR" },
  { icon: AudioLines, title: "Rescuer interpreter", body: "A Hindi-speaking boat crew, a Tamil-speaking caller. Push to talk; Prisma, one LLM call and Timbre translate each side, with captions in both languages.", interp: true },
];

const STATS = [
  { from: 90, to: 133, unit: "ms", label: "Prisma streaming transcript latency", note: "first live call, 8 Nov" },
  { from: 0.72, to: 1.05, unit: "s", dec: 2, label: "LLM time to the first reply sentence", note: "live run, 10 Nov" },
  { to: 90, label: "Critical severity, explained", note: "+20 +30 +10 +14 +10 +6", prefix: "" },
  { to: 277, label: "Automated tests passing", note: "175 backend · 102 voice-core" },
  { to: 42, label: "Chennai localities with Tamil aliases", note: "the landmark gazetteer" },
  { from: 1.6, to: 2.3, unit: "s", dec: 1, label: "Interpreter: release to translated audio", note: "Hindi ↔ Tamil, 10 Nov" },
];

function Shot({ name, alt, className = "", eager = false }) {
  return (
    <figure className={`lp-shot ${className}`}>
      <div className="lp-shot-bar"><i /><i /><i /><span>pukaar · control room</span></div>
      <img src={`/landing/${name}.webp`} alt={alt} width="1280" height="800" loading={eager ? "eager" : "lazy"} decoding="async" fetchpriority={eager ? "high" : undefined} />
    </figure>
  );
}

function Logo({ size = 34 }) {
  return <img src="/landing/logo.svg" width={size} height={size} alt="" className="lp-logo" />;
}

function Nav() {
  return (
    <header className="lp-nav">
      <a className="lp-brand" href="#/" aria-label="Pukaar home"><Logo size={30} /><b>Pukaar</b><span className="lp-brand-sub">पुकार · புகார்</span></a>
      <nav className="lp-nav-links" aria-label="Sections">
        <button onClick={() => scrollToId("problem")}>Problem</button>
        <button onClick={() => scrollToId("features")}>Features</button>
        <button onClick={() => scrollToId("how")}>How it works</button>
        <button onClick={() => scrollToId("results")}>Results</button>
      </nav>
      <a className="lp-btn lp-btn-sm" href={APP_HREF}>Open control room <ArrowRight size={15} /></a>
    </header>
  );
}

function Hero() {
  return (
    <section className="lp-hero" aria-labelledby="lp-title">
      <div className="lp-water" aria-hidden="true">
        <svg viewBox="0 0 1440 320" preserveAspectRatio="none" className="lp-waves">
          <path className="lp-wave w1" d="M0 160 C 240 110 480 210 720 160 S 1200 110 1440 160 S 1920 210 2160 160 S 2640 110 2880 160 V320 H0Z" />
          <path className="lp-wave w2" d="M0 200 C 240 160 480 240 720 200 S 1200 160 1440 200 S 1920 240 2160 200 S 2640 160 2880 200 V320 H0Z" />
          <path className="lp-wave w3" d="M0 240 C 240 215 480 265 720 240 S 1200 215 1440 240 S 1920 265 2160 240 S 2640 215 2880 240 V320 H0Z" />
        </svg>
      </div>
      <div className="lp-hero-grid">
        <div className="lp-hero-copy">
          <div className="lp-eyebrow" data-hero>
            <span className="lp-live-dot" />AI overflow line for floods · built on Gnani Prisma + Timbre
          </div>
          <h1 id="lp-title" className="lp-h1">
            {HEADLINE.map((w, i) => (
              <Fragment key={i}><span className="lp-word"><span className={w.startsWith("Pukaar") ? "lp-grad-text" : ""}>{w}</span></span>{i < HEADLINE.length - 1 ? " " : ""}</Fragment>
            ))}
          </h1>
          <p className="lp-sub" data-hero>
            Pukaar answers overflow emergency calls in the caller's own language, keeps them calm, asks what a rescuer needs, and puts every caller on a live rescue map. <b>A human confirms every dispatch.</b>
          </p>
          <div className="lp-ctas" data-hero>
            <a className="lp-btn" href={APP_HREF}><PhoneIncoming size={18} /> Open the live control room</a>
            <a className="lp-btn lp-btn-ghost" href={VIDEO_URL} target="_blank" rel="noreferrer"><PlayCircle size={18} /> Watch the 3-minute video</a>
          </div>
          <ul className="lp-chips" data-hero>
            <li>Tamil · Tanglish · Hindi · Telugu · English</li>
            <li>Explainable 0–100 severity</li>
            <li>CAP 1.2 alerts</li>
          </ul>
        </div>
        <div className="lp-hero-visual">
          <div className="lp-ripple" aria-hidden="true">
            <span /><span /><span />
            <div className="lp-ripple-core"><Logo size={56} /></div>
          </div>
          <div className="lp-float">
            <Shot name="desktop-overview" eager alt="Pukaar control room: the caller phone, live KPIs and the rescue map with severity-coloured pins" className="lp-hero-shot" />
            <div className="lp-float-card lp-fc-1" aria-hidden="true"><Siren size={15} /><span><b>Critical 90</b> · Velachery · 4 callers merged</span></div>
            <div className="lp-float-card lp-fc-2" aria-hidden="true"><Languages size={15} /><span lang="ta">அவங்களுக்கு insulin வேணும்.</span></div>
          </div>
        </div>
      </div>
    </section>
  );
}

function Problem() {
  return (
    <section id="problem" className="lp-section lp-problem">
      <div className="lp-head" data-reveal>
        <div className="lp-kicker">The problem</div>
        <h2>In a flood, the helpline is the first thing to drown.</h2>
        <p>Every helpline has a fixed number of call-takers, and a flood brings every call at once. People fall back to social media and volunteer spreadsheets, and the control room loses sight of them.</p>
      </div>
      <div className="lp-facts">
        <article className="lp-fact" data-reveal>
          <div className="lp-fact-tag">Chennai · Cyclone Michaung · Dec 2023</div>
          <blockquote>"Almost every call to the complaint cell went unanswered till December 7."</blockquote>
          <p>Power and mobile networks were down for three to four days.</p>
          <a href="https://www.dtnext.in/news/city/calls-to-govt-helplines-go-unanswered-754073" target="_blank" rel="noreferrer">DT Next, 13 Dec 2023 ↗</a>
        </article>
        <article className="lp-fact" data-reveal>
          <div className="lp-fact-tag">Kerala floods · Aug 2018</div>
          <div className="lp-fact-num"><span data-count="483">483</span><small>people died</small></div>
          <p>Volunteers built keralarescue.in in about a day. It received <b>over 1 crore</b> aid and rescue requests.</p>
          <div className="lp-fact-links">
            <a href="https://morungexpress.com/483-dead-flood-loss-more-keralas-annual-outlay-vijayan" target="_blank" rel="noreferrer">Morung Express/IANS ↗</a>
            <a href="https://theprint.in/governance/behind-official-kerala-rescue-website-are-1500-techies-working-for-free/102568" target="_blank" rel="noreferrer">ThePrint ↗</a>
          </div>
        </article>
        <article className="lp-fact" data-reveal>
          <div className="lp-fact-tag">Kerala · 2018</div>
          <blockquote>"Called 10 numbers and none of them answered."</blockquote>
          <p>The pattern repeats in every flood: the official line is busy.</p>
          <a href="https://caravanmagazine.in/vantage/how-social-media-was-vital-to-rescue-efforts-during-the-kerala-floods" target="_blank" rel="noreferrer">The Caravan, 6 Oct 2018 ↗</a>
        </article>
      </div>
      <p className="lp-overflow" data-reveal>
        <b>Pukaar is an overflow layer.</b> When every human call-taker is busy, the call does not ring out. Pukaar picks up, and the control room sees the caller on the map within seconds.
      </p>
    </section>
  );
}

function SeverityDemo() {
  const total = DRIVERS.reduce((s, [, v]) => s + v, 0);
  return (
    <div className="lp-sev" data-sev>
      <div className="lp-sev-head">
        <span className="lp-sev-badge">CRITICAL</span>
        <span className="lp-sev-total"><span data-count={total}>{total}</span><small>/100</small></span>
      </div>
      <div className="lp-sev-where">Velachery · 4 on the roof · grandmother needs insulin</div>
      <ul className="lp-sev-list">
        {DRIVERS.map(([k, v]) => (
          <li key={k}>
            <span>{k}</span>
            <span className="lp-sev-bar"><i style={{ "--w": v / 30 }} /></span>
            <b>+{v}</b>
          </li>
        ))}
      </ul>
      <div className="lp-sev-foot">Fixed rule table · critical ≥ 70 · high ≥ 45</div>
    </div>
  );
}

function Features() {
  return (
    <section id="features" className="lp-section">
      <div className="lp-head" data-reveal>
        <div className="lp-kicker">What it does</div>
        <h2>A calm voice on the line. A clear picture in the control room.</h2>
      </div>
      <div className="lp-rows">
        {FEATURES.map((f, i) => (
          <article className={`lp-row ${i % 2 ? "flip" : ""}`} key={f.title}>
            <div className="lp-row-copy" data-reveal>
              <div className="lp-kicker"><f.icon size={15} /> {f.kicker}</div>
              <h3>{f.title}</h3>
              <p>{f.body}</p>
              <ul className="lp-checks">{f.points.map((p) => <li key={p}><Check size={15} />{p}</li>)}</ul>
            </div>
            <div className="lp-row-media" data-reveal>
              {f.severity ? <SeverityDemo /> : <Shot name={f.img} alt={f.alt} />}
            </div>
          </article>
        ))}
      </div>
      <div className="lp-grid">
        {GRID.map((g) => (
          <article className={`lp-card ${g.tall ? "tall" : ""} ${g.interp ? "interp" : ""}`} key={g.title} data-reveal>
            <div className="lp-card-copy">
              <span className="lp-card-icon"><g.icon size={18} /></span>
              <h3>{g.title}</h3>
              <p>{g.body}</p>
            </div>
            {g.img && <div className="lp-card-img"><img src={`/landing/${g.img}.webp`} alt={g.alt} loading="lazy" decoding="async" width={g.tall ? 520 : 1280} height={g.tall ? 1125 : 800} /></div>}
            {g.interp && (
              <div className="lp-interp" aria-label="Example exchange">
                <div className="lp-bubble r"><small>Rescuer · Hindi</small><span lang="hi">हम नाव लेकर आ रहे हैं। आपके घर के पास कौन सी बड़ी इमारत है?</span></div>
                <div className="lp-bubble c"><small>Caller hears · Tamil</small><span lang="ta">நாம் படகை எடுத்து வந்து கொண்டிருக்கிறோம். உங்கள் வீட்டருகில் எந்த பெரிய கட்டிடம் உள்ளது?</span></div>
                <div className="lp-interp-note">Recorded live, 10 Nov · 2.3 s release to audio</div>
              </div>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}

// Pipeline diagram: nodes on a horizontal track (desktop) with a control-room branch
const NODES = [
  { id: "caller", x: 70, y: 120, t: "Caller", s: "flood · rain · 8 kHz" },
  { id: "prisma", x: 235, y: 120, t: "Gnani Prisma", s: "STT · indic-auto", g: true },
  { id: "facts", x: 400, y: 120, t: "Fact extraction", s: "LLM fills a form" },
  { id: "rules", x: 565, y: 120, t: "Rules", s: "severity 0–100" },
  { id: "guard", x: 730, y: 120, t: "Guard", s: "no false promises" },
  { id: "timbre", x: 895, y: 120, t: "Gnani Timbre", s: "TTS · same language", g: true },
  { id: "back", x: 1050, y: 120, t: "Caller hears", s: "one question at a time" },
];

function Pipeline() {
  return (
    <section id="how" className="lp-section">
      <div className="lp-head" data-reveal>
        <div className="lp-kicker">How it works</div>
        <h2>The AI fills in a form. The rules rank. A human decides.</h2>
        <p>Every reply passes the guard before Timbre speaks it. Every caller lands in the control room the moment a fact is known.</p>
      </div>
      <div className="lp-pipe" data-pipe data-reveal>
        <svg viewBox="0 0 1120 310" role="img" aria-label="Pipeline: caller to Gnani Prisma to fact extraction to rules to guard to Gnani Timbre back to the caller, with a branch from rules to the control room">
          <defs>
            <linearGradient id="lp-pipe-g" gradientUnits="userSpaceOnUse" x1="70" y1="0" x2="1050" y2="0">
              <stop offset="0" stopColor="#2dd4bf" /><stop offset="0.6" stopColor="#38bdf8" /><stop offset="1" stopColor="#f59e0b" />
            </linearGradient>
          </defs>
          <path className="lp-pipe-path main" d="M70 120 H1050" />
          <path className="lp-pipe-path branch" d="M582 136 C 650 176, 616 262, 712 262 H 890" />
          {NODES.map((n) => (
            <g key={n.id} transform={`translate(${n.x} ${n.y})`}>
              <g className={`lp-node ${n.g ? "gnani" : ""}`}>
                <circle r="22" />
                <circle className="core" r="6" />
                <text className="t" y="50" textAnchor="middle">{n.t}</text>
                <text className="s" y="68" textAnchor="middle">{n.s}</text>
              </g>
            </g>
          ))}
          <g transform="translate(960 262)">
            <g className="lp-node room">
              <rect x="-70" y="-26" width="204" height="52" rx="16" />
              <text className="t" x="32" y="-2" textAnchor="middle">Control room</text>
              <text className="s" x="32" y="15" textAnchor="middle">map · queue · human dispatch</text>
            </g>
          </g>
          <circle className="lp-pulse p1" r="5" />
          <circle className="lp-pulse p2" r="5" />
          <circle className="lp-pulse p3 amber" r="5" />
        </svg>
      </div>
      <ol className="lp-pipe-list" data-reveal>
        {NODES.map((n) => <li key={n.id} className={n.g ? "gnani" : ""}><b>{n.t}</b><span>{n.s}</span></li>)}
        <li className="room"><b>Control room</b><span>map · queue · a human confirms dispatch</span></li>
      </ol>
    </section>
  );
}

function fmt(v, dec = 0) { return dec ? v.toFixed(dec) : Math.round(v).toLocaleString("en-IN"); }

function Results() {
  return (
    <section id="results" className="lp-section">
      <div className="lp-head" data-reveal>
        <div className="lp-kicker">Measured, not promised</div>
        <h2>Numbers from live runs on Gnani's servers.</h2>
        <p>Small samples, conditions stated, all from the test log. Synthetic callers.</p>
      </div>
      <div className="lp-stats">
        {STATS.map((s) => (
          <div className="lp-stat" key={s.label} data-reveal>
            <div className="lp-stat-num">
              {s.from != null && <><span data-count={s.from} data-dec={s.dec || 0}>{fmt(s.from, s.dec)}</span><span className="dash">–</span></>}
              <span data-count={s.to} data-dec={s.dec || 0}>{fmt(s.to, s.dec)}</span>
              {s.unit && <small>{s.unit}</small>}
            </div>
            <div className="lp-stat-label">{s.label}</div>
            <div className="lp-stat-note">{s.note}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Compare() {
  return (
    <section className="lp-section">
      <div className="lp-head" data-reveal>
        <div className="lp-kicker">How it's different</div>
        <h2>Others help the call-taker. Pukaar answers the overflow call itself.</h2>
      </div>
      <div className="lp-compare">
        <article data-reveal>
          <h3>Bengaluru Namma 112 "VANKI"</h3><small>Apr 2026</small>
          <p>Live translation for human call-takers, 10+ languages.</p>
          <a href="https://www.devdiscourse.com/article/technology/3890691-bengaluru-police-launch-multilingual-ai-capability-in-112-emergency-response-system" target="_blank" rel="noreferrer">Source ↗</a>
        </article>
        <article data-reveal>
          <h3>Telangana AI-ERSS</h3><small>Aug 2026</small>
          <p>Assists call-takers, with severity ranking and duplicate filtering.</p>
          <a href="https://www.siasat.com/telangana-police-launches-ai-enabled-emergency-response-system-3519196/" target="_blank" rel="noreferrer">Source ↗</a>
        </article>
        <article className="us" data-reveal>
          <h3>Pukaar</h3><small>overflow voice agent</small>
          <p>Answers the call itself in code-mixed Indian languages, triages with explainable rules, guards against false reassurance, and emits CAP 1.2 alerts.</p>
          <span className="lp-tag">A human still confirms every dispatch</span>
        </article>
      </div>
      <p className="lp-note" data-reveal>
        To our knowledge, as of November 2026, the Indian AI deployments in emergency calls we found assist human call-takers. We found no public deployment of an AI voice agent that itself answers overflow disaster calls in code-mixed Tamil, Hindi and English with explainable triage.
      </p>
    </section>
  );
}

function Family() {
  return (
    <section className="lp-section">
      <div className="lp-head" data-reveal>
        <div className="lp-kicker">One engine, three products</div>
        <h2>Built on one shared Gnani voice engine.</h2>
        <p><code>voice-core</code>: streaming STT, barge-in, an echo guard, a request gate with 429 retries, reconnect backoff and a TTS stall timeout.</p>
      </div>
      <div className="lp-family">
        <div className="lp-prod" data-reveal>
          <b>Dadi vs Scammers</b><span>An AI grandmother answers scam calls, wastes the scammer's time and extracts mule accounts into a complaint.</span>
          <div className="lp-prod-links"><a href={DADI_URL} target="_blank" rel="noreferrer">Live demo ↗</a><a href={DADI_REPO} target="_blank" rel="noreferrer">GitHub ↗</a></div>
        </div>
        <div className="lp-prod on" data-reveal>
          <b>Pukaar</b><span>The overflow line for floods: every caller answered, triaged and on the map.</span>
          <div className="lp-prod-links"><em>You are here</em><a href={REPO_URL} target="_blank" rel="noreferrer">GitHub ↗</a></div>
        </div>
        <div className="lp-prod" data-reveal>
          <b>Apni Awaaz</b><span>Gives people who lost their voice their own voice back, from old voice notes, in 10 Indian languages.</span>
          <div className="lp-prod-links"><a href={AWAAZ_URL} target="_blank" rel="noreferrer">Live demo ↗</a><a href={AWAAZ_REPO} target="_blank" rel="noreferrer">GitHub ↗</a></div>
        </div>
      </div>
    </section>
  );
}

function Closing() {
  return (
    <section className="lp-section lp-closing" data-reveal>
      <Logo size={64} />
      <h2>See a flood night in the control room.</h2>
      <p>The demo replays a real run recorded on Gnani's live servers on 10 Nov 2026. Play the recorded Tamil call, open an incident and see exactly why it ranks where it does.</p>
      <div className="lp-ctas center">
        <a className="lp-btn" href={APP_HREF}><PhoneIncoming size={18} /> Open the live control room</a>
        <a className="lp-btn lp-btn-ghost" href={REPO_URL} target="_blank" rel="noreferrer"><Github size={18} /> Read the code</a>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="lp-foot">
      <div className="lp-foot-row">
        <a className="lp-brand" href="#/"><Logo size={26} /><b>Pukaar</b></a>
        <span className="lp-team">Built by <b>Nitya Prakash Pandey</b> · <b>Dilavesh Kanz Nidooli</b></span>
        <a href={REPO_URL} target="_blank" rel="noreferrer" className="lp-foot-gh"><Github size={16} /> GitHub</a>
      </div>
      <p className="lp-foot-note">
        Demo note: every caller, voice and incident here is synthetic. No real emergency data. Phone location is simulated. Built on Gnani AI: Prisma v3.0 (STT) and Timbre v3.0 (TTS).
      </p>
      <p className="lp-tags">#GnaniAI · #GreatIndianAIInternshipChallenge</p>
    </footer>
  );
}

function useLandingMotion(root) {
  useEffect(() => {
    const el = root.current;
    if (!el) return;
    const html = document.documentElement;
    if (reduceMotion()) return; // everything renders in its final state
    html.classList.add("lp-js");
    const anims = [];

    // hero entrance
    const tl = createTimeline({ defaults: { ease: "outExpo", duration: 900 } });
    tl.add(el.querySelectorAll(".lp-word > span"), { translateY: ["110%", "0%"], opacity: [0, 1], delay: stagger(70) })
      .add(el.querySelectorAll("[data-hero]"), { translateY: [18, 0], opacity: [0, 1], delay: stagger(90) }, "-=650")
      .add(el.querySelector(".lp-float"), { translateY: [40, 0], opacity: [0, 1], duration: 1200 }, "-=900")
      .add(el.querySelectorAll(".lp-float-card"), { scale: [0.85, 1], opacity: [0, 1], delay: stagger(160) }, "-=700");
    anims.push(tl);

    // ambient loops: waves, ripples, floating shot
    el.querySelectorAll(".lp-wave").forEach((w, i) => {
      anims.push(animate(w, { translateX: ["0%", "-50%"], duration: 16000 + i * 6000, ease: "linear", loop: true }));
    });
    anims.push(animate(el.querySelectorAll(".lp-ripple > span"), { scale: [0.4, 2.3], opacity: [0.55, 0], duration: 3000, delay: stagger(1000), loop: true, ease: "outSine" }));
    anims.push(animate(el.querySelector(".lp-hero-shot"), { translateY: [-6, 6], duration: 4200, alternate: true, loop: true, ease: "inOutSine" }));

    // pipeline: draw paths, then send pulses along them
    let pipeStarted = false;
    const startPipe = () => {
      if (pipeStarted) return;
      pipeStarted = true;
      const main = el.querySelector(".lp-pipe-path.main");
      const branch = el.querySelector(".lp-pipe-path.branch");
      if (!main || !branch) return;
      anims.push(animate(svg.createDrawable([main, branch]), { draw: ["0 0", "0 1"], duration: 1600, ease: "inOutQuad", delay: stagger(500) }));
      anims.push(animate(el.querySelectorAll(".lp-node"), { opacity: [0, 1], scale: [0.6, 1], delay: stagger(110), duration: 700, ease: "outBack" }));
      const mp = svg.createMotionPath(main);
      const bp = svg.createMotionPath(branch);
      anims.push(animate(el.querySelector(".lp-pulse.p1"), { ...mp, opacity: [0, 1, 1, 0], duration: 4200, loop: true, ease: "linear", delay: 1400 }));
      anims.push(animate(el.querySelector(".lp-pulse.p2"), { ...mp, opacity: [0, 1, 1, 0], duration: 4200, loop: true, ease: "linear", delay: 3500 }));
      anims.push(animate(el.querySelector(".lp-pulse.p3"), { ...bp, opacity: [0, 1, 1, 0], duration: 2600, loop: true, ease: "inOutSine", delay: 2400 }));
    };

    const countUp = (node) => {
      const to = parseFloat(node.dataset.count);
      const dec = parseInt(node.dataset.dec || "0", 10);
      const o = { v: 0 };
      node.textContent = fmt(0, dec);
      anims.push(animate(o, { v: to, duration: 1600, ease: "outExpo", onUpdate: () => { node.textContent = fmt(o.v, dec); } }));
    };

    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (!e.isIntersecting) return;
        const t = e.target;
        io.unobserve(t);
        anims.push(animate(t, { translateY: [28, 0], opacity: [0, 1], duration: 900, ease: "outExpo" }));
        t.querySelectorAll("[data-count]").forEach(countUp);
        const bars = t.querySelectorAll(".lp-sev-bar i");
        if (bars.length) anims.push(animate(bars, { scaleX: [0, (_, i) => parseFloat(bars[i].style.getPropertyValue("--w"))], delay: stagger(140, { start: 250 }), duration: 900, ease: "outExpo" }));
        if (t.matches("[data-pipe]")) startPipe();
      });
    }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
    el.querySelectorAll("[data-reveal]").forEach((n) => io.observe(n));

    return () => {
      io.disconnect();
      anims.forEach((a) => a?.revert?.());
      html.classList.remove("lp-js");
    };
  }, [root]);
}

export default function Landing() {
  const root = useRef(null);
  useLandingMotion(root);
  useEffect(() => {
    const prev = document.title;
    document.title = "Pukaar · When every line is busy, Pukaar picks up";
    window.scrollTo(0, 0);
    return () => { document.title = prev; };
  }, []);
  return (
    <div className="lp" ref={root}>
      <a className="lp-skip" href={APP_HREF}>Skip to the control room</a>
      <Nav />
      <main>
        <Hero />
        <Problem />
        <Features />
        <Pipeline />
        <Results />
        <Compare />
        <Family />
        <Closing />
      </main>
      <Footer />
    </div>
  );
}
