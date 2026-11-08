import { useEffect, useState } from "react";

const read = () => {
  const raw = window.location.hash.replace(/^#/, "") || "/";
  const [path, qs] = raw.split("?");
  return { path: path || "/", parts: path.split("/").filter(Boolean), query: Object.fromEntries(new URLSearchParams(qs || "")) };
};

export function useRoute() {
  const [r, setR] = useState(read);
  useEffect(() => {
    const on = () => setR(read());
    window.addEventListener("hashchange", on);
    return () => window.removeEventListener("hashchange", on);
  }, []);
  return r;
}

export function navigate(path) {
  if (window.location.hash !== `#${path}`) window.location.hash = path;
}

export const currentPath = () => read().path;
