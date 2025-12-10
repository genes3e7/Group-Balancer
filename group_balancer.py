# group_balancer.py
import multiprocessing
from modules import config, data_loader, algorithms, parallel_engine, output_manager

def main():
    multiprocessing.freeze_support()
    print("--- Advanced Group Balancer (Global State) ---")
    
    filepath = data_loader.get_file_path_from_user()
    participants = data_loader.load_data(filepath)
    if not participants: return

    try:
        n_groups = int(input("Enter number of groups: "))
        if n_groups < 1: return
    except:
        print("Invalid number.")
        return

    final_results = {}

    # 1. RUN PARALLEL ENGINE
    # The engine now handles the cross-updating via shared memory
    best_c, std_c, best_u, std_u = parallel_engine.solve_both_scenarios_parallel(
        participants, n_groups, config.SEARCH_DURATION
    )
    
    print(f"\n[RESULTS ANALYSIS]")
    print(f"  > Constrained Best Std: {std_c:.4f}")
    print(f"  > Unconstrained Best Std: {std_u:.4f}")

    # 2. Store Constrained (State A)
    # Safety Polish
    if best_c:
        polished_c = algorithms.run_local_search_descent(algorithms.deep_copy_groups(best_c), True, 2000)
        # Verify if polish helped or hurt
        if algorithms.calculate_std_dev(polished_c) < std_c:
            best_c = polished_c
            std_c = algorithms.calculate_std_dev(best_c)
    
    final_results[config.SHEET_WITH_CONSTRAINT] = best_c

    # 3. Handle Unconstrained (State B)
    # The State B should already contain the best result found by EITHER Constrained OR Unconstrained workers.
    # So we technically don't need to manually compare A vs B here, because the workers did it live!
    # But as a sanity check:
    
    if std_c < (std_u - 1e-9):
        print("  > [Sanity Check] Constrained result is better. Promoting to Unconstrained.")
        best_u = algorithms.deep_copy_groups(best_c)
        std_u = std_c
        
    # Safety Polish for Unconstrained
    if best_u:
        polished_u = algorithms.run_local_search_descent(algorithms.deep_copy_groups(best_u), False, 2000)
        if algorithms.calculate_std_dev(polished_u) < std_u:
            print("  > Polishing improved Unconstrained result.")
            best_u = polished_u
            
    final_results[config.SHEET_WITHOUT_CONSTRAINT] = best_u

    # 4. Output
    output_manager.save_results(final_results)

if __name__ == "__main__":
    main()
