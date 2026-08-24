'use client';

import { useEffect, useState } from 'react';
import { Fit, Layout, useRive } from '@rive-app/react-webgl2';
import { useHeroMotion } from 'rive-engine/react';

/**
 * The mark, gliding.
 *
 * Every part of this asset came from the pipeline the page describes: Parallel
 * researched how a paper plane is really drawn, Gemini drew it, the tracer
 * simplified it, the facet splitter derived the fold, and it was authored into
 * Rive over MCP. It exposes `lift`, `bank` and `glide` — what the mark means,
 * not the properties those happen to move.
 *
 * The motion follows the researched timings and, more importantly, the
 * researched *restraint*: the same query answered "0% squash by default, keep
 * the silhouette rigid", so nothing here deforms. A stiff object that squashes
 * reads as wrong even when the viewer cannot say why.
 */
export function HeroMark({ className = '' }: { className?: string }) {
  const [failed, setFailed] = useState(false);

  const { rive, RiveComponent } = useRive({
    src: '/riv/hero-plane.riv',
    artboard: 'hero/plane',
    stateMachines: 'State Machine 1',
    autoplay: true,
    autoBind: true,
    layout: new Layout({ fit: Fit.Contain }),
    onLoadError: () => setFailed(true),
  });

  const flying = useHeroMotion(rive ?? null);

  useEffect(() => {
    if (rive && !flying) {
      // Not fatal — the mark still renders, it just sits still. Worth saying
      // out loud rather than silently shipping a static logo.
      // eslint-disable-next-line no-console
      console.warn('[hero] channels not found; the mark will not glide');
    }
  }, [rive, flying]);

  if (failed) {
    return (
      <div className={`flex items-center justify-center ${className}`}>
        <p className="num text-[12px] text-dim">hero-plane.riv did not load</p>
      </div>
    );
  }

  return <RiveComponent className={className} />;
}
