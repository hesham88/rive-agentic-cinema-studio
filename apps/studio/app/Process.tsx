'use client';

import { useReveal } from './useScrollProgress';

/**
 * The pipeline, in its own measurements.
 *
 * These are the figures from the run that produced `paper-plane.riv`, not an
 * illustration of a process. The numbers are the argument: 86 KB of raster
 * becomes 868 bytes of vector, a hundredth the size and infinitely scalable,
 * and every step is a real artefact on disk.
 *
 * Numbered because it genuinely is a sequence — each step consumes the previous
 * one's output. That is the only case where numbering earns its place.
 */

const STEPS = [
  {
    n: '01',
    step: 'brief',
    value: '1',
    unit: 'sentence',
    detail: 'A prompt, in plain language. Nothing else is required.',
  },
  {
    n: '02',
    step: 'research',
    value: '5',
    unit: 'cited sources',
    detail:
      'Parallel finds how the subject is really drawn and returns a structured brief — ' +
      'palette, silhouette, conventions — with the source of every field.',
  },
  {
    n: '03',
    step: 'render',
    value: '86',
    unit: 'KB raster',
    detail: 'Gemini draws it from the researched direction. Still a picture, not yet animatable.',
  },
  {
    n: '04',
    step: 'trace',
    value: '252',
    unit: 'path commands',
    detail: 'Vectorised. It has geometry now instead of pixels.',
  },
  {
    n: '05',
    step: 'simplify',
    value: '41',
    unit: 'path commands',
    detail: 'Tracer noise removed. Every vertex left is one a human could drag.',
  },
  {
    n: '06',
    step: 'ship',
    value: '868',
    unit: 'bytes',
    detail: 'Rigged, keyframed, exported. A hundredth the size, and alive.',
  },
] as const;

function Step({ s, i }: { s: (typeof STEPS)[number]; i: number }) {
  // Staggered so the column assembles top-down rather than snapping in as a
  // block — overlapping action, applied to a layout.
  const ref = useReveal<HTMLLIElement>(i * 70);
  return (
    <li ref={ref} className="reveal group rule-t py-7">
      <div className="grid gap-4 sm:grid-cols-[3rem_1fr_auto] sm:items-baseline">
        <span className="num text-[11px] text-dim/50">{s.n}</span>
        <div className="min-w-0">
          <p className="eyebrow">{s.step}</p>
          <p className="mt-2 max-w-[52ch] text-[15px] leading-relaxed text-read">{s.detail}</p>
        </div>
        <p className="flex items-baseline gap-2 sm:justify-end">
          <span className="num text-[28px] font-medium text-bright">{s.value}</span>
          <span className="num text-[11px] text-dim">{s.unit}</span>
        </p>
      </div>
    </li>
  );
}

export function Process() {
  const head = useReveal<HTMLDivElement>();
  const foot = useReveal<HTMLParagraphElement>(120);

  return (
    <section id="pipeline" className="relative">
      <div className="mx-auto max-w-[1400px] px-6 py-28 lg:pl-[224px]">
        <div ref={head} className="reveal max-w-[54ch]">
          <p className="eyebrow">One run, measured</p>
          <h2 className="display mt-4 text-[clamp(2rem,4.5vw,3.25rem)]">
            Six steps from a prompt to a <em>shipped asset.</em>
          </h2>
          <p className="mt-5 text-[15px] leading-relaxed text-read">
            Nothing here is generated before it is researched. The figures below are from
            the run that produced the paper plane — measured, not illustrative.
          </p>
        </div>

        <ol className="mt-14">
          {STEPS.map((s, i) => (
            <Step key={s.step} s={s} i={i} />
          ))}
        </ol>

        <p ref={foot} className="reveal num mt-8 rule-t pt-6 text-[13px] text-dim">
          86 KB raster <span className="text-dim/40">→</span>{' '}
          <span className="text-lamp">868 B vector</span>
          <span className="ml-3 font-sans text-[13px] text-dim/70">
            a hundredth the size, infinitely scalable, and animatable
          </span>
        </p>
      </div>
    </section>
  );
}
