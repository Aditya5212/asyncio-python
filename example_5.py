import asyncio
import time


async def fetch_data(param):
    """Simple coroutine that simulates non-blocking I/O with asyncio.sleep.

    Calling `fetch_data(n)` returns a coroutine object. The coroutine only
    executes once the event loop runs it (by awaiting it or by scheduling it
    as a Task).
    """
    await asyncio.sleep(param)
    return f"Result of {param}"


async def main():
    # ------------------------------------------------------------------
    # Create Tasks Manually
    # ------------------------------------------------------------------
    # Execution flow:
    # 1. asyncio.create_task(fetch_data(1)) schedules the coroutine as a Task
    #    on the running event loop and immediately returns a Task object.
    # 2. The Task begins executing concurrently (subject to loop scheduling).
    # 3. awaiting the Task (await task1) suspends the current coroutine until
    #    that Task completes, while the event loop can run other tasks.
    #
    # Note: creating tasks for both fetches allows their sleeps to overlap.
    task1 = asyncio.create_task(fetch_data(1))
    task2 = asyncio.create_task(fetch_data(2))
    result1 = await task1
    result2 = await task2
    print(f"Task 1 and 2 awaited results: {[result1, result2]}")

    # ------------------------------------------------------------------
    # Gather Coroutines
    # ------------------------------------------------------------------
    # `asyncio.gather` accepts awaitables (coroutine objects or Tasks).
    # When passed raw coroutine objects, gather will schedule them to run
    # concurrently and return their results as a list. If you pass Tasks,
    # gather will await those Tasks (which are already scheduled).
    #
    # Execution flow (gather with coroutines):
    # 1. create coroutine objects with fetch_data(i)
    # 2. gather schedules both coroutines to run concurrently
    # 3. await gather -> suspends until all coroutines complete
    coroutines = [fetch_data(i) for i in range(1, 3)]
    results = await asyncio.gather(*coroutines, return_exceptions=True)
    print(f"Coroutine Results: {results}")

    # ------------------------------------------------------------------
    # Gather Tasks (explicit create_task + gather)
    # ------------------------------------------------------------------
    # If you create tasks explicitly and then pass them to gather, the tasks
    # are already scheduled; gather simply awaits their completion.
    tasks = [asyncio.create_task(fetch_data(i)) for i in range(1, 3)]
    results = await asyncio.gather(*tasks)
    print(f"Task Results: {results}")

    # ------------------------------------------------------------------
    # TaskGroup (Python 3.11+)
    # ------------------------------------------------------------------
    # `asyncio.TaskGroup` groups tasks and ensures they are awaited; it will
    # also propagate exceptions in a structured way. Tasks created via
    # tg.create_task(...) start running immediately and the context manager
    # waits for them to finish (or cancels them on error).
    async with asyncio.TaskGroup() as tg:
        results = [tg.create_task(fetch_data(i)) for i in range(1, 3)]
        # Inside the TaskGroup block the tasks are scheduled; when the
        # context manager exits it ensures all tasks are finished or
        # cancelled on failure.
    # TaskGroup tasks are Task objects, so to access their results we call
    # `task.result()` after they have completed.
    print(f"Task Group Results: {[result.result() for result in results]}")

    return "Main Coroutine Done"


t1 = time.perf_counter()

results = asyncio.run(main())
print(results)

t2 = time.perf_counter()
print(f"Finished in {t2 - t1:.2f} seconds")


# ---------------------------------------------------------------------------
# Additional explanation (coroutines, tasks, gather, TaskGroup)
# ---------------------------------------------------------------------------
#
# - Coroutine objects: calling an `async def` function returns a coroutine
#   object (an awaitable). The object is inert until the event loop runs it
#   (via `await`, `gather`, `create_task`, etc.).
#
# - `await`: runs the awaitable and suspends the current coroutine until the
#   awaited one yields a result. If you `await` coroutines sequentially they
#   run sequentially; to run them concurrently schedule them first (create
#   Tasks) or use `asyncio.gather`.
#
# - `asyncio.create_task(coro)`: wraps a coroutine in a Task and schedules it
#   to run on the event loop as soon as possible. The Task starts executing
#   independently; you can `await` the Task to get its result later.
#
# - `asyncio.gather(*awaitables)`: concurrently waits for a group of
#   awaitables (coroutines or Tasks) and returns their results in order. When
#   passed raw coroutine objects, gather schedules them as Tasks internally.
#
# - `asyncio.TaskGroup`: structured concurrency that groups tasks and ensures
#   proper cancellation and exception propagation. Tasks created inside a
#   TaskGroup are awaited when the group exits.
#
# Practical note: use `await asyncio.sleep(...)` in coroutines for non-blocking
# delays. Avoid `time.sleep(...)` in the event loop thread — use
# `asyncio.to_thread` or executors to offload blocking work.
#