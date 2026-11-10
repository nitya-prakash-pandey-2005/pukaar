import { useEffect, useState } from "react";
import { ExternalLink, History, PhoneCall, Radar } from "lucide-react";
import { useRoute } from "./lib/router";
import AppShell from "./shell/AppShell";
import { Badge, PageHead, Toasts } from "./ui";
import { useApi } from "./lib/api";
import { useCall } from "./state/useCall";
import { useControl } from "./state/useControl";
import CallerPhone from "./components/CallerPhone";
import ControlRoom from "./components/ControlRoom";
import { DEMO, REPO_URL } from "./demo/demo";

const NAV = [{ group: "Helpline", items: [{ to: "/app", label: "Live helpline", short: "Live", icon: PhoneCall, exact: true }] }];
const TITLES = [["/app", "Pukaar control room", "Flood night in Chennai · Gnani Prisma + Timbre"]];

function HealthPill({ health }) {
  if (DEMO) return <Badge tone="cyan" dot>Recorded run · 10 Nov</Badge>;
  if (!health) return <Badge tone="muted" dot>Server offline</Badge>;
  if (health.fake) return <Badge tone="amber" dot>Fake mode: no API keys</Badge>;
  if (!health.gnani_key || !health.llm_key) return <Badge tone="rose" dot>API keys missing</Badge>;
  if (!health.fillers_ready) return <Badge tone="cyan" dot>Warming up voices…</Badge>;
  return <Badge tone="green" dot>Gnani live · {health.llm_provider}</Badge>;
}

// Static demo only: says plainly what the visitor is looking at, and where the live version is
function DemoBanner() {
  return (
    <div className="demo-banner" role="note">
      <History size={16} className="flex-none" />
      <span>
        <b>Interactive demo:</b> replays a real run recorded on Gnani's live servers on 10 Nov 2026 (synthetic callers).
        Run it locally with your own keys for live calls.
      </span>
      <a href={REPO_URL} target="_blank" rel="noreferrer">GitHub <ExternalLink size={13} /></a>
    </div>
  );
}

export default function App() {
  const route = useRoute();
  useEffect(() => { if (route.path === "/" || route.path === "") window.location.hash = "/app"; }, [route.path]);

  const { data: health, reload: reloadHealth } = useApi("/api/health");
  const { data: places, reload: reloadPlaces } = useApi("/api/places");
  const { data: guidance, reload: reloadGuidance } = useApi("/api/guidance");
  // the pill follows the server: "Warming up voices…" turns green, and an outage or restart shows up
  useEffect(() => {
    const id = setInterval(reloadHealth, 5000);
    return () => clearInterval(id);
  }, [reloadHealth]);
  // page opened before the server was up: fetch the places and guidance once it answers
  useEffect(() => {
    if (health && !places) reloadPlaces();
    if (health && !guidance) reloadGuidance();
  }, [health]); // eslint-disable-line react-hooks/exhaustive-deps
  const call = useCall();
  const control = useControl();
  const [placeName, setPlaceName] = useState("Velachery");
  const [noise, setNoise] = useState("off");
  const [tab, setTab] = useState("phone"); // only used under 900px

  return (
    <>
      <AppShell
        path={route.path}
        brand={{ name: "Pukaar", sub: "AI disaster helpline", logo: "/icons/icon.svg", href: "#/app" }}
        nav={NAV}
        titles={TITLES}
        topRight={<HealthPill health={health} />}
        footer={<div className="pill-src">Built on Gnani AI: Prisma v3.0 (STT) · Timbre v3.0 (TTS) · Evon v3.3 (LLM, when hosted)</div>}
      >
        {DEMO && <DemoBanner />}
        <PageHead
          kicker="Pukaar · पुकार"
          title="Every flood call answered, in the caller's language."
          sub="An overflow helpline on Gnani Prisma and Timbre. It keeps callers calm, gives only approved safety advice, scores severity with transparent rules and puts every caller on the rescue map. A human confirms every dispatch."
        />
        <div className="tabs-line callroom-tabs" role="tablist">
          <button className={tab === "phone" ? "on" : ""} onClick={() => setTab("phone")}><PhoneCall size={15} /> Call</button>
          <button className={tab === "control" ? "on" : ""} onClick={() => setTab("control")}><Radar size={15} /> Control room</button>
        </div>
        <div className="callroom">
          <div className="phone-col" data-hidden={tab !== "phone"}>
            <CallerPhone call={call} places={places || []} placeName={placeName} setPlaceName={setPlaceName} noise={noise} setNoise={setNoise} />
          </div>
          <div className="war-col" data-hidden={tab !== "control"}>
            <ControlRoom control={control} guidance={guidance || []} />
          </div>
        </div>
      </AppShell>
      <Toasts />
    </>
  );
}
