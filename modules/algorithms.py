# modules/algorithms.py
import random
import math
import time
import numpy as np
import copy
from modules import config

# --- HELPERS ---

def recalculate_sums(groups):
    """Paranoid integrity check: Sums from scratch."""
    for g in groups:
        # Summing floats can have drift, but this is fresh every time
        g['current_sum'] = sum(float(m[config.COL_SCORE]) for m in g['members'])
        count = len(g['members'])
        g['avg'] = g['current_sum'] / count if count > 0 else 0.0
    return groups

def calculate_std_dev(groups):
    avgs = []
    for g in groups:
        s = sum(float(m[config.COL_SCORE]) for m in g['members'])
        c = len(g['members'])
        if c > 0:
            avgs.append(s/c)
    return np.std(avgs) if avgs else 999999.0

def deep_copy_groups(grps):
    new_grps = []
    for g in grps:
        new_g = g.copy() # dict copy
        new_g['members'] = g['members'][:] # list copy
        new_grps.append(new_g)
    return recalculate_sums(new_grps)

def generate_random_state(participants, num_groups, respect_stars):
    groups = [{'id': i+1, 'members': [], 'current_sum': 0} for i in range(num_groups)]
    
    stars = [p for p in participants if str(p[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)] if respect_stars else []
    normals = [p for p in participants if p not in stars]
    
    random.shuffle(stars)
    random.shuffle(normals)
    
    total = len(participants)
    min_size = total // num_groups
    max_size = min_size + 1
    
    def is_safe(g, pool_rem):
        if len(g['members']) >= max_size: return False
        needed = sum(max(0, min_size - len(og['members'])) for og in groups if og['id'] != g['id'])
        return (pool_rem - 1) >= needed

    pool_len = len(stars) + len(normals)
    
    if respect_stars:
        for i, s in enumerate(stars):
            groups[i % num_groups]['members'].append(s)
            pool_len -= 1
            
    for n in normals:
        valid = [g for g in groups if is_safe(g, pool_len)]
        target = random.choice(valid if valid else groups)
        target['members'].append(n)
        pool_len -= 1
        
    return recalculate_sums(groups)

# --- ENGINES ---

def run_local_search_descent(groups, respect_stars, max_iter=2000):
    """
    Hill Climbing Polish. 
    """
    groups = recalculate_sums(groups)
    start_score = calculate_std_dev(groups)
    
    for _ in range(max_iter):
        improved = False
        for i in range(len(groups)):
            for j in range(i+1, len(groups)):
                g1, g2 = groups[i], groups[j]
                curr_sse = g1['avg']**2 + g2['avg']**2
                
                for idx1, m1 in enumerate(g1['members']):
                    for idx2, m2 in enumerate(g2['members']):
                        if respect_stars:
                            s1 = str(m1[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
                            s2 = str(m2[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
                            if s1 != s2: continue
                            
                        s1_new = g1['current_sum'] - m1[config.COL_SCORE] + m2[config.COL_SCORE]
                        s2_new = g2['current_sum'] - m2[config.COL_SCORE] + m1[config.COL_SCORE]
                        avg1_new = s1_new / len(g1['members'])
                        avg2_new = s2_new / len(g2['members'])
                        
                        if (avg1_new**2 + avg2_new**2) < (curr_sse - 1e-8):
                            g1['members'][idx1], g2['members'][idx2] = m2, m1
                            g1['current_sum'], g2['current_sum'] = s1_new, s2_new
                            g1['avg'], g2['avg'] = avg1_new, avg2_new
                            improved = True
                            curr_sse = avg1_new**2 + avg2_new**2
                            break
                    if improved: break
                if improved: break
        if not improved: break
    return groups

def update_global_state(local_groups, local_std, is_constrained, shared_ns, locks):
    """Updates shared manager namespace safely."""
    if not shared_ns: return
    if is_constrained:
        if local_std < shared_ns.best_a_score:
            with locks[0]: # Lock A
                if local_std < shared_ns.best_a_score:
                    shared_ns.best_a_score = local_std
                    shared_ns.best_a_groups = local_groups
    if local_std < shared_ns.best_b_score:
        with locks[1]: # Lock B
            if local_std < shared_ns.best_b_score:
                shared_ns.best_b_score = local_std
                shared_ns.best_b_groups = local_groups

def run_simulated_annealing(groups, respect_stars, duration, seed, shared_ns, locks, stop_event=None):
    """
    Solver with Stop Event check.
    """
    random.seed(seed)
    start_time = time.time()
    
    best_groups = deep_copy_groups(groups)
    best_std = calculate_std_dev(best_groups)
    
    update_global_state(best_groups, best_std, respect_stars, shared_ns, locks)
    
    current_groups = deep_copy_groups(groups)
    
    T_MAX = 1000.0
    T_MIN = 0.001
    alpha = 0.9999 
    T = T_MAX
    
    total_people = sum(len(g['members']) for g in groups)
    min_size = total_people // len(groups)
    max_size = min_size + 1
    
    iters_since_improvement = 0
    
    while (time.time() - start_time) < duration:
        # --- INTERRUPT CHECK ---
        if stop_event and stop_event.is_set():
            break

        move_type = 'swap' if random.random() < 0.8 else 'transfer'
        g1, g2 = random.sample(current_groups, 2)
        
        # --- SWAP ---
        if move_type == 'swap':
            if not g1['members'] or not g2['members']: continue
            idx1 = random.randint(0, len(g1['members'])-1)
            idx2 = random.randint(0, len(g2['members'])-1)
            
            if respect_stars:
                s1 = str(g1['members'][idx1][config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
                s2 = str(g2['members'][idx2][config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
                if s1 != s2: continue

            g1['members'][idx1], g2['members'][idx2] = g2['members'][idx2], g1['members'][idx1]
            recalculate_sums([g1, g2])
            
            curr_std = calculate_std_dev(current_groups)
            
            if curr_std < best_std:
                best_std = curr_std
                best_groups = deep_copy_groups(current_groups)
                update_global_state(best_groups, best_std, respect_stars, shared_ns, locks)
                iters_since_improvement = 0
            else:
                diff = curr_std - best_std
                if random.random() > math.exp(-diff * 100 / T):
                    g1['members'][idx1], g2['members'][idx2] = g2['members'][idx2], g1['members'][idx1]
                    recalculate_sums([g1, g2])
                else:
                    iters_since_improvement += 1

        # --- TRANSFER ---
        elif move_type == 'transfer':
            src, dst = None, None
            if len(g1['members']) == max_size and len(g2['members']) == min_size: src, dst = g1, g2
            elif len(g2['members']) == max_size and len(g1['members']) == min_size: src, dst = g2, g1
            
            if src:
                idx = random.randint(0, len(src['members'])-1)
                
                if respect_stars:
                     is_star = str(src['members'][idx][config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
                     dst_stars = sum(1 for x in dst['members'] if str(x[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR))
                     if is_star and dst_stars > 0: src = None
                
                if src:
                    item = src['members'].pop(idx)
                    dst['members'].append(item)
                    recalculate_sums([src, dst])
                    
                    curr_std = calculate_std_dev(current_groups)
                    
                    if curr_std < best_std:
                        best_std = curr_std
                        best_groups = deep_copy_groups(current_groups)
                        update_global_state(best_groups, best_std, respect_stars, shared_ns, locks)
                        iters_since_improvement = 0
                    else:
                        diff = curr_std - best_std
                        if random.random() > math.exp(-diff * 100 / T):
                            item = dst['members'].pop()
                            src['members'].append(item)
                            recalculate_sums([src, dst])
                        else:
                            iters_since_improvement += 1
        
        T *= alpha
        if T < T_MIN: 
            T = T_MAX 
            
    return best_groups, best_std
