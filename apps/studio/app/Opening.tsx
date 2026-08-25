'use client';

import Link from 'next/link';
import { useCanvasResync } from 'rive-engine/react';
import { Fit, Layout, useRive } from '@rive-app/react-webgl2';
import { useEffect, useRef, useState } from 'react';
import { HeroCollage } from './HeroCollage';

/**
 * The opening shot.
 *
 * The hero is the artefact, not a picture of it: `scene.riv` is playing its own
 * generated camera move, and everything visible was made by the pipeline this
 * page goes on to describe. A screenshot of an interactive asset proves
 * nothing, so the page refuses to use one.
 *
 * The scene sits ON A MONITOR rather than bleeding behind the words. Two
 * attempts at a full-bleed backdrop failed for the same underlying reason:
 * type over moving art needs a scrim, a scrim heavy enough to read through
 * mutes the art, and muting the art destroys the only argument the section is
 * making. Framing it solves both — the words get a clean ground, and the
 * artwork stays fully saturated, which the palette reserves for exactly this.
 *
 * It is also the truer reading of the room. You sit at the desk; the footage is
 * on the monitor in front of you.
 */

/** Real keyframes from the camera engine's `CameraMove`. */
const BEATS = [
  { frame: 0, name: 'wide', note: 'locked off' },
  { frame: 110, name: 'push in', note: 'dolly 2.2×' },
  { frame: 136, name: 'shake', note: 'liftoff' },
  { frame: 216, name: 'follow', note: 'track up' },
  { frame: 286, name: 'canted', note: 'roll 6°' },
] as const;

const TOTAL = BEATS[BEATS.length - 1].frame;
const FPS = 60;

export function Opening() {
  const [frame, setFrame] = useState(0);
  const [failed, setFailed] = useState(false);
  const startedAt = useRef(0);

  const { rive, RiveComponent } = useRive({
    src: '/riv/scene.riv',
    artboard: 'Scene',
    stateMachines: 'State Machine 1',
    autoplay: true,
    autoBind: true,
    // Contain: the monitor is sized to the artboard's own 5:3, so nothing is
    // cropped and the composition the camera engine framed survives.
    layout: new Layout({ fit: Fit.Contain }),
    onLoadError: () => setFailed(true),
  });

  useCanvasResync(rive);

  // The runtime exposes no frame cursor, so the readout runs on a wall clock in
  // step with the looping timeline rather than reaching into internals.
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

  const beat = BEATS.reduce((acc, b, i) => (frame >= b.frame ? i : acc), 0);

  return (
    <section id="open" className="relative isolate min-h-dvh overflow-hidden">
      <HeroCollage />
      {/* The room: a single warm pool of light behind the monitor, so the
          brightest thing on screen has somewhere to sit. Nothing else in this
          viewport is coloured. */}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 z-0"
        style={{
          background:
            'radial-gradient(58% 48% at 74% 42%, ' +
            'color-mix(in srgb, var(--color-lamp) 9%, transparent) 0%, ' +
            'transparent 70%)',
        }}
      />

      <div className="relative z-10 mx-auto grid min-h-dvh max-w-[1400px] items-center gap-14 px-6 pb-20 pt-28 lg:grid-cols-[1fr_minmax(0,540px)] lg:gap-12 lg:pl-[224px] xl:gap-16">
        <div>
          {/* The mark this studio generated for itself, gliding. */}
          {/* The hero mark is deliberately absent.
              It used to sit here: a two-path, two-colour paper plane that the
              pipeline's own quality gate now rejects (it needs 80-160 paths and
              24-36 colours). Shipping it beside the sentence "everything on this
              page was made that way" argued the opposite of what the page claims.

              Its removal is also the palette's own rule applied: ONE chromatic
              action per view. The monitor is the artwork, so the monitor is the
              only saturated thing above the fold, and the type carries the rest. */}

          {/* 6px gap, not 24. The eyebrow and the headline are ONE unit; the
              caption's 0.90 leading exists so they can sit this close. */}
          <p className="eyebrow whitespace-nowrap">Agentic studio · web &amp; cinema</p>

          {/* clamp() floors at 40px and tops out at the spec's 80px. Tracking
              rides the same scale via `display-xl`, so the headline is tracked
              correctly at every width instead of at one. */}
          <h1 className="display display-xl mt-1.5 text-[clamp(2.5rem,6vw,5rem)]">
            A sentence becomes <em>a scene.</em>
          </h1>

          <p className="mt-7 max-w-[52ch] text-[16px] leading-[1.5] text-read">
            Describe what you want. The studio researches how it is really drawn, generates
            the art, traces it to vector, rigs it, animates it, scores it, and ships an
            interactive file the web can run.
          </p>

          <p className="mt-4 max-w-[52ch] text-[14px] leading-[1.5] text-dim">
            Everything on this page was made that way — including the scene beside these
            words, and the camera move framing it.
          </p>

          <div className="mt-9 flex flex-wrap items-center gap-3">
            <Link
              href="/inspect"
              className="btn btn-filled"
            >
              open the inspector
            </Link>
            <a
              href="#pipeline"
              className="btn btn-ghost"
            >
              how it works
            </a>
          </div>
        </div>

        {/* The monitor */}
        <figure className="m-0">
          <div className="panel panel-lit overflow-hidden">
            <div className="aspect-[5/3] w-full bg-room">
              {failed ? (
                <div className="flex h-full items-center justify-center px-6 text-center">
                  <p className="num text-[13px] text-dim">
                    scene.riv did not load —{' '}
                    <code className="text-glow">/riv/scene.riv</code>
                  </p>
                </div>
              ) : (
                <RiveComponent className="h-full w-full" />
              )}
            </div>
          </div>

          {/* The camera move, read out live. Real frames, not illustration. */}
          <figcaption className="mt-5">
            <div className="flex items-baseline justify-between">
              <p className="eyebrow">CameraMove · scene.riv</p>
              <p className="num text-[11px] text-dim">
                <span className="text-glow">{String(frame).padStart(3, '0')}</span>
                <span className="text-dim/40"> / {TOTAL}</span>
              </p>
            </div>

            <ol className="mt-4 grid grid-cols-5 gap-2.5">
              {BEATS.map((b, i) => (
                <li key={b.name} className="min-w-0">
                  <div
                    className={`h-px w-full transition-colors duration-500 ${
                      i <= beat ? 'bg-signal' : 'bg-rule'
                    }`}
                  />
                  <p
                    className={`num mt-2 text-[10px] transition-colors duration-500 ${
                      i === beat ? 'text-glow' : 'text-dim/50'
                    }`}
                  >
                    {String(b.frame).padStart(3, '0')}
                  </p>
                  <p
                    className={`mt-0.5 truncate text-[12px] transition-colors duration-500 ${
                      i === beat ? 'text-bright' : 'text-dim'
                    }`}
                  >
                    {b.name}
                  </p>
                  <p className="num mt-0.5 hidden truncate text-[10px] text-dim/60 sm:block">
                    {b.note}
                  </p>
                </li>
              ))}
            </ol>
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
