# modules/algorithms.py
import random
import math
import time
import numpy as np
import copy
from modules import config

# --- HELPERS ---

def recalculate_sums(groups):
    for g in groups:
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
        new_g = g.copy() 
        new_g['members'] = g['members'][:]
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

# --- SMART LOGIC ---

def attempt_smart_swap(groups, respect_stars):
    """
    User Algorithm (Focused Extremes):
    1. Sort groups by Score Avg.
    2. ONLY check Top 3 Highest vs Bottom 3 Lowest.
    3. Find the single member pair that maximizes improvement.
    """
    sorted_indices = sorted(range(len(groups)), key=lambda k: groups[k]['avg'], reverse=True)
    
    # FOCUS: Top 3 vs Bottom 3
    high_candidates = sorted_indices[:3]
    low_candidates = sorted_indices[-3:]
    
    best_swap = None # (g_high_idx, g_low_idx, m_high_idx, m_low_idx)
    best_improvement = 0.0
    
    current_std = calculate_std_dev(groups)
    
    for h_idx in high_candidates:
        # Check against worst first
        for l_idx in reversed(low_candidates):
            if h_idx == l_idx: continue
            
            g_high = groups[h_idx]
            g_low = groups[l_idx]
            
            # Skip if gap is negligible
            if (g_high['avg'] - g_low['avg']) < 0.01:
                continue

            for idx_h, m_h in enumerate(g_high['members']):
                for idx_l, m_l in enumerate(g_low['members']):
                    
                    if m_h[config.COL_SCORE] <= m_l[config.COL_SCORE]:
                        continue
                        
                    if respect_stars:
                        s1 = str(m_h[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
                        s2 = str(m_l[config.COL_NAME]).endswith(config.ADVANTAGE_CHAR)
                        if s1 != s2: continue

                    avg_h_old = g_high['avg']
                    avg_l_old = g_low['avg']
                    
                    s_h_new = g_high['current_sum'] - m_h[config.COL_SCORE] + m_l[config.COL_SCORE]
                    s_l_new = g_low['current_sum'] - m_l[config.COL_SCORE] + m_h[config.COL_SCORE]
                    
                    avg_h_new = s_h_new / len(g_high['members'])
                    avg_l_new = s_l_new / len(g_low['members'])
                    
                    old_sse = avg_h_old**2 + avg_l_old**2
                    new_sse = avg_h_new**2 + avg_l_new**2
                    
                    improvement = old_sse - new_sse
                    
                    if improvement > 1e-6 and improvement > best_improvement:
                        best_improvement = improvement
                        best_swap = (h_idx, l_idx, idx_h, idx_l)
    
    if best_swap:
        h, l, mh, ml = best_swap
        m_h = groups[h]['members'][mh]
        m_l = groups[l]['members'][ml]
        groups[h]['members'][mh] = m_l
        groups[l]['members'][ml] = m_h
        recalculate_sums([groups[h], groups[l]])
        return True, groups
        
    return False, groups

# --- ENGINES ---

def run_local_search_descent(groups, respect_stars, max_iter=2000):
    for _ in range(max_iter):
        improved, groups = attempt_smart_swap(groups, respect_stars)
        if not improved: break
    return groups

def update_global_state(local_groups, local_std, is_constrained, shared_ns, locks):
    if not shared_ns: return
    
    updated = False
    if is_constrained:
        if local_std < shared_ns.best_a_score:
            with locks[0]: 
                if local_std < shared_ns.best_a_score:
                    shared_ns.best_a_score = local_std
                    shared_ns.best_a_groups = local_groups
                    updated = True
    if local_std < shared_ns.best_b_score:
        with locks[1]: 
            if local_std < shared_ns.best_b_score:
                shared_ns.best_b_score = local_std
                shared_ns.best_b_groups = local_groups
                updated = True
    return updated

def run_simulated_annealing(groups, respect_stars, duration, seed, shared_ns, locks, stop_event=None):
    random.seed(seed)
    start_time = time.time()
    
    best_groups = deep_copy_groups(groups)
    best_std = calculate_std_dev(best_groups)
    update_global_state(best_groups, best_std, respect_stars, shared_ns, locks)
    
    current_groups = deep_copy_groups(groups)
    
    T_MAX = 1000.0
    T_MIN = 0.01
    alpha = 0.99 
    T = T_MAX
    
    total_people = sum(len(g['members']) for g in groups)
    min_size = total_people // len(groups)
    max_size = min_size + 1
    
    while (time.time() - start_time) < duration:
        if stop_event and stop_event.is_set(): break
        
        # 1. SMART SWAP (Focused Extremes)
        improved, current_groups = attempt_smart_swap(current_groups, respect_stars)
        
        if improved:
            curr_std = calculate_std_dev(current_groups)
            if curr_std < best_std:
                best_std = curr_std
                best_groups = deep_copy_groups(current_groups)
                update_global_state(best_groups, best_std, respect_stars, shared_ns, locks)
            continue
            
        # 2. RANDOM TRANSFER (Topology Mutation)
        g1, g2 = random.sample(current_groups, 2)
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
                else:
                    diff = curr_std - best_std
                    if random.random() > math.exp(-diff * 100 / T):
                        # Revert
                        item = dst['members'].pop()
                        src['members'].append(item)
                        recalculate_sums([src, dst])
        
        T *= alpha
        if T < T_MIN: T = T_MAX 
            
    return best_groups, best_std
