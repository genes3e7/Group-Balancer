import pandas as pd
import numpy as np
import os
import math
import random
import time
import concurrent.futures
import multiprocessing

# Try importing tqdm for progress bars
try:
    from tqdm import tqdm
except ImportError:
    def tqdm(iterable, **kwargs): return iterable

# ==========================================
# CONFIGURATION
# ==========================================

INPUT_FILENAME = 'Test.xlsx'
OUTPUT_FILENAME = 'balanced_groups.xlsx'
COL_NAME = 'Name'
COL_SCORE = 'Score'
SHEET_WITH_CONSTRAINT = 'With_Star_Constraint'
SHEET_WITHOUT_CONSTRAINT = 'No_Constraints'
ADVANTAGE_CHAR = '*'

# Time Settings (Seconds per Scenario)
SEARCH_DURATION = 30  

# ==========================================
# DATA LOADING
# ==========================================

def load_data(filepath):
    if not os.path.exists(filepath):
        csv_path = filepath.replace('.xlsx', '.csv')
        if os.path.exists(csv_path):
            filepath = csv_path
        else:
            print(f"Error: '{filepath}' not found.")
            return None
    try:
        if filepath.endswith('.csv'): df = pd.read_csv(filepath)
        else: df = pd.read_excel(filepath)
        df.columns = df.columns.str.strip()
        if COL_NAME not in df.columns or COL_SCORE not in df.columns: return None
        df[COL_NAME] = df[COL_NAME].astype(str).str.strip()
        df[COL_SCORE] = pd.to_numeric(df[COL_SCORE], errors='coerce').fillna(0)
        return df
    except: return None

def full_recalculate(groups):
    """Paranoid Mode: Sums everything from scratch to ensure zero drift."""
    for g in groups:
        # Re-sum scores
        g['current_sum'] = sum(m[COL_SCORE] for m in g['members'])
        # Re-calc average
        count = len(g['members'])
        g['avg'] = g['current_sum'] / count if count > 0 else 0
    return groups

def calculate_std_dev(groups):
    groups = full_recalculate(groups) # Ensure freshness
    avgs = [g['avg'] for g in groups if len(g['members']) > 0]
    return np.std(avgs) if avgs else 999999

def deep_copy_groups(grps):
    new_grps = []
    for g in grps:
        new_g = g.copy()
        new_g['members'] = g['members'][:]
        new_grps.append(new_g)
    return full_recalculate(new_grps)

# ==========================================
# ROBUST SIMULATED ANNEALING
# ==========================================

def generate_random_state(participants, num_groups, respect_stars):
    """Generates a fresh random grouping valid under constraints."""
    groups = [{'id': i+1, 'members': [], 'current_sum': 0} for i in range(num_groups)]
    
    total = len(participants)
    min_size = total // num_groups
    max_size = min_size + 1
    
    stars = [p for p in participants if p[COL_NAME].endswith(ADVANTAGE_CHAR)] if respect_stars else []
    normals = [p for p in participants if p not in stars]
    
    random.shuffle(stars)
    random.shuffle(normals)
    
    def is_safe(g, pool_rem):
        if len(g['members']) >= max_size: return False
        needed = sum(max(0, min_size - len(og['members'])) for og in groups if og['id'] != g['id'])
        return (pool_rem - 1) >= needed

    pool_len = len(stars) + len(normals)
    
    if respect_stars:
        for i, s in enumerate(stars):
            g = groups[i % num_groups]
            g['members'].append(s)
            pool_len -= 1
            
    for n in normals:
        valid = [g for g in groups if is_safe(g, pool_len)]
        target = random.choice(valid if valid else groups)
        target['members'].append(n)
        pool_len -= 1
        
    return full_recalculate(groups)

