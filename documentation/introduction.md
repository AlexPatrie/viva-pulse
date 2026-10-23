# Introduction

viva-pulse runs the [Kitware Pulse Physiology Engine](https://gitlab.kitware.com/physiology/engine),
a whole-body model of adult human physiology, inside
[process-bigraph](https://github.com/vivarium-collective/process-bigraph) simulations.

Pulse runs as an ordinary process-bigraph `Process`:

- **interventions** (a bleed, an infusion, a ventilator setting, the room temperature) are
  input ports;
- **readings** (vital signs, and the pressure, volume and flow in each region of Pulse's
  circuits) are output ports;
- a **simulation** is an ordinary composite document, built by a composite generator and run
  with `Composite.run`.

Nothing is reimplemented or mocked. Every number comes from Pulse's C++ engine, through
Pulse's own Python bindings. Because Pulse is a process-bigraph component, it can be wired
together with other processes, such as the MAP-targeted fluid controller in
{doc}`tutorials/01-hemorrhage-and-resuscitation`, and run as studies in the
[vivarium-workbench](https://github.com/vivarium-collective/vivarium-workbench)
({doc}`howto/run-studies-in-the-workbench`).

## What you can do with it

- Run a hemorrhage, with or without closed-loop fluid resuscitation, and watch the vital
  signs respond ({doc}`tutorials/01-hemorrhage-and-resuscitation`).
- Change one circuit's resistances and compliances and read the pressure, volume and flow of
  every region of that circuit ({doc}`tutorials/02-cardiovascular-circuit`).
- Run the airway circuit alone or coupled to the whole body, to separate what the circuit does
  from what the rest of the body does ({doc}`tutorials/03-respiratory-alone-or-coupled`).
- Put every circuit on one engine and watch an intervention in one show up in the others
  ({doc}`tutorials/04-every-circuit-on-one-engine`).
- Sweep a parameter, compare interventions, or repeat a scenario across Pulse's 21 shipped
  patients as workbench studies, with a record of every run ({doc}`results/pulse-hemorrhage`).

## How Pulse models the body

Pulse models physiology as lumped-parameter circuits, the same mathematics as electrical
circuits. The water-pipe analogy helps:

- **pressure** plays the role of voltage: what pushes the fluid along;
- **flow** plays the role of current: how much fluid moves per second;
- **resistance** is a narrowing that restricts flow; **compliance** is a vessel's
  stretchiness, which lets it store volume.

The cardiovascular, respiratory and thermal systems are each such a circuit, solved together
every 0.02 s of simulated time. {doc}`concepts/circuits` shows them.

## What it can't do

Pulse's Python bindings expose the engine through about fifteen methods: load or save a
state, process actions, advance time, and pull named data. They can't reach inside the
engine. So viva-pulse reads **regions** (Pulse compartments), not individual circuit nodes,
and changes resistances and compliances through Pulse's multiplier actions, not by
rewiring a circuit.
