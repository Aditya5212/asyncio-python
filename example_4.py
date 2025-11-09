import asyncio
import time
from concurrent.futures import ProcessPoolExecutor


def fetch_data(param):
    # This is a blocking, CPU or I/O-bound synchronous function. It uses
    # time.sleep which blocks the current thread for `param` seconds.
    print(f"Do something with {param}...", flush=True)
    time.sleep(param)  # BLOCKING if run in the event loop thread
    print(f"Done with {param}", flush=True)
    return f"Result of {param}"


async def main():
    # Example: offloading blocking work to threads using asyncio.to_thread
    # Execution flow (to_thread + create_task):
    # 1. asyncio.to_thread(fetch_data, 1) returns a coroutine that will run
    #    fetch_data in a separate thread when scheduled.
    # 2. asyncio.create_task schedules that coroutine as a Task on the event
    #    loop; the Task will start the background thread and return control
    #    to the loop immediately.
    # 3. awaiting the Task waits for the background thread to finish while
    #    allowing the event loop to run other tasks.
    #
    # Because the blocking `fetch_data` is run in worker threads, the event
    # loop is not blocked, and multiple thread-based tasks can overlap.
    task1 = asyncio.create_task(asyncio.to_thread(fetch_data, 1))
    task2 = asyncio.create_task(asyncio.to_thread(fetch_data, 2))

    result1 = await task1
    print("Thread 1 fully completed")
    result2 = await task2
    print("Thread 2 fully completed")

    # Example: offloading blocking work to a ProcessPoolExecutor
    # Execution flow (run_in_executor):
    # 1. loop.run_in_executor(executor, fetch_data, 1) schedules fetch_data to
    #    run in a separate process managed by the executor. It returns a
    #    Future/awaitable immediately.
    # 2. awaiting that future suspends the current coroutine until the
    #    separate process finishes, while the event loop keeps running.
    #
    # Using a process pool is useful to avoid GIL limitations for CPU-bound work.
    loop = asyncio.get_running_loop()

    with ProcessPoolExecutor() as executor:
        task1 = loop.run_in_executor(executor, fetch_data, 1)
        task2 = loop.run_in_executor(executor, fetch_data, 2)

        result1 = await task1
        print("Process 1 fully completed")
        result2 = await task2
        print("Process 2 fully completed")

    return [result1, result2]


if __name__ == "__main__":
    t1 = time.perf_counter()

    results = asyncio.run(main())
    print(results)

    t2 = time.perf_counter()
    print(f"Finished in {t2 - t1:.2f} seconds")


# ---------------------------------------------------------------------------
# Notes: event loop, coroutine objects, scheduling, and executors
# ---------------------------------------------------------------------------
#
# Key ideas shown in this file:
# - Blocking functions (like `fetch_data` using time.sleep) should NOT run on
#   the event loop's main thread because they block the loop and stop it from
#   scheduling other coroutines.
# - `asyncio.to_thread(func, *args)` is a convenient way to run a blocking
#   function in a background thread. It returns a coroutine; scheduling that
#   coroutine (with `create_task` or `await`) runs the function in a thread.
# - `loop.run_in_executor(executor, func, *args)` runs `func` in the provided
#   executor (thread or process), returning a Future/awaitable immediately.
#
# Coroutine objects and Tasks:
# - Calling an async function (e.g., `asyncio.to_thread(...)` or any
#   `async def` function) returns a coroutine object — a lazily-executable
#   awaitable. The coroutine does nothing until awaited or scheduled.
# - `await coro` runs the coroutine and suspends the current coroutine until
#   it completes.
# - `asyncio.create_task(coro)` wraps the coroutine in a Task and schedules it
#   to run on the event loop as soon as possible. The Task is itself
#   awaitable (you can `await task` to get its result). Creating a Task means
#   the coroutine's execution begins (subject to scheduling) without blocking
#   the creator.
#
# Why scheduling offloaded work matters:
# - Offloading blocking work (to threads/processes) keeps the event loop
#   responsive. While background workers are busy, the event loop can handle
#   I/O, timers, and other coroutines.
# - Use threads (to_thread or ThreadPoolExecutor) for I/O-bound blocking
#   functions where GIL contention isn't a problem. Use processes for CPU-bound
#   functions that need true parallelism (ProcessPoolExecutor).
#