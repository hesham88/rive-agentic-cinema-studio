'use client';

import { useEffect, useMemo, useState } from 'react';
import { Fit, Layout, useRive } from '@rive-app/react-webgl2';
import type { StateMachineInput } from '@rive-app/react-webgl2';
import { RIVE_INPUT_TYPE } from 'rive-engine';
import { useViewModelControls } from 'rive-engine/react';
import { useReveal } from './useReveal';

/**
 * The control deck — the page's signature element.
 *
 * Nothing here is hardcoded to a particular file. The deck loads a `.riv`, asks
 * it what it exposes, and builds one control per property. Point it at a
 * different file and the panel rebuilds itself.
 *
 * It reads BOTH of Rive's input systems, which is the whole reason this panel
 * is interesting. Classic state-machine inputs (`stateMachineInputs()`) and
 * view-model properties are separate worlds that do not overlap: a file
 * authored with data binding reports zero state-machine inputs while being
 * fully interactive. A deck that read only the classic system would show an
 * empty panel over a working animation — which is exactly what the first
 * version of this component did, until the e2e test caught it.
 */

interface Rig {
  id: string;
  file: string;
  artboard?: string;
  stateMachine: string;
  label: string;
  note: string;
  /** Said out loud, because "works on files we did not author" is the claim. */
  origin: string;
}

const RIGS: Rig[] = [
  {
    id: 'plane',
    file: '/riv/paper-plane-interactive.riv',
    stateMachine: 'State Machine 1',
    label: 'Paper plane',
    note: 'Generated here, and driven by data binding: a boolean crossfades idle float into a hover bank, and a number feeds the boost.',
    origin: 'made by this studio',
  },
  {
    id: 'jeep',
    file: '/riv/vehicles.riv',
    artboard: 'Jeep',
    stateMachine: 'weather',
    label: 'Jeep',
    note: 'Rive’s own public sample, which this studio did not author. The deck reads it anyway — a classic state-machine boolean, switching the weather.',
    origin: 'Rive sample, cdn.rive.app',
  },
  {
    id: 'truck',
    file: '/riv/vehicles.riv',
    artboard: 'Truck',
    stateMachine: 'bumpy',
    label: 'Truck',
    note: 'The same file, a different artboard, a different interface — one trigger instead of a boolean. Nothing about the panel is written for it.',
    origin: 'Rive sample, cdn.rive.app',
  },
];

type Kind = 'boolean' | 'number' | 'trigger' | 'string' | 'enum' | 'unknown';

/** One control, regardless of which of Rive's two systems it came from. */
interface Control {
  key: string;
  name: string;
  kind: Kind;
  /** Which system exposed it — shown, because the difference is real. */
  source: 'state machine' | 'view model';
  value: boolean | number | string | undefined;
  options: string[];
  rawType?: string | number;
  set(next: boolean | number | string): void;
  fire(): void;
}

function classicKind(input: StateMachineInput): Kind {
  switch (input.type) {
    case RIVE_INPUT_TYPE.Boolean:
      return 'boolean';
    case RIVE_INPUT_TYPE.Number:
      return 'number';
    case RIVE_INPUT_TYPE.Trigger:
      return 'trigger';
    default:
      return 'unknown';
  }
}

/* -------------------------------------------------------------------------- */

function Toggle({ c, onSignal }: { c: Control; onSignal: () => void }) {
  const [on, setOn] = useState(Boolean(c.value));
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={c.name}
      data-testid={'deck-boolean-' + c.name}
      onClick={() => {
        const next = !on;
        c.set(next);
        setOn(next);
        onSignal();
      }}
      className={
        'relative h-6 w-11 shrink-0 rounded-full border transition-colors duration-200 ' +
        (on ? 'border-ignite/70 bg-ignite/80' : 'border-white/20 bg-white/10')
      }
    >
      <span
        className={
          'absolute top-1/2 h-4 w-4 -translate-y-1/2 rounded-full bg-paper shadow transition-[left] duration-200 ' +
          (on ? 'left-6' : 'left-0.5')
        }
      />
    </button>
  );
}

