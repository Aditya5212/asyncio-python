import asyncio
import time


async def fetch_data(param):
    # A coroutine that simulates an I/O-bound operation using asyncio.sleep
    # `asyncio.sleep` is non-blocking: it tells the event loop "I won't run for
    # `param` seconds, please run other tasks meanwhile." The coroutine yields
    # control back to the event loop at that point.
    print(f"Do something with {param}...")
    await asyncio.sleep(param)  # NON-BLOCKING: yields control to the event loop
    print(f"Done with {param}")
    return f"Result of {param}"


async def main():
    # Important subtlety: calling `fetch_data(1)` returns a coroutine object,
    # but does NOT schedule it on the event loop by itself.
    #
    # Here `task1` and `task2` are plain coroutine objects. Because we `await`
    # them one after another, the event loop executes them sequentially:
    #   - Start coroutine task1 -> it runs until it hits `await asyncio.sleep(1)`
    #   - At that await point, the coroutine yields control; since nothing else
    #     is scheduled, the loop waits until the sleep completes (1s), then
    #     resumes the coroutine and it finishes.
    #   - After task1 completes, we `await task2` and the same happens for 2s.
    #
    # RESULT: behavior is sequential (total ~ 1 + 2 = 3 seconds), even though
    # the code uses `async`/`await`.
    task1 = fetch_data(1)  # coroutine object (NOT scheduled)
    task2 = fetch_data(2)  # coroutine object (NOT scheduled)

    # When we `await task1` we run the first coroutine to completion before
    # starting to await the second. This is why the example still takes ~3s.
    result1 = await task1
    print("Task 1 fully completed")
    result2 = await task2
    print("Task 2 fully completed")
    return [result1, result2]


# Measurements: asyncio.run creates an event loop and runs `main()` inside it.
t1 = time.perf_counter()

results = asyncio.run(main())
print(results)

t2 = time.perf_counter()
print(f"Finished in {t2 - t1:.2f} seconds")


# Execution diagram :
#
# Time 0s                         1s                         3s
# |------------------------------|---------------------------|
# fetch_data(1): [run -> sleep]----resume->finish
# fetch_data(2):                [run -> sleep]----resume->finish
#
# Because `task1` is awaited before `task2` is awaited, the sleeps do NOT
# overlap. The event loop is running, but there's nothing else scheduled to
# take advantage of the time while the first sleep is in progress. To make
# these overlap you must schedule both coroutines (for example with
# `asyncio.create_task` or by passing them directly to `asyncio.gather`).
#
# How to run concurrently (example):
#   task1 = asyncio.create_task(fetch_data(1))
#   task2 = asyncio.create_task(fetch_data(2))
#   await asyncio.gather(task1, task2)
#
# The above makes the sleeps overlap and the total time becomes roughly
# max(1, 2) = 2 seconds instead of 3.