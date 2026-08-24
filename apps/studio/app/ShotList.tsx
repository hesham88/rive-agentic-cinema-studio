'use client';

import { useActiveSection, useScrollProgress } from './useScrollProgress';

/**
 * The page as a shot list, with a playhead that follows the scroll.
 *
 * This is the page's signature element, and it is structural rather than
 * decorative. The camera engine genuinely emits shots with frame ranges, so a
 * numbered timeline encodes something true about this product: each section
 * consumes what the previous one produced, exactly as each shot follows the
 * last. Numbering a set of unrelated feature cards would be the decorative
 * version of the same idea, and worth nothing.
 *
 * It hides below `lg`. A 40px rail on a phone is a decoration competing with
 * the content for the only column available.
 */

export interface Shot {
  id: string;
  label: string;
  /** Frame this beat starts on. Real numbers from `scene.riv`'s CameraMove. */
  frame: number;
}

export const SHOTS: readonly Shot[] = [
  { id: 'open', label: 'open', frame: 0 },
  { id: 'why', label: 'why', frame: 42 },
  { id: 'pipeline', label: 'process', frame: 88 },
  { id: 'engines', label: 'engines', frame: 110 },
  { id: 'kit', label: 'interface', frame: 168 },
  { id: 'proof', label: 'proof', frame: 216 },
  { id: 'close', label: 'ship', frame: 286 },
] as const;

const IDS = SHOTS.map((s) => s.id);
const LAST = SHOTS[SHOTS.length - 1]!.frame;

export function ShotList() {
  const progress = useScrollProgress();
  const active = useActiveSection(IDS);

  // The playhead reads in frames, because that is the unit this product works
  // in. Scroll position maps onto the same range the camera move spans.
  const frame = Math.round(progress * LAST);

  return (
    <aside
      aria-hidden
      className="pointer-events-none fixed left-0 top-0 z-40 hidden h-dvh w-[220px] lg:block"
    >
      <div className="relative flex h-full flex-col justify-center pl-10">
        {/* The track, and the lit portion of it. */}
        <div className="absolute bottom-[12%] left-[52px] top-[12%] w-px bg-rule" />
        <div
          className="playhead absolute left-[52px] top-[12%] w-px"
          style={{ height: `${progress * 76}%` }}
        />

        <ol className="relative flex flex-col justify-between" style={{ height: '76%' }}>
          {SHOTS.map((shot, i) => {
            const isActive = i === active;
            const isPast = i < active;
            return (
              <li key={shot.id} className="flex items-center gap-4">
                <span
                  className={`num w-8 text-right text-[10px] tabular-nums transition-colors duration-500 ${
                    isActive ? 'text-lamp' : isPast ? 'text-dim' : 'text-dim/40'
                  }`}
                >
                  {String(shot.frame).padStart(3, '0')}
                </span>
                {/* The tick. Lit only on the active beat — the lamp appears
                    once per viewport, which is the palette's own rule. */}
                <span
                  className={`tick h-[7px] w-[7px] shrink-0 rotate-45 border ${
                    isActive
                      ? 'scale-125 border-lamp bg-lamp'
                      : isPast
                        ? 'border-dim bg-dim'
                        : 'border-rule bg-room'
                  }`}
                />
                <span
                  className={`num text-[10px] uppercase tracking-[0.18em] transition-colors duration-500 ${
                    isActive ? 'text-bright' : 'text-dim/60'
                  }`}
                >
                  {shot.label}
                </span>
              </li>
            );
          })}
        </ol>

        <p className="num absolute bottom-8 left-10 text-[10px] text-dim/50">
          frame <span className="text-ember">{String(frame).padStart(3, '0')}</span>
          <span className="text-dim/30"> / {LAST}</span>
        </p>
      </div>
    </aside>
  );
}