function Slider({ c, onSignal }: { c: Control; onSignal: () => void }) {
  const [value, setValue] = useState(Number(c.value ?? 0));
  // Range is 0–100 by convention: Rive numbers on these rigs are percentages or
  // 0–1 blend weights, and a slider that cannot reach a value is worse than one
  // with headroom.
  return (
    <div className="flex min-w-0 flex-1 items-center gap-3">
      <input
        type="range"
        min={0}
        max={100}
        step={1}
        value={value}
        aria-label={c.name}
        data-testid={'deck-number-' + c.name}
        onChange={(e) => {
          const next = Number(e.target.value);
          c.set(next);
          setValue(next);
          onSignal();
        }}
        className="h-1 w-full min-w-0 cursor-pointer appearance-none rounded-full bg-white/20 accent-ignite"
      />
      <output className="num w-8 shrink-0 text-right text-xs text-flame">{value}</output>
    </div>
  );
}

function Trigger({ c, onSignal }: { c: Control; onSignal: () => void }) {
  const [pulses, setPulses] = useState(0);
  return (
    <button
      type="button"
      data-testid={'deck-trigger-' + c.name}
      onClick={() => {
        c.fire();
        setPulses((p) => p + 1);
        onSignal();
      }}
      className="num shrink-0 rounded-md border border-ignite/40 bg-ignite/10 px-3 py-1.5 text-[11px] text-flame transition-colors hover:border-ignite hover:bg-ignite/25"
    >
      fire
      {pulses > 0 && <span className="ml-1.5 text-slate/70">{pulses}</span>}
    </button>
  );
}

function TextField({ c, onSignal }: { c: Control; onSignal: () => void }) {
  const [text, setText] = useState(String(c.value ?? ''));
  return (
    <input
      type="text"
      aria-label={c.name}
      data-testid={'deck-string-' + c.name}
      value={text}
      onChange={(e) => {
        setText(e.target.value);
        c.set(e.target.value);
        onSignal();
      }}
      className="num min-w-0 flex-1 rounded-md border border-white/15 bg-void/50 px-2.5 py-1.5 text-[12px] text-paper outline-none transition-colors focus:border-flame/60"
    />
  );
}

function EnumField({ c, onSignal }: { c: Control; onSignal: () => void }) {
  const [choice, setChoice] = useState(String(c.value ?? c.options[0] ?? ''));
  return (
    <select
      aria-label={c.name}
      data-testid={'deck-enum-' + c.name}
      value={choice}
      onChange={(e) => {
        setChoice(e.target.value);
        c.set(e.target.value);
        onSignal();
      }}
      className="num min-w-0 shrink-0 rounded-md border border-white/15 bg-void/50 px-2.5 py-1.5 text-[12px] text-paper outline-none focus:border-flame/60"
    >
      {c.options.map((o) => (
        <option key={o} value={o}>
          {o}
        </option>
      ))}
    </select>
  );
}

/* -------------------------------------------------------------------------- */

