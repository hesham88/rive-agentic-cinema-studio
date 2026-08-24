'use client';

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react';
import { Fit, Layout, useRive } from '@rive-app/react-webgl2';
import { clamp, remap } from '../../core/motion';
import { useRiveChannels } from '../useRiveChannels';

/**
 * Controls whose pixels come from Rive and whose behaviour comes from the DOM.
 *
 * The split is deliberate and it is the whole design:
 *
 *   * A real `<button>`, `<input type="range">` or `<input type="text">` sits
 *     in the tree, invisible, carrying every affordance a control must have —
 *     focus, keyboard operation, screen-reader semantics, form participation,
 *     autofill, IME. None of that is reproducible on a canvas, and a canvas
 *     that fakes it excludes people.
 *   * The Rive artboard renders on top of it, purely decorative, marked
 *     `aria-hidden`, driven from the DOM element's own state.
 *
 * So a screen reader hears a button and a mouse sees a Rive animation, and
 * neither has to compromise. The canvas never receives pointer events; the
 * native element does, and reports what happened.
 */

const KIT = '/riv/ui-kit.riv';

interface StageProps {
  artboard: string;
  /** Rive draws at the artboard's own size; the wrapper decides the box. */
  className?: string;
  onRive: (rive: ReturnType<typeof useRive>['rive']) => void;
}

/**
 * One kit artboard, mounted and reported upward.
 *
 * `aria-hidden` plus `pointer-events-none` is what keeps the canvas out of the
 * accessibility tree and out of hit-testing — the native control underneath
 * owns both.
 */
function Stage({ artboard, className, onRive }: StageProps) {
  const { rive, RiveComponent } = useRive({
    src: KIT,
    artboard,
    autoplay: true,
    autoBind: true,
    layout: new Layout({ fit: Fit.Contain }),
  });

  useEffect(() => {
    onRive(rive);
  }, [rive, onRive]);

  return (
    <div aria-hidden className={'pointer-events-none absolute inset-0 ' + (className ?? '')}>
      <RiveComponent className="h-full w-full" />
    </div>
  );
}

/** Shared plumbing: hold the instance, expose spring-driven channels. */
function useWidget(initial: Record<string, number>) {
  const [rive, setRive] = useState<ReturnType<typeof useRive>['rive']>(null);
  const onRive = useCallback((r: ReturnType<typeof useRive>['rive']) => setRive(r), []);
  const channels = useRiveChannels(rive ?? null, initial);
  return { onRive, channels };
}

/* -------------------------------------------------------------------------- */
/* Button                                                                      */
/* -------------------------------------------------------------------------- */

export interface RiveButtonProps {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  'data-testid'?: string;
}

/**
 * A button that lifts and glows on hover and compresses on press.
 *
 * The press response is squash: scaling down slightly in Y more than in X reads
 * as the surface taking weight, where a uniform scale reads as a zoom.
 */
export function RiveButton({
  children,
  onClick,
  disabled,
  className,
  ...rest
}: RiveButtonProps) {
  const { onRive, channels } = useWidget({
    glow: 0,
    tint: 0,
    scaleX: 100,
    scaleY: 100,
    lift: 28,
  });

  const set = (hover: boolean, press: boolean) => {
    if (disabled) return;
    channels.setTarget({
      glow: hover ? 34 : 0,
      tint: press ? 12 : hover ? 5 : 0,
      scaleX: press ? 99.2 : 100,
      scaleY: press ? 96 : 100,
      lift: press ? 28.5 : hover ? 26.5 : 28,
    });
  };

  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      onPointerEnter={() => set(true, false)}
      onPointerLeave={() => set(false, false)}
      onPointerDown={() => set(true, true)}
      onPointerUp={() => set(true, false)}
      onFocus={() => set(true, false)}
      onBlur={() => set(false, false)}
      className={
        'relative isolate inline-flex h-14 w-[220px] items-center justify-center text-sm font-semibold text-paper disabled:opacity-40 ' +
        (className ?? '')
      }
      {...rest}
    >
      <Stage artboard="ui/button" onRive={onRive} />
      <span className="relative z-10">{children}</span>
    </button>
  );
}

/* -------------------------------------------------------------------------- */
/* Toggle                                                                      */
/* -------------------------------------------------------------------------- */

export interface RiveToggleProps {
  checked: boolean;
  onChange: (next: boolean) => void;
  label: string;
  className?: string;
  'data-testid'?: string;
}

/** A switch. The knob travels 18 -> 50 px across a 68 px track. */
export function RiveToggle({
  checked,
  onChange,
  label,
  className,
  ...rest
}: RiveToggleProps) {
  const { onRive, channels } = useWidget({ on: 0, knobX: 18 });

  useEffect(() => {
    channels.setTarget({ on: checked ? 100 : 0, knobX: checked ? 50 : 18 });
  }, [checked, channels]);

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={'relative isolate inline-block h-9 w-[68px] ' + (className ?? '')}
      {...rest}
    >
      <Stage artboard="ui/toggle" onRive={onRive} />
    </button>
  );
}

