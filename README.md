# asyncio-python — Practical Guide & Deep Dive

## Recommended Reading Order (Revision Path)

1. Concepts Primer (below) — Futures vs Tasks vs Coroutines vs Awaitables.
2. Minimal building blocks: Event Loop lifecycle, coroutine scheduling, state transitions.
3. Sequential vs concurrent examples: `example_1.py` (sync), `example_2.py` (why async can still be sequential), `example_2_fixed.py` (true concurrency).
4. Task orchestration patterns: `example_3.py` (create_task & gather), `example_5.py` (TaskGroup, gather with tasks/coroutines).
5. Offloading blocking work: `example_4.py` (threads + processes).
6. Real-world progression: `real_world_example_sync_v1.py` → async_v1 → async_v2 → async_v3.
7. Optimization & control: Semaphores, bounded parallelism, process pool tuning.
8. Decision guide & recipes (toward end of this README).

Use this order when revising; each step introduces only one or two new ideas.

## Overview

This repository demonstrates progressive approaches to parallelism and
concurrency in Python using a small image-download + image-processing
pipeline. The goal is pedagogical: start with a synchronous baseline and
incrementally show how to convert to async models and then to production -
friendly patterns.

- `real_world_example_sync_v1.py` — synchronous baseline (blocking I/O and
	sequential processing).
- `real_world_example_async_v1.py` — minimal async conversion using
	`asyncio.to_thread` and `TaskGroup` to offload blocking work while keeping
	most of the original code.
- `real_world_example_async_v2.py` — fully asynchronous downloads (httpx +
	aiofiles) and offloaded CPU-bound processing via `ProcessPoolExecutor`.
- `real_world_example_async_v3.py` — production-focused: download concurrency
	limits (Semaphore), tuned process pool size, and additional practical
	notes.

This README explains the key primitives used, why they were chosen, and how
to decide which approach fits your workload.

## Core Concepts (Deep Revision)

### Awaitable hierarchy
In Python, an object is awaitable if it implements the Awaitable protocol; three main categories:
1. Coroutine objects (result of calling an `async def` function.)
2. Tasks (wrapper around a coroutine scheduled on the event loop.)
3. Futures (low-level objects representing a promise-like eventual result.)

You can `await` any of these. Tasks & Futures provide lifecycle APIs; coroutine objects must be turned into Tasks or awaited directly exactly once.

### Coroutines & Coroutine Objects
`async def func(...)` defines a coroutine function. Calling it returns a coroutine object (not yet running). It runs only when:
- You `await` it directly (sequential execution in the current coroutine), OR
- You schedule it via `asyncio.create_task()` (concurrent execution managed by loop), OR
- You pass it to `asyncio.gather()`/TaskGroup which schedules/awaits it.
Important: A coroutine object can be awaited only once; re-awaiting after completion raises an error.

### Event Loop Lifecycle
1. Create/enter loop (e.g., `asyncio.run(main())` wraps loop creation & teardown).
2. Schedule initial coroutine (`main`).
3. Loop repeatedly:
	- Pick ready Tasks/Futures.
	- Run them until they hit an await point (yield) or complete.
	- Integrate I/O selectors, timers, callbacks.
4. Stop when the main coroutine finishes and no pending tasks remain (or when explicitly stopped).

### `await` Mechanics
`await expr` suspends the current coroutine until `expr` completes. While suspended, other ready tasks can run. Yield points include:
- `asyncio.sleep()`, network I/O via async libraries, `await task_or_future`, `await gather(...)`, `await to_thread(...)` (internally yields until thread result is ready).

### Future vs Task
- Future: low-level state machine (pending → done) with result/exception. Often created internally (e.g., in executors or low-level APIs).
- Task: subclass of Future that wraps a coroutine and drives its execution on the event loop. Provides cancellation and metadata (tracebacks, name in 3.8+). Use `create_task` to get concurrency.

### Cancellation Flow
- `task.cancel()` schedules a `CancelledError` to be thrown into the coroutine at its next await point.
- Properly structured coroutines catch and handle cancellation if cleanup needed.
- TaskGroup handles cancellation of sibling tasks automatically on error.

### Backpressure & Concurrency Control
Use Semaphores, bounded queues, or TaskGroups to prevent unlimited spawning. This stabilizes latency and resource usage.

### Common Pitfalls
| Pitfall | Cause | Fix |
|---------|-------|-----|
| Sequential awaits | Awaiting each coroutine before scheduling others | Use `create_task`, `gather`, TaskGroup |
| Blocking calls in coroutines | Using `time.sleep`, heavy CPU loops inline | Replace with `await asyncio.sleep`, offload to thread/process |
| Forgotten tasks | Creating tasks without awaiting or tracking | Use TaskGroup or gather; log and cancel on shutdown |
| Over-parallelism | Spawning thousands of tasks at once | Use semaphores / chunking |
| Re-awaiting coroutine | Awaiting same coroutine twice | Wrap once in Task or design single-consumer flow |

