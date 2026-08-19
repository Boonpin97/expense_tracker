import * as React from "react";

const MOBILE_BREAKPOINT = 768;

function readIsMobile() {
  if (typeof window === "undefined") return false;
  return window.innerWidth < MOBILE_BREAKPOINT;
}

export function useIsMobile() {
  // Seeded synchronously so the first paint is already the right tree. Reading
  // window during render is safe here: this is a client-only SPA (main.tsx uses
  // createRoot), so there is no SSR pass to mismatch against. Initialising to
  // undefined would render the desktop layout for one frame on every phone.
  const [isMobile, setIsMobile] = React.useState(readIsMobile);

  React.useEffect(() => {
    const mql = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT - 1}px)`);
    const onChange = () => {
      setIsMobile(readIsMobile());
    };
    mql.addEventListener("change", onChange);
    // Re-sync in case the viewport changed between render and effect.
    setIsMobile(readIsMobile());
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return isMobile;
}
