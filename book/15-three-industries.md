# Chapter 15 — Three industries that change

So far the book has been about *what the framework does*. This
chapter is about *where it could matter*. I want to walk you
through three industries where the framework, if widely
adopted, could plausibly shift how the industry works — not
just helping individual practitioners, but reshaping how an
entire field does its business.

These are speculative. The framework today doesn't run any of
these industries. The case here is "*if the paradigm pans out
the way SQL did*, these are the three industries where the
economic gravity is strongest". One or two of them might
actually shift in this decade. The third might take longer.
All three are worth knowing about because they tell you what
kind of leverage the underlying paradigm has.

The three industries are:

1. **Power-grid reliability and capacity planning.**
2. **Catastrophe / reinsurance modelling.**
3. **Quantum error correction (specifically surface-code
   QEC).**

For each, I'll cover: what the industry does today, where the
framework fits, what changes if the framework wins, and what
the timeline looks like.

## 1. Power-grid reliability and capacity planning

### What the industry does today

Electric utilities — the companies that operate the high-
voltage transmission system that carries electricity from
power plants to your home — have to file reliability reports
with regulators. In the United States, the North American
Electric Reliability Corporation (NERC) sets the rules; state
public utility commissions (PUCs) enforce them. Similar
arrangements exist in Europe, the UK, and most other
developed economies.

The reports answer questions like: *what's the probability
that, given the current grid topology and component-level
failure rates, the grid fails to deliver power to every load
center in a given year?* Utilities use Monte Carlo simulators
— typically 5,000 to 50,000 lines of internal C++ — to
estimate these probabilities, report them with confidence
intervals, and justify capacity-planning investments.

Because the simulators are approximate, the utilities have to
build in safety margins. Over-engineering is the norm:
*"if the simulator says the failure probability is between 0.001
and 0.003, we'll plan for 0.005 to be safe"*. This safety
margin translates to billions of dollars per year of capacity
investment that may not be strictly necessary.

### Where the framework fits

Transmission grids are planar (they're drawn on geographic
maps; transmission lines follow rights-of-way that don't
generally cross each other). For planar graphs, the framework
computes failure probabilities exactly in polynomial time.
The Monte Carlo simulator's job is no longer needed.

The shift is dramatic for two reasons. First, the simulator
itself — tens of thousands of lines of specialised code — goes
away. Second, the safety margin goes away. Exact answers don't
need padding. Capacity investment can be retargeted from
"obviously safe" parts of the grid to "actually rare-tail-
heavy" parts.

### What changes

- **Capacity investments retarget.** US grid investment is
  roughly $120 billion per year. Conservative estimates of how
  much of this goes into safety-margin over-engineering on
  obviously-safe components are 5-15%. Retargeting that
  investment — pulling it from safe components and putting it
  into actually-rare-tail components — could be worth
  $6-18 billion per year in better-allocated capex.