/* -------------------------------------------------------------------------- */
/* Slider                                                                      */
/* -------------------------------------------------------------------------- */

export interface RiveSliderProps {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  onChange: (next: number) => void;
  label: string;
  className?: string;
  'data-testid'?: string;
}

/**
 * A slider driven by a real range input.
 *
 * The fill is written immediately rather than sprung: a sprung fill lags the
 * thumb the user is dragging, and that lag reads as the control being broken
 * rather than as smoothing. Springs are for state changes, not for direct
 * manipulation.
 */
export function RiveSlider({
  value,
  min = 0,
  max = 100,
  step = 1,
  onChange,
  label,
  className,
  ...rest
}: RiveSliderProps) {
  const [rive, setRive] = useState<ReturnType<typeof useRive>['rive']>(null);
  const onRive = useCallback((r: ReturnType<typeof useRive>['rive']) => setRive(r), []);
  const immediate = useMemo(() => ['fillW', 'thumbX'] as const, []);
  const channels = useRiveChannels(rive ?? null, { fillW: 0, thumbX: 14 }, { immediate });

  useEffect(() => {
    const t = remap(value, min, max, 0, 1);
    channels.setTarget({
      // Track runs 14..226; the fill grows from its left edge (originX = 0).
      fillW: t * 212,
      thumbX: 14 + t * 212,
    });
  }, [value, min, max, channels]);

  return (
    <div className={'relative isolate h-9 w-[240px] ' + (className ?? '')}>
      <Stage artboard="ui/slider" onRive={onRive} />
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        aria-label={label}
        onChange={(e) => onChange(Number(e.target.value))}
        className="absolute inset-0 h-full w-full cursor-pointer opacity-0"
        {...rest}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Text field                                                                  */
/* -------------------------------------------------------------------------- */

export interface RiveFieldProps {
  value: string;
  onChange: (next: string) => void;
  label: string;
  placeholder?: string;
  className?: string;
  'data-testid'?: string;
}

/**
 * A text field whose focus ring and caret are Rive.
 *
 * The real caret is hidden and a drawn one is positioned from a measured text
 * width, because a canvas cannot host a native caret. Measurement uses the
 * input's own computed font, so the drawn caret tracks the real one even when
 * the page's font changes.
 */
export function RiveField({
  value,
  onChange,
  label,
  placeholder,
  className,
  ...rest
}: RiveFieldProps) {
  const { onRive, channels } = useWidget({ ring: 0, caret: 0, caretX: 22 });
  const inputRef = useRef<HTMLInputElement>(null);
  const [focused, setFocused] = useState(false);
  const id = useId();

  // Caret position, measured on a canvas with the input's real font.
  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    let width = 0;
    try {
      const canvas = document.createElement('canvas');
      const ctx = canvas.getContext('2d');
      if (ctx) {
        const cs = getComputedStyle(el);
        ctx.font = `${cs.fontSize} ${cs.fontFamily}`;
        width = ctx.measureText(value).width;
      }
    } catch {
      /* measurement unavailable; the caret stays at the text start */
    }
    channels.setTarget({ caretX: clamp(22 + width, 22, 276) });
  }, [value, channels]);

  useEffect(() => {
    channels.setTarget({ ring: focused ? 100 : 0, caret: focused ? 100 : 0 });
  }, [focused, channels]);

  return (
    <div className={'relative isolate h-[52px] w-[300px] ' + (className ?? '')}>
      <Stage artboard="ui/field" onRive={onRive} />
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <input
        id={id}
        ref={inputRef}
        type="text"
        value={value}
        placeholder={placeholder}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => setFocused(true)}
        onBlur={() => setFocused(false)}
        // `caret-transparent` hands the caret to Rive; the input still owns
        // selection, IME and every keyboard behaviour.
        className="absolute inset-0 h-full w-full bg-transparent px-5 text-[13px] text-paper caret-transparent outline-none placeholder:text-slate/60"
        {...rest}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Select                                                                      */
/* -------------------------------------------------------------------------- */

export interface RiveSelectProps {
  value: string;
  options: readonly string[];
  onChange: (next: string) => void;
  label: string;
  className?: string;
  'data-testid'?: string;
}

/**
 * A select whose chevron is Rive and whose menu is the platform's.
 *
 * The dropdown list itself is deliberately NOT drawn: a native `<select>` gets
 * the operating system's own picker, which on a phone is a wheel and on a
 * desktop is a menu that can escape the page bounds. A canvas menu can do
 * neither, and reimplementing one is how comboboxes become inaccessible.
 */
export function RiveSelect({
  value,
  options,
  onChange,
  label,
  className,
  ...rest
}: RiveSelectProps) {
  const { onRive, channels } = useWidget({ chevron: 0, panel: 100 });
  const id = useId();

  return (
    <div className={'relative isolate h-[52px] w-[220px] ' + (className ?? '')}>
      <Stage artboard="ui/select" onRive={onRive} />
      <label htmlFor={id} className="sr-only">
        {label}
      </label>
      <select
        id={id}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => channels.setTarget({ chevron: 180 })}
        onBlur={() => channels.setTarget({ chevron: 0 })}
        onPointerEnter={() => channels.setTarget({ panel: 100 })}
        className="absolute inset-0 h-full w-full appearance-none bg-transparent px-5 text-[13px] text-paper outline-none"
        {...rest}
      >
        {options.map((o) => (
          <option key={o} value={o} className="bg-deep text-paper">
            {o}
          </option>
        ))}
      </select>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Tabs                                                                        */
/* -------------------------------------------------------------------------- */

export interface RiveTabsProps {
  tabs: readonly string[];
  active: number;
  onChange: (index: number) => void;
  label: string;
  className?: string;
}

/**
 * A tab bar whose indicator is a Rive shape that slides and resizes.
 *
 * Both position and width are driven, so the pill genuinely fits each label
 * rather than being a fixed-width marker that slides — which is the difference
 * between a control that looks designed and one that looks approximate.
 */
export function RiveTabs({ tabs, active, onChange, label, className }: RiveTabsProps) {
  const { onRive, channels } = useWidget({ indX: 4, indW: 106 });
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const list = listRef.current;
    if (!list) return;
    const el = list.children[active] as HTMLElement | undefined;
    if (!el) return;
    // Artboard is 330 wide; the DOM row may be a different width, so measure
    // and rescale rather than assuming they match.
    const scale = 330 / list.getBoundingClientRect().width;
    channels.setTarget({
      indX: el.offsetLeft * scale,
      indW: el.offsetWidth * scale,
    });
  }, [active, tabs, channels]);

  return (
    <div className={'relative isolate h-11 w-[330px] ' + (className ?? '')}>
      <Stage artboard="ui/tabs" onRive={onRive} />
      <div ref={listRef} role="tablist" aria-label={label} className="relative flex h-full">
        {tabs.map((t, i) => (
          <button
            key={t}
            type="button"
            role="tab"
            aria-selected={i === active}
            onClick={() => onChange(i)}
            className={
              'flex-1 text-[13px] font-medium transition-colors duration-200 ' +
              (i === active ? 'text-void' : 'text-slate hover:text-paper')
            }
          >
            {t}
          </button>
        ))}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Progress                                                                    */
/* -------------------------------------------------------------------------- */

export interface RiveProgressProps {
  /** 0..1. Omit for an indeterminate bar. */
  value?: number;
  label: string;
  className?: string;
}

/** A progress bar. Without a `value` it runs an indeterminate shimmer. */
export function RiveProgress({ value, label, className }: RiveProgressProps) {
  const { onRive, channels } = useWidget({ fillW: 0, shimmerX: 0, shimmer: 0 });
  const indeterminate = value === undefined;

  useEffect(() => {
    if (indeterminate) {
      channels.setTarget({ fillW: 240, shimmer: 55 });
      return;
    }
    channels.setTarget({ fillW: clamp(value, 0, 1) * 240, shimmer: 0 });
  }, [value, indeterminate, channels]);

  // The travelling highlight. Driven here rather than keyframed in Rive so the
  // same artboard serves both the determinate and indeterminate cases.
  useEffect(() => {
    if (!indeterminate) return;
    let raf = 0;
    const start = performance.now();
    const tick = () => {
      const t = ((performance.now() - start) / 1400) % 1;
      channels.snapTo({ shimmerX: -24 + t * 288 });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [indeterminate, channels]);

  return (
    <div
      role="progressbar"
      aria-label={label}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={indeterminate ? undefined : Math.round(clamp(value, 0, 1) * 100)}
      className={'relative isolate h-2.5 w-[240px] ' + (className ?? '')}
    >
      <Stage artboard="ui/progress" onRive={onRive} />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Panel                                                                       */
/* -------------------------------------------------------------------------- */

export interface RivePanelProps {
  children: ReactNode;
  className?: string;
}

/**
 * A container whose surface, edge and travelling sheen are Rive.
 *
 * The sheen runs once on hover rather than looping: a highlight that sweeps
 * forever is an attention magnet in the corner of the eye, which is exactly
 * what a container must not be.
 */
export function RivePanel({ children, className }: RivePanelProps) {
  const { onRive, channels } = useWidget({ sheenX: 40, sheen: 0, edge: 0 });
  const sweeping = useRef(false);

  const sweep = useCallback(() => {
    if (sweeping.current) return;
    sweeping.current = true;
    channels.snapTo({ sheenX: 20, sheen: 90 });
    channels.setTarget({ sheenX: 320, sheen: 0, edge: 45 });
    window.setTimeout(() => {
      sweeping.current = false;
    }, 900);
  }, [channels]);

  return (
    <div
      onPointerEnter={sweep}
      onPointerLeave={() => channels.setTarget({ edge: 0 })}
      className={'relative isolate min-h-[220px] w-full ' + (className ?? '')}
    >
      <Stage artboard="ui/panel" onRive={onRive} />
      <div className="relative z-10 h-full w-full p-6">{children}</div>
    </div>
  );
}
