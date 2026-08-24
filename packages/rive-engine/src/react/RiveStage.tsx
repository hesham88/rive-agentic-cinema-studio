'use client';

import type { RiveControllerState } from './useRiveController';

export interface RiveStageProps {
  /**
   * The `RiveComponent` from `useRiveController`. Passed in rather than created
   * here so the app has exactly ONE Rive instance: a second `useRiveController`
   * call would mount a second instance, and whichever one lacks a rendered
   * canvas never loads at all.
   */
  component: RiveControllerState['RiveComponent'] | null;
  className?: string;
}

/**
 * Canvas host.
 *
 * Remounting on selection change is the CALLER's job, via a `key` prop:
 * `<RiveStage key={`${artboard}/${stateMachine}`} ... />`. Without it the Rive
 * instance is reused across artboards and inputs go stale.
 */
export function RiveStage({ component: RiveComponent, className }: RiveStageProps) {
  if (!RiveComponent) {
    return <div className={className} data-testid="rive-stage-empty" />;
  }

  return (
    <div className={className} data-testid="rive-stage">
      <RiveComponent />
    </div>
  );
}
