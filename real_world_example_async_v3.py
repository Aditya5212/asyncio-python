"""
real_world_example_async_v3.py
--------------------------------
Async version v3 (production-focused improvements):
- Improvements over async_v2:
    - Introduces a download concurrency limit using `asyncio.Semaphore` to avoid
        overwhelming remote servers or saturating local resources.
    - Tunes the process pool size (`CPU_WORKERS`) based on available CPUs so
        image processing uses a reasonable number of worker processes.
- This version demonstrates practical controls you should add when moving
    from simple async examples toward production-quality code.

What this file demonstrates:
- Combining async downloads (httpx + aiofiles) with concurrency limits.
- Offloading CPU-bound work to a ProcessPoolExecutor with a tuned worker count.

Notes:
- Adjust DOWNLOAD_LIMIT and CPU_WORKERS for your environment; on some
    networks or servers, a smaller download concurrency is friendlier.
"""

import asyncio
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import aiofiles
import httpx
from PIL import Image

DOWNLOAD_LIMIT = 4
CPU_WORKERS = os.cpu_count() - 2


IMAGE_URLS = [
    "https://images.unsplash.com/photo-1516117172878-fd2c41f4a759?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1532009324734-20a7a5813719?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1524429656589-6633a470097c?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1530224264768-7ff8c1789d79?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1564135624576-c5c88640f235?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1541698444083-023c97d3f4b6?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1522364723953-452d3431c267?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1493976040374-85c8e12f0c0e?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1530122037265-a5f1f91d3b99?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1516972810927-80185027ca84?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1550439062-609e1531270e?w=1920&h=1080&fit=crop",
    "https://images.unsplash.com/photo-1549692520-acc6669e2f0c?w=1920&h=1080&fit=crop",
]


ORIGINAL_DIR = Path("original_images")
PROCESSED_DIR = Path("processed_images")


async def download_single_image(
    client: httpx.AsyncClient,
    url: str,
    img_num: int,
    semaphore: asyncio.Semaphore,
) -> Path:
    # Use a semaphore to limit the number of concurrent downloads. This
    # prevents saturating the network or overwhelming the remote server.
    async with semaphore:
        print(f"Downloading {url}...")
        ts = int(time.time())
        url = f"{url}?ts={ts}"  # Add timestamp to avoid caching issues

        response = await client.get(url, timeout=10, follow_redirects=True)
        response.raise_for_status()

        filename = f"image_{img_num}.jpg"
        download_path = ORIGINAL_DIR / filename

        async with aiofiles.open(download_path, "wb") as f:
            async for chunk in response.aiter_bytes(chunk_size=8192):
                await f.write(chunk)

        print(f"Downloaded and saved to: {download_path}")

        return download_path


async def download_images(urls: list) -> list[Path]:
    # Limit concurrent download tasks using a semaphore.
    dl_semaphore = asyncio.Semaphore(DOWNLOAD_LIMIT)
    async with httpx.AsyncClient() as client:
        async with asyncio.TaskGroup() as tg:
            tasks = [
                tg.create_task(
                    download_single_image(client, url, img_num, dl_semaphore)
                )
                for img_num, url in enumerate(urls, start=1)
            ]

        img_paths = [task.result() for task in tasks]

    return img_paths