## Key Features & Patterns Referenced

1. Coroutines & coroutine objects — units of cooperative work; become runnable only when awaited or scheduled.

2. Event loop & `await` — orchestrates fairness & progress by switching at yield points; concurrency emerges from waiting, not threads.

3. `asyncio.create_task` / `asyncio.gather` — primary scheduling APIs for concurrency; gather offers batch structured waiting.

4. `asyncio.TaskGroup` — structured scope binding lifetimes & errors of sibling tasks; simplifies cancellation reliability.

5. `asyncio.to_thread` / `run_in_executor` — bridging blocking heritage code into async without rewrites.

6. `ProcessPoolExecutor` — true parallelism for CPU-bound tasks beyond GIL.

7. `asyncio.Semaphore` — deterministic upper bound on simultaneous operations (I/O, rate-limiting side effect).

8. Futures — low-level placeholders for eventual results; produced by executors, transport callbacks, or internal scheduling; seldom created manually.

9. Tasks — driving wrappers for coroutine execution; handle state, cancellation, result retrieval.

10. Cancellation — mechanism to propagate shutdown or timeouts; design idempotent cleanup.

11. Timeouts — use `asyncio.wait_for(task, timeout)` or shields for selective protection.

12. Shielding — `asyncio.shield()` prevents outer cancellation from immediately cancelling an inner operation (use sparingly for critical sections).

## Execution Model (Putting It Together)

Pseudo-timeline for a batch of downloads + processing:

```
T0: schedule N download tasks (create_task/gather/TaskGroup)
T0-Tn: each task runs until first await (network send), yields
Loop: interleaves ready tasks as data arrives; idle CPU cycles not wasted
Tn: all downloads complete → schedule processing tasks in process pool
Processing futures complete as workers finish; loop handles callbacks
Final: gather results, finalize, shut down cleanly
```

Key principle: concurrency emerges from overlapping wait times and parallel execution (process pool) rather than raw thread count.

## Deep Dive: TaskGroup, ProcessPoolExecutor, and asyncio.Semaphore

See `real_world_example_async_v3.py` for live usage. The following explains
each primitive in depth and when to use it.

### asyncio.TaskGroup

- What it is: structured concurrency API (Python 3.11+) that groups related
	tasks and awaits them as a unit.
- Why use it: it ensures tasks are not accidentally leaked and provides
	consistent cancellation behavior: if one child fails, the rest are
	cancelled and the exception is propagated.
- Where used: `download_images` uses a TaskGroup to schedule downloads so
	they are started together and awaited in a single, well-scoped block.
- Best practices:
	- Use TaskGroup when multiple tasks form a logical unit (e.g., download
		all images, then process them).
	- Prefer TaskGroup for clearer code and better error handling than
		`gather`+manual cancellation.

### ProcessPoolExecutor

- What it is: a pool of worker processes (not threads) to which you can
	submit CPU-bound functions.
- Why use it: Python's GIL prevents multi-threaded Python code from running
	in true parallelism; processes are independent interpreter instances and
	can run in parallel on separate CPU cores.
- Where used: `process_images` uses `loop.run_in_executor(executor, func, ...)`
	to run image processing in separate processes.
- Best practices:
	- Tune `max_workers` to number of cores (e.g., `cpu_count() - 1`), leaving
		headroom for the OS and other tasks.
	- Use process pools for long-running or CPU-heavy tasks to amortize IPC
		overhead.

### asyncio.Semaphore

- What it is: an async-compatible counter that limits concurrent access to a
	resource.
- Why use it: to cap concurrent downloads/requests so you don't overwhelm
	the network, the remote server, or local file descriptors.
- Where used: `download_single_image` acquires the semaphore before starting
	a download; `download_images` creates the semaphore with `DOWNLOAD_LIMIT`.
- Best practices:
	- Start with small limits (4-10) and adjust based on observed throughput
		and target server policies.
	- Combine semaphores with retry/backoff for robust download logic.

## Decision Guide (Choose the Right Tool)

1) Pure asyncio (non-blocking I/O) — use this when:
	 - Your workload is I/O-bound (network requests, many sockets, file I/O
		 that can be async), and you can use async libraries (httpx, aiofiles,
		 aiomysql, aioredis, etc.).
	 - You need high concurrency with low per-task memory/CPU overhead.

2) Thread-bound (use threads / `asyncio.to_thread` / ThreadPoolExecutor) —
	 use this when:
	 - You depend on blocking libraries that are I/O-bound but not async
		 (e.g., `requests`, certain database drivers).
	 - The work is I/O-heavy but uses libraries that release the GIL or block
		 on system calls.
	 - Threads are easier to integrate when you cannot refactor blocking code
		 to async.

