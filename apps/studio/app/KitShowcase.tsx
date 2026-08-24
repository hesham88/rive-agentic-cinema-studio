'use client';

import { useState } from 'react';
import {
  RiveButton,
  RiveField,
  RiveProgress,
  RiveSelect,
  RiveSlider,
  RiveTabs,
  RiveToggle,
} from 'rive-engine/react';
import { useReveal } from './useScrollProgress';

/**
 * The kit, driving itself.
 *
 * Every control on this page is a Rive artboard: the button's surface, the
 * switch's knob, the slider's fill, the field's focus ring and caret, the tab
 * indicator, the progress bar. None of them are CSS.
 *
 * The section is wired as one small working panel rather than a specimen sheet,
 * because a row of disconnected controls proves they render, while a panel that
 * responds proves they work.
 */

const FINISHES = ['Glass', 'Matte', 'Ink', 'Neon'] as const;

function Row({ label, hint, children }: { label: string; hint: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-4 border-t border-rule py-5 first:border-t-0 first:pt-0">
      <div className="min-w-0">
        <p className="text-sm font-medium text-bright">{label}</p>
        <p className="num mt-0.5 text-[11px] text-dim/60">{hint}</p>
      </div>
      {children}
    </div>
  );
}

export function KitShowcase() {
  const head = useReveal<HTMLDivElement>();
  const body = useReveal<HTMLDivElement>(120);

  const [tab, setTab] = useState(0);
  const [grain, setGrain] = useState(42);
  const [bloom, setBloom] = useState(68);
  const [motionOn, setMotionOn] = useState(true);
  const [finish, setFinish] = useState<string>(FINISHES[0]);
  const [title, setTitle] = useState('Night launch');
  const [rendering, setRendering] = useState(false);

  return (
    <section id="kit" className="relative border-t border-rule">
      <div className="relative z-10 mx-auto max-w-6xl px-6 py-24">
        <div ref={head} className="reveal">
          <p className="eyebrow">Not a single CSS control</p>
          <h2 className="display mt-3 max-w-3xl text-[clamp(1.75rem,3.5vw,2.5rem)]">
            The interface is Rive too.
          </h2>
          <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-read">
            The button, the switch, the slider, the field, the tabs and the bar below are
            all artboards from one 4.8&nbsp;KB file. Rive draws them; the engine&rsquo;s
            spring maths — the same law that moves the camera — animates them. Every one
            is a real focusable control underneath, so they work from the keyboard.
          </p>
        </div>

        <div ref={body} className="reveal mt-12 grid gap-6 lg:grid-cols-[1fr_320px]">
          <div className="panel p-6 sm:p-8">
            <RiveTabs
              tabs={['Render', 'Grade', 'Export']}
              active={tab}
              onChange={setTab}
              label="Panel section"
            />

            <div className="mt-8">
              <Row label="Scene title" hint="bound text · caret and ring are Rive">
                <RiveField value={title} onChange={setTitle} label="Scene title" />
              </Row>

              <Row label="Grain" hint={`slider · fill width ${Math.round(grain * 2.12)}px`}>
                <RiveSlider value={grain} onChange={setGrain} label="Grain" />
              </Row>

              <Row label="Bloom" hint={`slider · ${bloom}%`}>
                <RiveSlider value={bloom} onChange={setBloom} label="Bloom" />
              </Row>

              <Row label="Motion blur" hint="switch · knob travels 18 → 50px">
                <RiveToggle
                  checked={motionOn}
                  onChange={setMotionOn}
                  label="Motion blur"
                />
              </Row>

              <Row label="Finish" hint="select · chevron rotates, menu is native">
                <RiveSelect
                  value={finish}
                  options={FINISHES}
                  onChange={setFinish}
                  label="Finish"
                />
              </Row>
            </div>
          </div>

          <div className="panel flex flex-col p-6">
            <p className="eyebrow">Output</p>
            <dl className="mt-4 flex flex-col gap-2.5">
              {[
                ['title', title || '—'],
                ['finish', finish],
                ['grain', `${grain}`],
                ['bloom', `${bloom}`],
                ['blur', motionOn ? 'on' : 'off'],
                ['section', ['render', 'grade', 'export'][tab] ?? '—'],
              ].map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between gap-3">
                  <dt className="num text-[11px] uppercase tracking-wider text-dim/60">
                    {k}
                  </dt>
                  <dd className="num truncate text-[12px] text-bright">{v}</dd>
                </div>
              ))}
            </dl>

            <div className="mt-6 border-t border-rule pt-5">
              <RiveProgress
                value={rendering ? undefined : 0.0}
                label="Render progress"
                className="w-full"
              />
              <p className="num mt-3 text-[11px] text-dim/60">
                {rendering ? 'rendering…' : 'idle'}
              </p>
            </div>

            <div className="mt-auto pt-6">
              <RiveButton
                onClick={() => {
                  setRendering(true);
                  window.setTimeout(() => setRendering(false), 2600);
                }}
                disabled={rendering}
                className="w-full"
                data-testid="kit-render"
              >
                {rendering ? 'Rendering' : 'Render scene'}
              </RiveButton>
            </div>
          </div>
        </div>

        <p className="num mt-8 text-[11px] text-dim/50">
          ui-kit.riv · 4,822 B · 8 artboards · 21 bound channels
        </p>
      </div>
    </section>
  );
}