- **Regulators get harder evidence.** A utility that can
  produce an *exact* failure probability with an auditable
  computation trail (the framework's workflow trace) has a
  much stronger regulatory position than one that produces
  MC ranges. Over time, regulators could start *requiring*
  exact methods for certain categories of analysis.
- **The reliability-engineering software industry consolidates.**
  Today there are dozens of competing reliability analysis
  products, each with its own simulator. In a framework-
  dominated future, most of the reliability-specific code
  vanishes; what's left is parsing, reporting, and integration.
  Two or three vendors are likely to dominate.

### Timeline

5-10 years. The first mover is likely Siemens, GE Power, ABB
(major grid-equipment vendors with embedded software
divisions), or a research utility consortium (e.g., EPRI in
the US). The fastest path is a single utility demonstrating
the cost savings on a real planning cycle and getting a
favourable regulator response.

If this happens, expect rapid copying across the industry —
nobody wants to be the utility filing MC-based reports when
the regulator now expects exact ones.

## 2. Catastrophe / reinsurance modelling

### What the industry does today

When you buy property insurance, your insurer cedes some of
the risk to a reinsurance company. The reinsurance company
needs to know how much risk it's taking on — specifically,
the probability of catastrophic losses across its portfolio
of treaties.

Three companies dominate the catastrophe modelling industry:
RMS (Risk Management Solutions, part of Moody's), AIR
Worldwide (Verisk), and EQECAT (CoreLogic). Each ships a
catastrophe modelling product that insurance companies and
reinsurers use to estimate tail losses (the worst-case
financial outcomes under hurricane, earthquake, flood, and
related hazards).

Each of these products has *millions of lines of C++* doing
Monte Carlo simulation. The simulator generates random
hazard events (a hurricane track, an earthquake epicentre),
overlays them on insured-property maps, sums up losses,
aggregates across millions of simulated events, and reports
tail percentiles.

The market for catastrophe modelling software is roughly
$1 billion per year globally. Reinsurance is a $400 billion
annual industry; catastrophe modelling is the analytical
backbone of the largest treaties.

### Where the framework fits

Earthquake hazard maps, hurricane wind-field maps,
flood-zone maps — these are all planar geographic
constructs. The exposed properties sit at points on the
plane. The losses are functions of distance and intensity.
The hazard-portfolio correlation structure has planar form.

For these planar pieces, exact tail-probability computation
is available in polynomial time. The Monte Carlo simulator —
the bulk of the catastrophe model's code — is unnecessary.

### What changes

- **Reinsurance treaty pricing tightens.** Today,
  reinsurance pricing has a substantial "model uncertainty"
  loading — extra premium charged because the model's
  estimates have confidence intervals. With exact methods,
  the model uncertainty piece shrinks. Some of that loading
  could pass back to insureds in lower premiums, some to
  reinsurers in higher margins, some to brokers in larger
  spreads.
- **Regulatory capital requirements (Solvency II) tighten.**
  Insurance regulators worldwide (especially in Europe under
  Solvency II) require insurers to hold capital against
  tail-loss scenarios. The capital requirement is based on
  model output. With exact methods, regulators could specify
  capital requirements more precisely.
- **The catastrophe-modelling software industry
  consolidates.** Like power-grid reliability, the
  catastrophe-model-specific code goes away. The remaining
  work — hazard data curation, exposure parsing, regulatory
  reporting — is much smaller. RMS / AIR / EQECAT either
  adopt the framework themselves or face competition from
  framework-native upstarts.

### Timeline

5-15 years. The reinsurance industry is conservative; it
takes a long time to change model standards. The path
forward is probably: a major reinsurer (Swiss Re, Munich Re)
adopts the framework internally for one specific peril
(say, US earthquake), demonstrates the analytical wins, and
the rest of the industry follows over the next decade.

## 3. Surface-code quantum error correction

### What the industry does today

Quantum computing is in an awkward transition phase.
Quantum hardware exists but is error-prone — every operation
on a quantum bit (qubit) introduces small errors. For
quantum computers to do useful work, those errors need to be
detected and corrected on the fly.

The leading approach is **surface code** error correction.
The idea is to encode each "logical" qubit using many
"physical" qubits (a typical surface-code implementation
uses 49 physical qubits per logical qubit). The physical
qubits are laid out on a 2D grid. Repeated measurements of
parity checks (called *stabilisers*) detect when an error
has occurred. A *decoder* — a piece of classical software
running alongside the quantum hardware — takes the
measurement record and decides which physical errors most
likely happened.

The decoder is the bottleneck. It has to run faster than
the quantum hardware introduces new errors. For
fault-tolerant quantum computing at useful scale, decoders
need to handle millions of stabiliser measurements per
second.

Today's decoders are largely heuristic — they make a best
guess and hope it's right. The state-of-the-art uses minimum-
weight perfect matching algorithms (yes, *those* matchings)
to find the most-likely error chain. Existing decoder
implementations are typically tens of thousands of lines of
optimised C++.

### Where the framework fits

The surface code's measurement record is, structurally, a
planar matching problem. The decoder's job is to find the
minimum-weight perfect matching in a planar graph whose nodes
are stabiliser-measurement outcomes. The framework's
`min_weight_matching` does exactly this, in `O(n^3)` time,
exactly.

Specialised research decoders exist that exploit this
matching structure. The framework's contribution would be to
make the matching engine available as a generic, well-tested,
maintained library — usable by any quantum-error-correction
team without requiring them to roll their own.

### What changes

- **Decoder development cycles shorten.** Today a quantum
  research team spending weeks tuning their custom matching
  decoder. With the framework, they call
  `sc.min_weight_matching(...)` and get a production-grade
  matching algorithm.
- **Decoder correctness becomes more provable.** The
  framework's audit trail tells you exactly what happened on
  each decode. Custom decoders have their own correctness
  arguments; using the framework's standardised one is
  simpler.
- **The quantum-computing software stack consolidates around
  shared primitives.** Just as classical software
  consolidated around `numpy` and `scipy`, quantum-computing
  software is consolidating around shared primitives. The
  framework's matching algorithms are exactly the kind of
  primitive that survives consolidation.

### Timeline

3-7 years. Quantum computing is moving faster than the other
two industries; the underlying hardware roadmaps (Google,
IBM, Quantinuum) target fault-tolerant systems in the early
2030s. By 2030 the decoder problem will be acute and
production-grade matching libraries will be in heavy demand.

The framework's `holant-tools` foundation includes specific
quantum-simulation primitives (`FreeFermionCircuit`,
matchgate-circuit simulation) and the matching infrastructure
is the same that surface-code decoders need. The connection
is direct.

## Why these three

I chose these three industries because each has the three
properties that make a paradigm shift economically rational:

1. **The exact answer matters financially or legally.**
   Power-grid capex decisions are billions of dollars;
   reinsurance premium loadings are billions of dollars per
   peril; quantum-computing decoder accuracy is what
   determines whether the whole field works.
2. **The relevant problem class is structurally suited.**
   Planar networks for power; planar geographic hazards for
   reinsurance; planar surface codes for QEC.
3. **There's a first-mover incentive.** A utility that can
   show exact-method reports gets regulatory advantage; a
   reinsurer that can price treaties with less model
   uncertainty wins business; a quantum-computing company
   with a production-grade decoder builds the most
   fault-tolerant hardware.

Other industries also have one or two of these properties.
Cloud SRE reliability has the technical fit but weaker
regulator incentive. Banking stress testing has regulator
incentive but mixed technical fit. Drug discovery has
varying technical fit. The three above are the cases where
all three converge cleanly.

## What this chapter taught you

1. The framework's paradigm has serious economic consequences
   in industries where Monte Carlo simulation is currently the
   default and the underlying problem is structurally planar.
2. Three specific industries — power-grid reliability,
   catastrophe reinsurance, surface-code QEC — are the most
   likely candidates for the framework's economic shift to
   actually transform daily practice.
3. The timelines are 5-15 years for industry-level shifts;
   the early-adopter wins are available much sooner (today).

The next chapter is about where the framework itself is going
— what's planned for the next decade of development, and how
the year-10 vision (where the 10-line form is literally one
line, behind a domain DSL) connects to the v1.x library
you can install today.
