import asyncio
import time


async def fetch_data(param):
    """Simulated I/O-bound coroutine.

    Note on execution flow:
    - When this function is called it returns a coroutine object immediately.
    - When run by the event loop, it executes until it hits `await asyncio.sleep(param)`.
      At that await the coroutine yields control to the event loop (non-blocking).
    - The event loop can then run other scheduled tasks while this one is sleeping.
    """
    print(f"Do something with {param}...")
    await asyncio.sleep(param)
    print(f"Done with {param}")
    return f"Result of {param}"


async def sequential():
    # Execution flow (sequential awaiting):
    # 1. await fetch_data(1) -> runs coroutine until sleep(1) and waits for it to finish
    # 2. after the first completes, await fetch_data(2) -> runs and waits
    # Total time ~ 1 + 2 = 3 seconds.
    t0 = time.perf_counter()
    r1 = await fetch_data(1)
    print("Fetch 1 fully completed")
    r2 = await fetch_data(2)
    print("Fetch 2 fully completed")
    t1 = time.perf_counter()
    print([r1, r2])
    print(f"Sequential finished in {t1 - t0:.2f} seconds")


async def concurrent_with_create_task():
    # Execution flow (create_task + gather):
    # 1. create_task schedules both coroutines immediately on the event loop.
    # 2. both coroutines run up to their first await and yield control (sleep).
    # 3. while both are sleeping, the event loop can switch between ready tasks.
    # 4. both completes independently and gather returns their results.
    # Result: sleeps overlap; total time roughly max(1,2) = ~2 seconds.
    t0 = time.perf_counter()
    # create_task schedules the coroutine to run on the event loop immediately
    task1 = asyncio.create_task(fetch_data(1))
    task2 = asyncio.create_task(fetch_data(2))

    # wait for both concurrently
    r1, r2 = await asyncio.gather(task1, task2)
    t1 = time.perf_counter()
    print([r1, r2])
    print(f"concurrent_with_create_task finished in {t1 - t0:.2f} seconds")


async def concurrent_with_gather_direct():
    # Execution flow (gather with coroutines): gather schedules the awaitables
    # for concurrent execution as well. Equivalent effect to create_task+gather
    # for these simple coroutines.
    t0 = time.perf_counter()
    # gather accepts awaitables and runs them concurrently
    r1, r2 = await asyncio.gather(fetch_data(1), fetch_data(2))
    t1 = time.perf_counter()
    print([r1, r2])
    print(f"concurrent_with_gather_direct finished in {t1 - t0:.2f} seconds")


async def main():
    print("--- Sequential (await coroutines one-by-one) ---")
    await sequential()

    print("\n--- Concurrent using create_task + gather ---")
    await concurrent_with_create_task()

    print("\n--- Concurrent using gather(fetch, fetch) ---")
    await concurrent_with_gather_direct()


if __name__ == "__main__":
    asyncio.run(main())


# ---------------------------------------------------------------------------
# Explanatory notes — coroutine objects, awaiting, and scheduling (event loop)
# ---------------------------------------------------------------------------
#
# Coroutine objects
# - When you call an async function (defined with `async def`) you DON'T run it.
#   Instead, Python returns a coroutine object (an awaitable). Example:
#     coro = fetch_data(1)
#   `coro` is a coroutine object. It's like a recipe for work — it won't execute
#   until the event loop runs it (by `await`ing it or scheduling it).
#
# Why coroutine objects must be awaited (or scheduled)
# - The event loop can only run coroutines that are awaited or scheduled as
#   Tasks. If you create a coroutine object and never await or schedule it,
#   nothing happens and the coroutine is never executed.
# - `await coro` tells the event loop: run this coroutine now and pause this
#   caller until it yields a result. During `await`, the coroutine may yield
#   control (at further await points) so the loop can run other tasks.
#
# Scheduling vs awaiting
# - `await coro`: runs the coroutine and suspends the current coroutine until
#   `coro` completes (or yields back control at awaits). If you `await` one
#   coroutine and only afterwards `await` another, they run sequentially.
# - `asyncio.create_task(coro)`: wraps the coroutine in a Task and schedules it
#   to run on the event loop as soon as possible. The call returns a Task
#   object immediately. The Task will start executing concurrently with the
#   code that created it (subject to the event loop scheduling).
#
# How create_task schedules coroutines (brief)
# - A Task is a wrapper around a coroutine and is itself an awaitable.
# - When you call `asyncio.create_task(coro)` inside a running event loop,
#   the loop adds the Task to its internal queue of ready tasks.
# - The loop will switch to that Task (run it) at the next opportunity. The
#   Task runs until it reaches an `await` expression, at which point it yields
#   control back to the loop and other ready tasks can run.
# - Because tasks are scheduled immediately, multiple tasks can be running
#   (or sleeping) concurrently from the perspective of the event loop — which
#   lets I/O-bound waits overlap.
#
# Practical takeaways
# - Use `await` when you want the current coroutine to wait for a result.
# - Use `asyncio.create_task` (or `gather`) to schedule coroutines to run
#   concurrently and let their waits overlap.
# - Never mix blocking calls like `time.sleep` inside coroutines — they block
#   the whole event loop; use `await asyncio.sleep(...)` for non-blocking delays.