function Deck({ rig }: { rig: Rig }) {
  const [classic, setClassic] = useState<StateMachineInput[]>([]);
  const [signals, setSignals] = useState(0);

  const { rive, RiveComponent } = useRive({
    src: rig.file,
    artboard: rig.artboard,
    stateMachines: rig.stateMachine,
    autoplay: true,
    // Not the default. Without it the runtime binds no view model instance, so
    // a data-bound file reports nothing drivable while animating perfectly.
    autoBind: true,
    layout: new Layout({ fit: Fit.Contain }),
  });

  // Inputs only exist once the machine is instanced, so this reads them after
  // load rather than at mount.
  useEffect(() => {
    if (!rive) {
      setClassic([]);
      return;
    }
    setClassic(rive.stateMachineInputs(rig.stateMachine) ?? []);
    setSignals(0);
  }, [rive, rig.stateMachine]);

  const vm = useViewModelControls(rive ?? null);


  const controls = useMemo<Control[]>(() => {
    const fromClassic: Control[] = classic.map((input) => ({
      key: 'sm:' + input.name,
      name: input.name,
      kind: classicKind(input),
      source: 'state machine',
      value: input.value,
      options: [],
      rawType: input.type,
      set: (next) => {
        input.value = next as never;
      },
      fire: () => input.fire(),
    }));

    const fromVm: Control[] = vm.handles.map((h) => ({
      key: 'vm:' + h.key,
      name: h.info.name,
      kind: (['boolean', 'number', 'trigger', 'string', 'enum'] as const).includes(
        h.info.kind as never,
      )
        ? (h.info.kind as Kind)
        : 'unknown',
      source: 'view model',
      value: h.value,
      options: h.options,
      rawType: h.info.rawType,
      set: h.set,
      fire: h.fire,
    }));

    return [...fromClassic, ...fromVm];
  }, [classic, vm.handles]);

  const onSignal = () => setSignals((s) => s + 1);

  return (
    <div className="grid gap-6 lg:grid-cols-[1.25fr_1fr]">
      <div className="glass overflow-hidden">
        <div className="aspect-[16/10] w-full">
          <RiveComponent className="h-full w-full" />
        </div>
      </div>

      <div className="glass flex flex-col p-5">
        <div className="flex items-baseline justify-between gap-3">
          <p className="eyebrow">Exposed properties</p>
          <span className="num text-[11px] text-slate/60">{controls.length} found</span>
        </div>
        <p className="mt-2 text-sm leading-relaxed text-slate">{rig.note}</p>
        <p className="num mt-2 text-[10px] uppercase tracking-wider text-slate/50">
          {rig.origin}
        </p>

        <ul className="mt-5 flex flex-col gap-3">
          {controls.length === 0 && (
            <li className="num text-xs text-slate/60" data-testid="deck-empty">
              {rive ? 'this file exposes nothing drivable' : 'reading the file…'}
            </li>
          )}
          {controls.map((c) => (
            <li
              key={c.key}
              className="flex items-center gap-4 rounded-lg border border-white/10 bg-white/5 px-3 py-2.5"
            >
              <div className="min-w-0 flex-1">
                <p className="num truncate text-[13px] text-paper">{c.name}</p>
                <p className="num text-[10px] uppercase tracking-wider text-slate/60">
                  {c.kind} · {c.source}
                </p>
              </div>
              {c.kind === 'boolean' && <Toggle c={c} onSignal={onSignal} />}
              {c.kind === 'number' && <Slider c={c} onSignal={onSignal} />}
              {c.kind === 'trigger' && <Trigger c={c} onSignal={onSignal} />}
              {c.kind === 'string' && <TextField c={c} onSignal={onSignal} />}
              {c.kind === 'enum' && <EnumField c={c} onSignal={onSignal} />}
              {c.kind === 'unknown' && (
                <span className="num text-[11px] text-slate/60">type {c.rawType}</span>
              )}
            </li>
          ))}
        </ul>

        <p className="num mt-auto pt-5 text-[11px] text-slate/50">
          {signals} signal{signals === 1 ? '' : 's'} sent this session
          {vm.viewModelName && (
            <span className="ml-2 text-slate/40">· bound to {vm.viewModelName}</span>
          )}
        </p>
      </div>
    </div>
  );
}

export function ControlDeck() {
  const [active, setActive] = useState<Rig>(RIGS[0]!);
  const ref = useReveal<HTMLDivElement>();

  return (
    <section id="deck" className="relative border-t border-white/8">
      <div className="aurora" aria-hidden />
      <div ref={ref} className="reveal relative z-10 mx-auto max-w-6xl px-6 py-24">
        <p className="eyebrow">Drive it yourself</p>
        <h2 className="display mt-3 max-w-2xl text-[clamp(1.75rem,3.5vw,2.5rem)]">
          Generated assets ship with real controls.
        </h2>
        <p className="mt-4 max-w-xl text-[15px] leading-relaxed text-slate">
          This panel is not a mock-up of an interface. It asks the file what it exposes —
          across both of Rive&rsquo;s input systems — and builds a control for each one.
          Switch files and it rebuilds itself.
        </p>

        <div
          role="tablist"
          aria-label="Choose a rig"
          className="mt-8 inline-flex gap-1 rounded-xl border border-white/10 bg-white/5 p-1 backdrop-blur"
        >
          {RIGS.map((rig) => (
            <button
              key={rig.id}
              type="button"
              role="tab"
              aria-selected={rig.id === active.id}
              onClick={() => setActive(rig)}
              className={
                'rounded-lg px-4 py-2 text-[13px] font-medium transition-colors ' +
                (rig.id === active.id ? 'bg-paper text-void' : 'text-slate hover:text-paper')
              }
            >
              {rig.label}
            </button>
          ))}
        </div>

        {/* Keyed so switching rigs tears the canvas down rather than trying to
            swap a source the runtime does not treat as reactive. */}
        <div className="mt-8">
          <Deck key={active.id} rig={active} />
        </div>
      </div>
    </section>
  );
}