3) Process-bound (ProcessPoolExecutor) — use this when:
	 - Work is CPU-bound (image/video processing, heavy numeric computation).
	 - You need true parallelism across multiple CPU cores and want to avoid
		 GIL contention.

### Trade-offs Summary
| Approach | Strengths | Weaknesses | Ideal Use |
|----------|-----------|------------|-----------|
| Asyncio | Low overhead I/O concurrency; structured patterns | Requires async libs; CPU-bound needs offload | High-volume network/file I/O |
| Threads | Easy integration with legacy blocking libs | GIL limits CPU parallelism; context-switch overhead | Blocking I/O libraries (requests) |
| Processes | True CPU parallelism; isolation | Higher startup & IPC cost | Heavy CPU transforms (image/video) |
| Hybrid | Best-of-both layered | Complexity (tuning, debugging) | Mixed I/O + CPU pipelines |

## Processes, Threads, CPU Cores — Fundamentals

- Process: independent OS-level memory space. Processes do not share Python
	interpreter state and thus bypass the GIL.
- Thread: lightweight execution context inside a process; multiple threads
	share memory but are subject to the GIL for Python bytecode execution.
- CPU core: hardware unit capable of executing instructions; use processes
	to utilize multiple cores for CPU-bound Python code.

Practical notes:
- Creating many processes has memory and IPC overhead; choose worker counts
	thoughtfully.
- Threads are low-overhead but don't give CPU parallelism for Python-bound
	CPU tasks because of the GIL.

## Optimization Strategies in Asyncio

- Asyncio relies on cooperative multitasking: coroutines yield control at
	`await` points (I/O, sleeps, etc.). The event loop schedules runnable
	tasks and switches between them when they yield.
- This model is efficient for I/O-bound workloads because while one
	coroutine waits for I/O, others can run without extra OS threads.

Key optimization levers:
- Use non-blocking I/O libraries (httpx, aiofiles) to avoid threads for
	network/disk-bound tasks.
- Offload CPU-bound work to processes to avoid blocking the event loop.
- Use semaphores and concurrency limits to avoid resource exhaustion and to
	provide predictable throughput.
- Batch small tasks where possible to amortize overhead.

## Real-Life Scenarios

- Web crawler / API harvester: use async HTTP client + semaphore to limit
	per-host concurrency; offload parsing or transformation to threads or
	processes if blocking or CPU-heavy.
- ETL pipeline that downloads files then processes them: async downloads
	(httpx + aiofiles) + ProcessPoolExecutor for heavy transforms (images,
	video encoding, data aggregation).
- Real-time dashboard or websocket server: asyncio to handle many concurrent
	connections with low latency; use background tasks for heavy work.

## Tackling Complex Optimization Problems with Asyncio

- Mixed workloads: many real systems combine I/O-bound and CPU-bound work.
	Asyncio offers a composition model where the event loop handles I/O
	concurrency and executors provide parallel CPU processing. This separation
	lets you tune each layer independently.
- Backpressure and resource control: semaphores, bounded queues, and
	TaskGroups allow you to implement backpressure, preventing overload and
	keeping latency predictable under load.
- Structured concurrency: TaskGroup (and similar patterns) helps manage
	lifecycles and error propagation for complex DAGs of tasks.

## Quick Recipes (Flash Cards)

- Make a blocking function async via thread-offload:

```py
result = await asyncio.to_thread(blocking_fn, *args)
```

- Run CPU work in a process pool and await results:

```py
loop = asyncio.get_running_loop()
with ProcessPoolExecutor(max_workers=workers) as ex:
		futures = [loop.run_in_executor(ex, cpu_fn, arg) for arg in args]
		results = await asyncio.gather(*futures)
```

- Limit concurrent downloads with a semaphore:

```py
sem = asyncio.Semaphore(8)
async def limited_download(...):
		async with sem:
				await download(...)
```

## Closing Notes & Revision Checklist

### Revision Checklist
Tick each mentally:
- Can I define the difference between coroutine object, Task, Future?
- Do I know how the event loop selects and advances tasks?
- Can I convert a blocking function using `to_thread`?
- Can I decide between threads vs processes for a workload?
- Do I know how to cap concurrency with a semaphore?
- Can I explain why sequential awaits lose concurrency?
- Do I understand cancellation and its impact on cleanup?

### Further Study
- Look into `asyncio.Streams`, `asyncio.Queue` for producer-consumer patterns.
- Explore tracing: `Task.get_coro()`, naming tasks, logging start/finish.
- Consider `anyio` / `trio` for alternative structured concurrency paradigms.

This repository is a learning path: start from the simple synchronous model
to understand blocking behavior, then progressively reduce blocking and
introduce concurrency safely. The combination of async I/O, Tasks/TaskGroup,
executors, and concurrency controls is a powerful toolbox for building
efficient Python applications that scale.

If you'd like, I can also add a short `BENCHMARK.md` or a small harness that
runs the different scripts and records timings on your machine.