def process_single_image(orig_path: Path) -> Path:
    save_path = PROCESSED_DIR / orig_path.name

    with Image.open(orig_path) as img:
        data = list(img.getdata())
        width, height = img.size
        new_data = []

        for i in range(len(data)):
            current_r, current_g, current_b = data[i]

            total_diff = 0
            neighbor_count = 0

            for dx, dy in [(1, 0), (0, 1)]:
                x = (i % width) + dx
                y = (i // width) + dy

                if 0 <= x < width and 0 <= y < height:
                    neighbor_r, neighbor_g, neighbor_b = data[y * width + x]
                    diff = (
                        abs(current_r - neighbor_r)
                        + abs(current_g - neighbor_g)
                        + abs(current_b - neighbor_b)
                    )
                    total_diff += diff
                    neighbor_count += 1

            if neighbor_count > 0:
                edge_strength = total_diff // neighbor_count
                if edge_strength > 30:
                    new_data.append((255, 255, 255))
                else:
                    new_data.append((0, 0, 0))
            else:
                new_data.append((0, 0, 0))

        edge_img = Image.new("RGB", (width, height))
        edge_img.putdata(new_data)
        edge_img.save(save_path)

    print(f"Processed {orig_path} and saved to {save_path}")
    return save_path


async def process_images(orig_paths: list[Path]) -> list[Path]:
    # Use a ProcessPoolExecutor with a tuned number of workers to process
    # images in parallel. This provides true CPU-bound parallelism.
    loop = asyncio.get_running_loop()

    with ProcessPoolExecutor(max_workers=CPU_WORKERS) as executor:
        tasks = [
            loop.run_in_executor(executor, process_single_image, orig_path)
            for orig_path in orig_paths
        ]

        processed_paths = await asyncio.gather(*tasks)

    return processed_paths


async def main():
    ORIGINAL_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    start_time = time.perf_counter()

    img_paths = await download_images(IMAGE_URLS)

    proc_start_time = time.perf_counter()

    processed_paths = await process_images(img_paths)

    finished_time = time.perf_counter()

    dl_total_time = proc_start_time - start_time
    proc_total_time = finished_time - proc_start_time
    total_time = finished_time - start_time

    print(
        f"\nDownloaded {len(img_paths)} images in: {dl_total_time:.2f} seconds. {(dl_total_time / total_time) * 100:.2f}% of total time",
    )
    print(
        f"Processed {len(processed_paths)} images in: {proc_total_time:.2f} seconds. {(proc_total_time / total_time) * 100:.2f}% of total time",
    )
    print(
        f"\nTotal execution time: {total_time:.2f} seconds. {(total_time / total_time) * 100:.2f}% of total time",
    )


if __name__ == "__main__":
    asyncio.run(main())


# ---------------------------------------------------------------------------
# Deep dive: TaskGroup, ProcessPoolExecutor, and asyncio.Semaphore
# ---------------------------------------------------------------------------
# This section explains why each primitive is used in this tutorial, where it
# appears in the code above, and practical guidance on how to use them.
#
# 1) asyncio.TaskGroup (structured concurrency)
# ------------------------------------------------
# Where used:
# - In `download_images` we create a TaskGroup and call `tg.create_task(...)`
#   for each download coroutine. TaskGroup also appears in other examples that
#   group related background work.
#
# Why it's used:
# - TaskGroup provides structured concurrency: tasks created by the group are
#   children of the group and are guaranteed to be awaited when the group
#   context manager exits. If an exception occurs in one child task, the
#   group cancels the remaining children and propagates the exception in a
#   controlled way.
# - This avoids the common pitfall of "fire-and-forget" tasks that become
#   unobserved and leak errors or resources.
#
# How it works (conceptually):
# - `async with asyncio.TaskGroup() as tg:` opens a scope.
# - `tg.create_task(coro)` schedules `coro` as a Task under the group.
# - When the `async with` block exits, the TaskGroup waits for all child
#   tasks to finish (or cancels them on error) and then continues.
#
# Practical tips:
# - Use TaskGroup when you have multiple related tasks whose lifetimes should
#   be bound together (download all files, then proceed to processing).
# - Prefer TaskGroup over ad-hoc lists of Tasks + `asyncio.gather` when you
#   want clearer exception propagation and automatic cancellation semantics.
# - TaskGroup is available in Python 3.11+. For older versions, use
#   `asyncio.gather` carefully and manage cancellations explicitly.
#
# 2) ProcessPoolExecutor (parallel CPU-bound work)
# --------------------------------------------------
# Where used:
# - In `process_images` we call `loop.run_in_executor(executor, process_single_image, orig_path)`
#   to run the CPU-bound image processing function in separate processes.
#
# Why it's used:
# - The image processing function is CPU-bound (heavy pixel operations). The
#   Python Global Interpreter Lock (GIL) prevents multiple threads from
#   executing Python bytecode in parallel, so threads do not give real CPU
#   parallelism for CPU-heavy tasks.
# - `ProcessPoolExecutor` runs workers in separate processes, bypassing the
#   GIL and enabling true parallel execution across CPU cores.
#
# How it works (conceptually):
# - Create a ProcessPoolExecutor (optionally with max_workers tuned to
#   available CPUs).
# - Use `loop.run_in_executor(executor, func, *args)` to submit work to the
#   pool. It returns an awaitable Future. Awaiting it suspends the coroutine
#   until the worker finishes and returns the result.
#
# Practical tips:
# - Choose `max_workers` carefully. A common heuristic is `max(1, cpu_count - 1)`
#   or similar; this code uses `os.cpu_count() - 2` to leave headroom.
# - Avoid passing very large objects between processes frequently — that
#   adds IPC serialization/deserialization overhead. Prefer paths/filenames
#   or small metadata and let the worker read files if needed.
# - For short-lived tiny CPU tasks the process startup/IPC overhead can
#   dominate; batching or using larger units of work is more efficient.
#
# 3) asyncio.Semaphore (limiting concurrency)
# --------------------------------------------
# Where used:
# - In `download_single_image` and `download_images` we create a semaphore
#   (`dl_semaphore = asyncio.Semaphore(DOWNLOAD_LIMIT)`) and use `async with
#   semaphore:` inside each download coroutine.
#
# Why it's used:
# - Even though async I/O lets you launch many coroutines concurrently, the
#   external world (remote servers, networks) and local resources (bandwidth,
#   sockets) are finite. A semaphore caps the number of concurrently active
#   downloads to a safe value, preventing overload.
# - It also acts as a polite client-side rate-limiter; many servers prefer
#   fewer parallel connections from a single client.
#
# How it works (conceptually):
# - `sem = asyncio.Semaphore(n)` creates a counter with capacity `n`.
# - `async with sem:` tries to acquire the semaphore; if the counter is
#   positive it decrements and enters the block immediately. If zero, the
#   coroutine waits until another holder releases it.
# - When the `async with` block exits, the semaphore is released (counter
#   increments), allowing another waiting coroutine to start.
#
# Practical tips:
# - Choose a download limit based on your bandwidth and the target server's
#   friendliness policy. Typical values are 4-10 for downloads, but this
#   depends heavily on the workload and environment.
# - You can combine Semaphores with backoff/retry logic for robust downloads
#   when network errors occur.
#
# Summary — how these pieces fit together in this project:
# - TaskGroup: groups and manages related coroutines (downloads/processes),
#   providing structured concurrency and better error handling.
# - Semaphore: limits concurrency for network-bound operations so you don't
#   overwhelm the network or the remote server.
# - ProcessPoolExecutor (via run_in_executor): offloads CPU-bound tasks to
#   separate processes to achieve real parallelism.
#
# Together they let this program:
# - Download many files efficiently without blocking the event loop.
# - Respect external resource limits with a semaphore.
# - Process images in parallel across CPU cores without blocking the loop.
#