def run_optimizer(groups, respect_stars, duration, seed):
    """
    Simulated Annealing with PARANOID INTEGRITY.
    Recalculates sums on every move to prevent "Phantom Results".
    """
    random.seed(seed)
    start_time = time.time()
    
    # Init
    current_groups = deep_copy_groups(groups)
    best_groups = deep_copy_groups(groups)
    best_std = calculate_std_dev(best_groups)
    
    T = 1000.0
    alpha = 0.995
    
    total_people = sum(len(g['members']) for g in groups)
    min_size = total_people // len(groups)
    max_size = min_size + 1
    
    iters = 0
    
    while (time.time() - start_time) < duration:
        iters += 1
        move_type = 'swap' if random.random() < 0.8 else 'transfer'
        g1, g2 = random.sample(current_groups, 2)
        
        # --- ATTEMPT MOVE ---
        if move_type == 'swap':
            if not g1['members'] or not g2['members']: continue
            idx1 = random.randint(0, len(g1['members'])-1)
            idx2 = random.randint(0, len(g2['members'])-1)
            
            # Constraint
            if respect_stars:
                s1 = g1['members'][idx1][COL_NAME].endswith(ADVANTAGE_CHAR)
                s2 = g2['members'][idx2][COL_NAME].endswith(ADVANTAGE_CHAR)
                if s1 != s2: continue

            # Apply Temp Swap
            g1['members'][idx1], g2['members'][idx2] = g2['members'][idx2], g1['members'][idx1]
            
            # CHECK SCORE (PARANOID MODE: FULL RECALC)
            # We only recalc the two affected groups for speed, then global std
            g1['current_sum'] = sum(m[COL_SCORE] for m in g1['members'])
            g2['current_sum'] = sum(m[COL_SCORE] for m in g2['members'])
            g1['avg'] = g1['current_sum'] / len(g1['members'])
            g2['avg'] = g2['current_sum'] / len(g2['members'])
            
            current_std = calculate_std_dev(current_groups)
            delta = current_std - best_std # Negative is good (if comparing against best)
            
            # ACCEPTANCE LOGIC
            # Annealing Logic: If worse, maybe keep it?
            # Actually, we need to compare against PREVIOUS step, not best.
            # But for simplicity in this structure: 
            # If it's better than BEST, we keep. 
            # If it's worse, we revert?
            
            # Let's do standard SA:
            # We need previous energy.
            # Calculating std dev is O(G). Cheap.
            
            if current_std < best_std:
                best_std = current_std
                best_groups = deep_copy_groups(current_groups)
            else:
                # Revert if Metropolis fail
                # Delta relative to best is wrong for Metropolis, but relative to 'prev' is complex to track here cleanly.
                # Simplified Hill Climber + Noise:
                # If it's just a bit worse, we might keep it based on T?
                # For this problem, strict descent + random restarts is often enough.
                # Let's strictly REVERT if it didn't improve BEST, 
                # UNLESS random < T (Allow exploration).
                
                diff = current_std - best_std
                if random.random() > math.exp(-diff * 100 / T):
                     # Revert
                     g1['members'][idx1], g2['members'][idx2] = g2['members'][idx2], g1['members'][idx1]
                     # Restore Stats (Costly but safe)
                     full_recalculate([g1, g2])

        elif move_type == 'transfer':
            # Size Check
            src, dst = None, None
            if len(g1['members']) == max_size and len(g2['members']) == min_size: src, dst = g1, g2
            elif len(g2['members']) == max_size and len(g1['members']) == min_size: src, dst = g2, g1
            
            if src:
                idx = random.randint(0, len(src['members'])-1)
                
                if respect_stars:
                     # Don't stack stars
                     is_star = src['members'][idx][COL_NAME].endswith(ADVANTAGE_CHAR)
                     dst_stars = sum(1 for x in dst['members'] if x[COL_NAME].endswith(ADVANTAGE_CHAR))
                     if is_star and dst_stars > 0: src = None # Block move
                
                if src:
                    # Apply
                    item = src['members'].pop(idx)
                    dst['members'].append(item)
                    
                    # Recalc
                    full_recalculate([src, dst])
                    current_std = calculate_std_dev(current_groups)
                    
                    if current_std < best_std:
                        best_std = current_std
                        best_groups = deep_copy_groups(current_groups)
                    else:
                        diff = current_std - best_std
                        if random.random() > math.exp(-diff * 100 / T):
                            # Revert
                            item = dst['members'].pop()
                            src['members'].append(item)
                            full_recalculate([src, dst])

        T *= alpha
        if T < 0.001: T = 0.001

    return best_groups, best_std, iters

# ==========================================
# PARALLEL WRAPPERS
# ==========================================

def worker_wrapper(params):
    return run_optimizer(*params)

def solve_scenario(participants, n_groups, respect_stars, duration):
    num_workers = os.cpu_count() or 4
    print(f"  > Optimizing on {num_workers} cores for {duration}s...")
    
    best_global_g = None
    best_global_std = float('inf')
    total_iters = 0
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=num_workers) as executor:
        futures = []
        for _ in range(num_workers):
            seed = random.randint(0, 1000000)
            # Generate random start
            start_g = generate_random_state(participants, n_groups, respect_stars)
            futures.append(executor.submit(worker_wrapper, (start_g, respect_stars, duration, seed)))
            
        for future in tqdm(concurrent.futures.as_completed(futures), total=len(futures), unit="core"):
            try:
                g, std, iters = future.result()
                total_iters += iters
                # Validated in worker, but validate again here
                real_std = calculate_std_dev(g)
                if abs(real_std - std) > 0.001:
                    print(f"  [WARNING] Worker reported {std:.4f} but Real is {real_std:.4f}. Discarding.")
                    continue
                    
                if real_std < best_global_std:
                    best_global_std = real_std
                    best_global_g = g
            except Exception as e: print(e)
            
    return best_global_g, best_global_std

