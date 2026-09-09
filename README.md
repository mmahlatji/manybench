# PolyBench

A local-first benchmarking and experimentation platform. PolyBench does **not**
implement its own benchmark engine — it orchestrates established ones, starting with
**JMH** for Java.

Describe what you want to measure with a source comment; PolyBench handles the
benchmarking machinery.

```java
// @bench physics-step
// @bench-param particles = [1000, 10000, 100000]
public static void step(int particles) { ... }
```

```
$ bench list
physics-step

$ bench run physics-step
polybench.generated.PhysicsStepBenchmark.physics_step  [particles=1000]   median 0.123 ms
polybench.generated.PhysicsStepBenchmark.physics_step  [particles=10000]  median 1.250 ms
```

## Status

| Area | State |
|---|---|
| Core experiment model | ✅ implemented (`polybench/core/`) |
| Java adapter → JMH | ✅ implemented (Phase 1 MVP) |
| Rust / C++ / Python adapters | ⛔ Phase 5 |
| SQLite persistence, `bench history`/`compare`/`diff` | ⛔ Phase 2 |
| Profiling (`bench profile`) | ⛔ Phase 3 |
| Web UI | ⛔ Phase 4 |

The full design is in [`PROJECTSPEC.md`](PROJECTSPEC.md); the end-to-end flow is
documented in [`FLOW.md`](FLOW.md).

## Requirements

- Python 3.10+
- `javac` and `java` on `PATH` (to build and run benchmarks)
- Network access on the **first** `bench run` (JMH jars are downloaded from Maven
  Central and cached under `~/.cache/polybench/jmh/`; override the location with
  `POLYBENCH_CACHE`)

## Install

```bash
uv sync --extra dev          # or: pip install -e ".[dev]"
```

This installs the `bench` CLI.

## Usage

Run inside a Java project (any directory containing `.java` files).

```bash
bench list                      # discover benchmarks
bench run <name>                # run one benchmark
bench run <name> --format json  # machine-readable output
```

`bench run` options:

| Option | Default | Meaning |
|---|---|---|
| `--forks` | 1 | JMH forks |
| `--warmup-iterations` | 5 | warmup iterations |
| `--iterations` | 20 | measurement iterations |
| `--time-ms` | unset | per-iteration time in ms (JMH default is 10 s; pass a value for quick runs) |

## Annotating benchmarks

Add `@bench` comments to your Java source (only `//` line comments are recognized).

```java
// @bench <name>                          marks the method below as a benchmark
// @bench-param <n> = [v1, v2, ...]       -> JMH @Param (setup scope)
// @bench-param <n> = gen(args)           -> value generated in @Setup
// @bench-fixture <name>                  (in a @bench block) references a fixture
// @bench-fixture <name>                  (before a method) defines a fixture
```

### Parameters

```java
// @bench sort
// @bench-param size = [1000, 10000, 100000]
public static void sort(int[] data) { ... }
```

Each value combination becomes its own benchmark configuration (the Cartesian
product when multiple params are used).

### Generators

Raw values can't describe complex inputs, so PolyBench supports generators:

```java
// @bench sort
// @bench-param size = [1000, 10000]
// @bench-param data = randomIntArray(size)
```

Built-in generators: `randomIntArray`, `sortedIntArray` (→ `int[]`),
`randomIntList` (→ `List<Integer>`).

### Fixtures

Fixtures separate construction from measurement — the hard rule is that **setup is
never timed with the benchmarked routine**. A fixture is a static factory method
that builds the state passed to the benchmark:

```java
public class Physics {

    // @bench check-collisions
    // @bench-param particles = [1000, 10000]
    // @bench-param subSteps = [1, 2]
    // @bench-fixture createParticles
    public static void checkCollisions(List<Particle> particles, int subSteps) { ... }

    // @bench-fixture createParticles
    public static List<Particle> createParticles(int particles) { ... }
}
```

The fixture's parameters must match `@bench-param` names; its result is passed to
any target argument whose type matches the fixture's return type. The generated
benchmark builds the fixture in `@Setup(Level.Trial)` and only times the target call.

### Current limitations (deliberate)

- Only **single-line** method declarations are parsed.
- Target methods must be `static`, unless a fixture supplies the receiver (instance
  method called on the fixture).
- `void` benchmarks are not `Blackhole`-guarded (dead-code elimination not yet
  defended against).
- Only plain-`javac`/Makefile projects are built today (Gradle/Maven detection is
  present but not yet used for building).

## Development

```bash
uv sync --extra dev   # install deps
ruff check .          # lint
pytest                # run tests (skip the network/JDK test with: pytest -m "not e2e")
```

Sample javac project for tests lives in `tests/java_project/`.

## Architecture

PolyBench is split into two halves:

- **Core** (`polybench/core/`) — language-neutral model of experiments, parameters,
  fixtures, routines, runs, and results. It knows nothing about JMH.
- **Adapters** (`polybench/adapters/<lang>/`) — translate that model into a native
  framework. `JavaAdapter` (`polybench/adapters/java/`) handles detection, scanning,
  resolution, JMH code generation, build, run, and result parsing.

The contract between them is the `LanguageAdapter` ABC. See
[`FLOW.md`](FLOW.md) for a stage-by-stage trace of a `bench run`.
