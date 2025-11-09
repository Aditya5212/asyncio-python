import time


def fetch_data(param):
    # This is a synchronous blocking function.
    # Calling time.sleep blocks the entire thread (and thus the whole program)
    # for `param` seconds. No other Python code runs while sleeping.
    print(f"Do something with {param}...")
    time.sleep(param)  # BLOCKING: halts the whole interpreter for `param` seconds
    print(f"Done with {param}")
    return f"Result of {param}"


def main():
    # Execution flow (synchronous):
    # 1. call fetch_data(1) -> blocks 1s
    # 2. after it returns, call fetch_data(2) -> blocks 2s
    # Total time ~ 1 + 2 = 3 seconds.
    result1 = fetch_data(1)
    print("Fetch 1 fully completed")
    result2 = fetch_data(2)
    print("Fetch 2 fully completed")
    return [result1, result2]


t1 = time.perf_counter()

results = main()
print(results)

t2 = time.perf_counter()
print(f"Finished in {t2 - t1:.2f} seconds")