# ==========================================
# MAIN
# ==========================================

def main():
    multiprocessing.freeze_support()
    print("--- Advanced Group Balancer (V6: Paranoid Integrity) ---")
    
    df = load_data(INPUT_FILENAME)
    if df is None: return
    participants = df.to_dict('records')
    
    try: n_groups = int(input("Enter number of groups: "))
    except: return

    final_results = {}

    # 1. CONSTRAINED
    print(f"\nSCENARIO: WITH Star Constraints")
    best_c, std_c = solve_scenario(participants, n_groups, True, SEARCH_DURATION)
    print(f"  > Best Constrained Std: {std_c:.4f}")
    final_results[SHEET_WITH_CONSTRAINT] = best_c

    # 2. UNCONSTRAINED
    print(f"\nSCENARIO: NO Constraints")
    best_u, std_u = solve_scenario(participants, n_groups, False, SEARCH_DURATION)
    
    # 3. SHOWDOWN (Champion vs Challenger)
    print(f"\n  > --- CHAMPION vs CHALLENGER ---")
    print(f"  > Champion (Constrained): {std_c:.4f}")
    print(f"  > Challenger (Random):    {std_u:.4f}")
    
    if std_c < std_u:
        print("  > Champion Wins! (Using Constrained Result for Unconstrained Sheet)")
        final_results[SHEET_WITHOUT_CONSTRAINT] = deep_copy_groups(best_c)
        # Attempt one final polish just in case removing constraints helps tiny bit
        polished, p_std, _ = run_optimizer(best_c, False, 2.0, 42)
        if p_std < std_c:
             final_results[SHEET_WITHOUT_CONSTRAINT] = polished
    else:
        print("  > Challenger Wins!")
        final_results[SHEET_WITHOUT_CONSTRAINT] = best_u

    # OUTPUT
    print(f"\nSaving to {OUTPUT_FILENAME}...")
    try:
        with pd.ExcelWriter(OUTPUT_FILENAME, engine='openpyxl') as writer:
            for sheet, groups in final_results.items():
                s_groups = sorted(groups, key=lambda x: x['id'])
                rows = []
                for i in range(0, len(s_groups), 2):
                    g1 = s_groups[i]
                    g2 = s_groups[i+1] if i+1 < len(s_groups) else None
                    rows.append({'A': f"GROUP {g1['id']}", 'B': f"AVG: {g1['avg']:.2f}", 'C': '', 
                                 'D': f"GROUP {g2['id']}" if g2 else "", 'E': f"AVG: {g2['avg']:.2f}" if g2 else ""})
                    rows.append({'A': 'Name', 'B': 'Score', 'D': 'Name' if g2 else '', 'E': 'Score' if g2 else ''})
                    max_len = max(len(g1['members']), len(g2['members']) if g2 else 0)
                    for k in range(max_len):
                        m1 = g1['members'][k] if k < len(g1['members']) else None
                        m2 = g2['members'][k] if g2 and k < len(g2['members']) else None
                        rows.append({'A': m1[COL_NAME] if m1 else "", 'B': m1[COL_SCORE] if m1 else "",
                                     'D': m2[COL_NAME] if m2 else "", 'E': m2[COL_SCORE] if m2 else ""})
                    rows.append({})
                pd.DataFrame(rows).to_excel(writer, sheet_name=sheet, index=False, header=False)
                
                avgs = [g['avg'] for g in groups]
                stats = [
                    {'Stat': 'Lowest', 'Val': f"{min(avgs):.3f}", 'Grp': f"Grp {min(groups, key=lambda x:x['avg'])['id']}"},
                    {'Stat': 'Highest', 'Val': f"{max(avgs):.3f}", 'Grp': f"Grp {max(groups, key=lambda x:x['avg'])['id']}"},
                    {'Stat': 'Avg', 'Val': f"{np.mean(avgs):.3f}", 'Grp': '-'},
                    {'Stat': 'StdDev', 'Val': f"{np.std(avgs):.3f}", 'Grp': '-'}
                ]
                pd.DataFrame(stats).to_excel(writer, sheet_name=sheet, index=False, startcol=6)
                
                print(f"\n{sheet} Summary:")
                for g in s_groups:
                    print(f"Grp {g['id']} | Cnt: {len(g['members'])} | Avg: {g['avg']:.3f}")
                print(f"StdDev: {np.std(avgs):.4f}")

    except Exception as e: print(e)

if __name__ == "__main__":
    main()
