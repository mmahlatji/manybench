# ManyBench

A local-first benchmarking and experimentation platform. ManyBench does not
implement its own benchmark engine — it orchestrates established ones, starting
with JMH for Java (the current MVP). Describe what you want to measure with a
`@bench` source comment; ManyBench handles the benchmarking machinery.

```java
// @bench physics-step
// @bench-param particles = [1000, 10000, 100000]
public static void step(int particles) { ... }
```

```
$ bench list
physics-step

$ bench run physics-step
manybench.generated.PhysicsStepBenchmark.physics_step  [particles=1000]   median 0.123 ms
manybench.generated.PhysicsStepBenchmark.physics_step  [particles=10000]  median 1.250 ms
```

## Requirements

- Python 3.10+
- `javac` and `java` on `PATH` (to build and run benchmarks)
- Network access on the first `bench run` (JMH jars are downloaded from Maven
  Central and cached under `~/.cache/manybench/jmh/`; override the location with
  `MANYBENCH_CACHE`)

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

### Annotating benchmarks

Add `@bench` comments to your Java source (only `//` line comments are
recognized).

```java
// @bench <name>                          marks the method below as a benchmark
// @bench-param <n> = [v1, v2, ...]       -> JMH @Param (setup scope)
// @bench-param <n> = gen(args)           -> value generated in @Setup
// @bench-fixture <name>                  (in a @bench block) references a fixture
// @bench-fixture <name>                  (before a method) defines a fixture
```

#### Parameters

```java
// @bench sort
// @bench-param size = [1000, 10000, 100000]
public static void sort(int[] data) { ... }
```

Each value combination becomes its own benchmark configuration (the Cartesian
product when multiple params are used).

#### Generators

Raw values can't describe complex inputs, so ManyBench supports generators:

```java
// @bench sort
// @bench-param size = [1000, 10000]
// @bench-param data = randomIntArray(size)
```

Built-in generators: `randomIntArray`, `sortedIntArray` (return `int[]`),
`randomIntList` (returns `List<Integer>`). Generated values are built in
`@Setup`.

#### Fixtures

Fixtures separate construction from measurement — setup is never timed with the
benchmarked routine. A fixture is a static factory method whose result is passed
to any target argument whose type matches the fixture's return type:

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

The fixture's parameters must match `@bench-param` names. The generated
benchmark builds the fixture in `@Setup(Level.Trial)` and only times the target
call.

## Limitations

Current deliberate limitations:

- Only single-line method declarations are parsed.
- Target methods must be `static`, unless a fixture supplies the receiver.
- `void` benchmarks are not `Blackhole`-guarded (dead-code elimination not yet
  defended against).
- Only plain-`javac`/Makefile projects are built today.

## Notes

- Generators are deterministic, not random: `randomIntArray` and `randomIntList`
  seed `java.util.Random` with a fixed value (42), so every run builds the same
  data.
- `@bench-param` value lists are auto-typed as `boolean`, `int`, `double`, or
  `String` only. Use a fixture when you need a `long` or another specific type.
- Run `bench` from the project root; detection uses the current working directory
  and reports "No Java project detected" from a subdirectory.
- Java sources must live under `src/` (or the project root) so `javac` can find
  them via `-sourcepath`.
- A build system is required to run benchmarks: javac projects need a `Makefile`.
  Gradle (`build.gradle`) and Maven (`pom.xml`) are detected but not yet used for
  building.
