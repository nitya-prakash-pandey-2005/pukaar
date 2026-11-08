// Caller-phone state machine: WebSocket + mic + player, plus the caller's own incident and missed callbacks.
import { useCallback, useEffect, useRef, useState } from "react";
import { createPcmPlayer, startMic } from "@voice/index.js";
import { openCall } from "../net/callSocket";
import { getJSON } from "../lib/api";
import { toast } from "../ui";

const RATE = 8000; // phone-quality audio both ways (Prisma is trained on 8 kHz calls)

export function useCall() {
  const [phase, setPhase] = useState("idle"); // idle | connecting | live | ending | ended
  const [callId, setCallId] = useState(null);
  const [turns, setTurns] = useState([]);
  const [incident, setIncident] = useState(null);
  const [language, setLanguage] = useState(null);
  const [stt, setStt] = useState("idle");
  const [speaking, setSpeaking] = useState(false);
  const [startedAt, setStartedAt] = useState(null);
  const [seconds, setSeconds] = useState(0);
  const [callbacks, setCallbacks] = useState([]);
  const refs = useRef({ call: null, mic: null, player: null });

  const stopMic = () => {
    refs.current.mic?.stop();
    refs.current.mic = null;
  };

  const onEvent = useCallback((m) => {
    switch (m.type) {
      case "session_started":
        setCallId(m.call_id);
        setStartedAt(Date.now());
        setPhase("live");
        break;
      case "turn":
        setTurns((t) => [...t, m]);
        break;
      case "agent_speaking":
        setSpeaking(!!m.on);
        break;
      case "stop_audio":
        refs.current.player?.flush();
        setSpeaking(false);
        break;
      case "status":
        setStt(m.stt);
        if (m.stt === "error" && m.message) toast(m.message, "warn");
        break;
      case "incident":
        setIncident(m.incident);
        break;
      case "language":
        setLanguage(m.language_name || m.language);
        break;
      case "call_ended":
        setSeconds(m.seconds || 0);
        setPhase("ended");
        setSpeaking(false);
        stopMic();
        break;
      default:
        break;
    }
  }, []);

  const start = useCallback(async (gps, noiseDb = null) => {
    if (refs.current.call) return;
    setTurns([]);
    setIncident(null);
    setLanguage(null);
    setCallbacks([]);
    setSeconds(0);
    setCallId(null);
    setSpeaking(false);
    setStt("connecting");
    setPhase("connecting");
    refs.current.player?.close();
    const player = createPcmPlayer({ sampleRate: RATE }); // created inside the click, so audio is allowed
    refs.current.player = player;
    const t0 = Date.now();
    refs.current.call = openCall({
      gps,
      noiseSnrDb: noiseDb,
      onEvent,
      onAudio: (ab) => player.play(ab),
      onClose: () => {
        refs.current.call = null;
        stopMic();
        setStt("idle");
        setSpeaking(false);
        setPhase((p) => {
          if (p !== "ended") setSeconds((s) => s || (Date.now() - t0) / 1000);
          return "ended";
        });
      },
    });
    try {
      refs.current.mic = await startMic({ targetRate: RATE, onFrame: (ab) => refs.current.call?.sendAudio(ab) });
    } catch (e) {
      toast(`Microphone unavailable: ${e?.message || e}`, "warn");
    }
  }, [onEvent]);

  const hangup = useCallback(() => {
    stopMic();
    if (refs.current.call) {
      refs.current.call.hangup();
      setPhase("ending");
    }
  }, []);

  // after hanging up, check for a dispatcher's callback ("missed callback" banner)
  useEffect(() => {
    if (phase !== "ended" || !callId) return undefined;
    const poll = () => getJSON(`/api/calls/${callId}/callbacks`).then(setCallbacks).catch(() => {});
    poll();
    const id = setInterval(poll, 4000);
    return () => clearInterval(id);
  }, [phase, callId]);

  const setNoise = useCallback((db) => refs.current.call?.setNoise(db), []);
  const playerLevel = useCallback(() => refs.current.player?.level() ?? 0, []);

  useEffect(() => () => {
    refs.current.call?.close();
    stopMic();
    refs.current.player?.close();
  }, []);

  return { phase, callId, turns, incident, language, stt, speaking, startedAt, seconds, callbacks,
           start, hangup, setNoise, playerLevel };
}

export function useNow(active, every = 250) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return undefined;
    const id = setInterval(() => setNow(Date.now()), every);
    return () => clearInterval(id);
  }, [active, every]);
  return now;
}
