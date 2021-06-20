import time
from .logger import *

start_times = {}
end_times = {}


def bench_start(name: str, parent: str = None):
    save_bench(start_times, time.time(), name, parent)


def bench_end(name: str, parent: str = None):
    save_bench(end_times, time.time(), name, parent)


def save_bench(timestamps_map: map, timestamp: float, name: str, parent: str = None):
    if parent:
        if parent not in timestamps_map:
            timestamps_map[parent] = {}
        timestamps_map[parent][name] = timestamp
    else:
        if name not in timestamps_map:
            timestamps_map[name] = {}
        timestamps_map[name]['root'] = timestamp
        

def print_bench():
    print("=== BENCHMARK TIMES RESULT ===")
    for key in start_times.keys():
        subkey = 'root'
        if (subkey not in start_times[key].keys()) \
                or (key not in end_times.keys() and subkey not in end_times[key].keys()):
            continue
        log(DEBUG, key + ": " + str(round(end_times[key][subkey] - start_times[key][subkey], 3)) + " seconds")
        for subkey in start_times[key].keys():
            if subkey == 'root' or subkey not in end_times[key].keys():
                continue
            log(DEBUG, " - " + subkey + ": " + str(round(end_times[key][subkey] - start_times[key][subkey], 3)) + " seconds")
    print("=== BENCHMARK TIMES RESULT ===")