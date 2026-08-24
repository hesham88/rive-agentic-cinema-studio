'use client';

import { useEffect, useRef, useState } from 'react';
import { Fit, Layout, useRive } from '@rive-app/react-webgl2';

/**
 * The hero stage: the scene playing full-bleed, with the shot list read over it
 * as a heads-up display.
 *
 * The scene is the backdrop rather than a framed thumbnail because that is what
 * makes the glass above it honest — `backdrop-filter` is sampling a live
 * animation, so the panels genuinely refract moving content instead of blurring
 * a flat gradient.
 *
 * The frame numbers are not illustrative. They are the keyframes the camera
 * engine emitted for `CameraMove`: a 2.2x push-in landing at 110, a 26-frame
 * shake, a follow to 216, and a canted wide at 286. The HUD is the data
 * structure, drawn.
 */

export interface Shot {
  name: string;
  /** Frame this shot begins on, from the emitted keyframes. */
  frame: number;
  note: string;
}

/** Straight from tools/genassets — the shot list that produced scene.riv. */
export const SHOTS: Shot[] = [
  { name: 'open', frame: 0, note: 'wide, locked off' },
  { name: 'push in', frame: 110, note: 'dolly to 2.2x' },
  { name: 'shake', frame: 136, note: 'liftoff, seeded jitter' },
  { name: 'follow', frame: 216, note: 'track up, ease to 1.6x' },
  { name: 'canted', frame: 286, note: 'roll 6 degrees, settle' },
];

const TOTAL = SHOTS[SHOTS.length - 1]!.frame;
const FPS = 60;

export function HeroStage() {
  const [frame, setFrame] = useState(0);
  const [failed, setFailed] = useState(false);
  const startedAt = useRef(0);

  const { rive, RiveComponent } = useRive({
    src: '/riv/scene.riv',
    artboard: 'Scene',
    animations: 'CameraMove',
    autoplay: true,
    // Cover, because this is a backdrop: letterbox bars behind a glass panel
    // would expose the seam and give the blur nothing to sample at the edges.
    layout: new Layout({ fit: Fit.Cover }),
    onLoadError: () => setFailed(true),
  });

  // Drive the playhead from wall-clock time rather than polling Rive: the
  // runtime does not expose a frame cursor, and a rAF clock stays in step with
  // a looping timeline without reaching into internals.
  useEffect(() => {
    if (!rive) return;
    startedAt.current = performance.now();
    let raf = 0;
    const tick = () => {
      const elapsed = (performance.now() - startedAt.current) / 1000;
      setFrame(Math.floor((elapsed * FPS) % (TOTAL + 1)));
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [rive]);

  const active = SHOTS.reduce((acc, s, i) => (frame >= s.frame ? i : acc), 0);

  return (
    <div className="absolute inset-0 z-0" aria-hidden={!failed}>
      {failed ? (
        <div className="flex h-full items-center justify-center px-6 text-center">
          <p className="text-sm text-slate">
            The scene didn&rsquo;t load. It lives at{' '}
            <code className="num text-flame">/riv/scene.riv</code>.
          </p>
        </div>
      ) : (
        <RiveComponent className="h-full w-full" />
      )}

      {/* Scrim. The headline sits over a moving image, so legibility cannot be
          left to chance — dark at the left and bottom where type lands. */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            'linear-gradient(100deg, var(--color-void) 6%, color-mix(in srgb, var(--color-void) 72%, transparent) 42%, transparent 78%),' +
            'linear-gradient(to top, var(--color-void) 2%, transparent 38%)',
        }}
      />

      {/* The HUD. Ticks sit at their true proportional frame. */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 z-10 px-6 pb-6">
        <div className="glass pointer-events-auto mx-auto max-w-6xl p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <p className="eyebrow">Camera move · CameraMove</p>
            <p className="num text-[11px] text-slate/70">
              frame <span className="text-flame">{String(frame).padStart(3, '0')}</span>
              <span className="text-slate/40"> / {TOTAL}</span>
            </p>
          </div>

          <div className="relative mt-4 h-px w-full bg-white/15">
            <div
              className="playhead absolute top-0 h-px bg-ignite"
              style={{ width: `${(frame / TOTAL) * 100}%` }}
            />
            {SHOTS.map((s, i) => (
              <span
                key={s.name}
                aria-hidden
                className={
                  'absolute top-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rotate-45 border transition-colors duration-300 ' +
                  (i <= active ? 'border-ignite bg-ignite' : 'border-white/30 bg-void')
                }
                style={{ left: `${(s.frame / TOTAL) * 100}%` }}
              />
            ))}
          </div>

          <ol className="mt-4 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-5">
            {SHOTS.map((s, i) => (
              <li key={s.name} className="min-w-0">
                <div
                  className={
                    'num text-xs transition-colors duration-300 ' +
                    (i === active ? 'text-flame' : 'text-slate')
                  }
                >
                  {String(s.frame).padStart(3, '0')}
                </div>
                <div
                  className={
                    'mt-0.5 truncate text-sm font-medium transition-colors duration-300 ' +
                    (i === active ? 'text-paper' : 'text-slate')
                  }
                >
                  {s.name}
                </div>
                <div className="mt-0.5 truncate text-xs leading-snug text-slate/70">
                  {s.note}
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}
