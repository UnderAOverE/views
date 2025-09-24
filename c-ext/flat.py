import timeit
import flatten
import flatten_nogil
import random

# Create a large list for testing
def create_data(num_items):
    data = []
    for i in range(num_items):
        data.append({"namespace": f"ns_{i}", "name": f"app_{i}", "version": f"v{i}"})
    return data

NUM_ITEMS = 1_000_000
data = create_data(NUM_ITEMS)

# Python version
def python_flatten():
    return [{item["namespace"]: {k: v for k, v in item.items() if k != "namespace"}} for item in data]

# C extension version
def c_flatten():
    return flatten.flatten(data)

# C extension no-GIL version
def c_flatten_nogil():
    return flatten_nogil.flatten(data)

# Time the executions
print("Pure Python:", timeit.timeit(python_flatten, number=1))
print("C Extension with GIL:", timeit.timeit(c_flatten, number=1))
print("C Extension without GIL:", timeit.timeit(c_flatten_nogil, number=1))
