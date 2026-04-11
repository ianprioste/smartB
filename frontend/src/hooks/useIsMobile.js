import { useEffect, useState } from 'react';

function isMobileUserAgent() {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent || navigator.vendor || '';
  return /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini|Mobile|Silk/i.test(ua);
}

function computeIsMobile(breakpoint = 768) {
  if (typeof window === 'undefined') return false;

  const viewportMatch = window.matchMedia
    ? window.matchMedia(`(max-width: ${breakpoint}px)`).matches
    : window.innerWidth <= breakpoint;

  const coarsePointer = window.matchMedia
    ? window.matchMedia('(pointer: coarse)').matches
    : false;

  return viewportMatch || (coarsePointer && isMobileUserAgent());
}

export default function useIsMobile(breakpoint = 768) {
  const [isMobile, setIsMobile] = useState(() => computeIsMobile(breakpoint));

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const viewportQuery = window.matchMedia(`(max-width: ${breakpoint}px)`);
    const coarseQuery = window.matchMedia('(pointer: coarse)');
    const update = () => setIsMobile(computeIsMobile(breakpoint));

    update();

    if (viewportQuery.addEventListener) {
      viewportQuery.addEventListener('change', update);
      coarseQuery.addEventListener('change', update);
    } else {
      viewportQuery.addListener(update);
      coarseQuery.addListener(update);
    }

    window.addEventListener('resize', update, { passive: true });
    window.addEventListener('orientationchange', update, { passive: true });

    return () => {
      if (viewportQuery.removeEventListener) {
        viewportQuery.removeEventListener('change', update);
        coarseQuery.removeEventListener('change', update);
      } else {
        viewportQuery.removeListener(update);
        coarseQuery.removeListener(update);
      }

      window.removeEventListener('resize', update);
      window.removeEventListener('orientationchange', update);
    };
  }, [breakpoint]);

  return isMobile;
}
