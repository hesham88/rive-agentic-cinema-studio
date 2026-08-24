'use client';

import { useReveal } from './useReveal';

/**
 * The pipeline, told in its own real numbers.
 *
 * These are measurements from the run that produced paper-plane.riv, not an
 * illustration of a process. The steps are numbered because they genuinely are
 * a sequence — each one consumes the previous one's output — which is the only
 * case where numbering earns its place.
 */
const PIPELINE = [
  {
    step: 'brief',
    value: '1',
    unit: 'sentence',
    detail: 'A prompt, in plain language.',
  },
  {
    step: 'research',
    value: '10',
    unit: 'sources',
    detail:
      'Parallel searches how the subject is really drawn, before anything is generated.',
  },
  {
    step: 'render',
    value: '86',
    unit: 'KB raster',
    detail: 'Gemini draws it. The result is a picture — flat, and not yet animatable.',
  },
  {
    step: 'trace',
    value: '252',
    unit: 'commands',
    detail: 'Vectorised into paths. Now it has geometry instead of pixels.',
  },
  {
    step: 'simplify',
    value: '41',
    unit: 'commands',
    detail: 'Tracer noise removed. Every vertex left is one a human could drag.',
  },
  {
    step: 'ship',
    value: '868',
    unit: 'bytes',
    detail: 'Rigged, keyframed, exported. A hundredth the size, and alive.',
  },
];

function Step({ s, i }: { s: (typeof PIPELINE)[number]; i: number }) {
  // Staggered by index so the row assembles left to right rather than snapping
  // in as a block.
  const ref = useReveal<HTMLLIElement>(i * 70);
  return (
    <li ref={ref} className="reveal glass-thin p-5">
      <div className="flex items-baseline justify-between gap-4">
        <span className="eyebrow">{s.step}</span>
        <span className="num text-xs text-slate/50">{String(i + 1).padStart(2, '0')}</span>
      </div>
      <p className="mt-3 flex items-baseline gap-2">
        <span className="num text-3xl font-medium text-paper">{s.value}</span>
        <span className="text-xs text-slate">{s.unit}</span>
      </p>
      <p className="mt-2 text-sm leading-relaxed text-slate">{s.detail}</p>
    </li>
  );
}

export function Pipeline() {
  const head = useReveal<HTMLDivElement>();

  return (
    <section id="pipeline" className="relative border-t border-white/8">
      <div className="relative z-10 mx-auto max-w-6xl px-6 py-24">
        <div ref={head} className="reveal">
          <p className="eyebrow">One run, measured</p>
          <h2 className="display mt-3 max-w-2xl text-[clamp(1.75rem,3.5vw,2.5rem)]">
            Six steps from prompt to shipped asset.
          </h2>
          <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-slate">
            These are the actual figures from the run that produced the paper plane — not
            an illustration of the process.
          </p>
        </div>

        <ol className="mt-12 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {PIPELINE.map((s, i) => (
            <Step key={s.step} s={s} i={i} />
          ))}
        </ol>

        <p className="num mt-10 border-t border-white/10 pt-5 text-sm text-slate">
          86 KB raster <span className="text-slate/40">→</span>{' '}
          <span className="text-flame">868 B vector</span>
          <span className="ml-3 font-sans text-xs text-slate/70">
            a hundredth the size, infinitely scalable, and animatable
          </span>
        </p>
      </div>
    </section>
  );
}
