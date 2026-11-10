import { lazy, Suspense, useEffect } from "react";
import { useRoute } from "../lib/router";
import Landing from "./Landing";
import { useAppMotion } from "../motion/useAppMotion";

// The product site lives at "#/" (or no hash); every app route ("#/app", "#/interpret", ...) renders the app unchanged.
// The app is loaded on demand so the landing page paints fast.
const App = lazy(() => import("../App"));

function AppWithMotion() {
  useAppMotion();
  return <App />;
}

export default function Root() {
  const route = useRoute();
  const landing = route.path === "/" || route.path === "";
  useEffect(() => { document.documentElement.classList.toggle("is-landing", landing); }, [landing]);
  if (landing) return <Landing />;
  return (
    <Suspense fallback={<div className="app-boot" aria-busy="true"><img src="/icons/icon.svg" width="44" height="44" alt="" /></div>}>
      <AppWithMotion />
    </Suspense>
  );
}
