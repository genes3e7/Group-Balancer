# modules/parallel_engine.py
import concurrent.futures
import multiprocessing
import os
import random
import time
import datetime
from modules import algorithms, config

try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable=None, **kwargs): 
        class DummyBar:
            def update(self, n=1): pass
            def set_postfix_str(self, s): print(s)
            def close(self): pass
            def __enter__(self): return self
            def __exit__(self, *args): pass
        return DummyBar()

def worker_wrapper(params):
    start_groups, respect_stars, duration, seed, shared_ns, locks, stop_event = params
    return algorithms.run_simulated_annealing(start_groups, respect_stars, duration, seed, shared_ns, locks, stop_event)

def solve_both_scenarios_parallel(participants, n_groups, duration):
    total_cores = os.cpu_count() or 4
    cores_constrained = max(1, total_cores // 2)
    cores_unconstrained = max(1, total_cores - cores_constrained)
    
    print(f"  > Launching Dual Parallel Search for {duration}s...")
    print(f"  > Resources: {cores_constrained} cores (Constrained) | {cores_unconstrained} cores (Unconstrained)")
    print(f"  > NOTE: Press Ctrl+C at any time to stop early.")
    
    manager = multiprocessing.Manager()
    shared_ns = manager.Namespace()
    shared_ns.best_a_score = 99999.0  
    shared_ns.best_b_score = 99999.0  
    shared_ns.best_a_groups = None
    shared_ns.best_b_groups = None
    
    locks = (manager.Lock(), manager.Lock())
    stop_event = manager.Event()
    
    # Tracking for "Time Since Last Change"
    last_best_a = 99999.0
    last_best_b = 99999.0
    time_last_change = time.time()
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=total_cores) as executor:
        futures = []
        for _ in range(cores_constrained):
            seed = random.randint(0, 1000000)
            start_g = algorithms.generate_random_state(participants, n_groups, True)
            futures.append(executor.submit(worker_wrapper, (start_g, True, duration, seed, shared_ns, locks, stop_event)))

        for _ in range(cores_unconstrained):
            seed = random.randint(0, 1000000)
            start_g = algorithms.generate_random_state(participants, n_groups, False)
            futures.append(executor.submit(worker_wrapper, (start_g, False, duration, seed, shared_ns, locks, stop_event)))
            
        start_time = time.time()
        try:
            with tqdm(total=duration, unit="s", bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt}s [{postfix}]") as pbar:
                while True:
                    elapsed = int(time.time() - start_time)
                    if elapsed > pbar.n: pbar.update(elapsed - pbar.n)
                    
                    sa = shared_ns.best_a_score
                    sb = shared_ns.best_b_score
                    
                    # Check for updates
                    if sa < last_best_a or sb < last_best_b:
                        time_last_change = time.time()
                        last_best_a = sa
                        last_best_b = sb
                    
                    time_since_change = int(time.time() - time_last_change)
                    
                    disp_a = f"{sa:.4f}" if sa < 1000 else "Init..."
                    disp_b = f"{sb:.4f}" if sb < 1000 else "Init..."
                    
                    pbar.set_postfix_str(f"Constr: {disp_a} | Unconstr: {disp_b} | Last Chg: {time_since_change}s ago")
                    
                    if all(f.done() for f in futures):
                        pbar.update(duration - pbar.n)
                        break
                    if elapsed > duration + 2: break
                    time.sleep(0.5)
                    
        except KeyboardInterrupt:
            print("\n  >>> KEYBOARD INTERRUPT DETECTED. SAVING... <<<")
            stop_event.set()

    print("\n  > Retrieving best states from Global Manager...")
    
    final_c = shared_ns.best_a_groups
    score_c = shared_ns.best_a_score
    final_u = shared_ns.best_b_groups
    score_u = shared_ns.best_b_score
    
    if final_c is None: final_c = []
    if final_u is None: final_u = []
            
    return final_c, score_c, final_u, score_u
