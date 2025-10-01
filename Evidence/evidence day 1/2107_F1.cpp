#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>

// Function to solve a single test case
void solve() {
    int n;
    std::cin >> n;
    std::vector<long long> a(n);
    for (int i = 0; i < n; ++i) {
        std::cin >> a[i];
    }

    // We use 0-based indexing for the vector `a` (indices 0 to n-1).
    // The problem uses 1-based indexing for cyclist positions (1 to n).
    // Cyclist at position k corresponds to index k-1.

    long long total_cost = 0;

    // Leo starts behind cyclist n and overtakes them in decreasing order of position: n, n-1, ..., 1.
    // We iterate k from n down to 1, representing the position Leo is about to clear.
    for (int k = n; k >= 1; --k) {
        // The index in our vector for the cyclist at position k is k-1.
        int current_k_idx = k - 1;

        long long min_step_cost = -1;
        int best_j_idx = -1;

        // At step k, Leo can choose to bring any cyclist from an available position j (1 <= j <= k)
        // to position k to overtake. The available cyclists are those at indices 0 to k-1.
        // We iterate through all possible choices for j.
        for (int j = 1; j <= k; ++j) {
            // The index for position j is j-1.
            int current_j_idx = j - 1;

            // The cost for choosing the cyclist at position j consists of two parts:
            // 1. Swap cost: to bring the cyclist from position j to k, which is (k-j).
            // 2. Overtake cost: the agility value of that cyclist, a[current_j_idx].
            long long current_step_cost = a[current_j_idx] + (k - j);
            
            // Find the minimum cost for this step and the corresponding index.
            if (best_j_idx == -1 || current_step_cost < min_step_cost) {
                min_step_cost = current_step_cost;
                best_j_idx = current_j_idx;
            }
        }
        
        // Add the minimum cost for this step to the total cost.
        total_cost += min_step_cost;
        
        // After making the decision, the state of the agilities array changes.
        // The cyclist with agility a[best_j_idx] is now "consumed" (overtaken).
        // The cyclist who was at position k is now at the position that the chosen cyclist came from.
        // This is equivalent to swapping the agilities at index best_j_idx and current_k_idx.
        // This updates the array for the next iteration (k-1).
        if (best_j_idx != current_k_idx) {
            std::swap(a[best_j_idx], a[current_k_idx]);
        }
    }
    
    std::cout << total_cost << std::endl;
}

int main() {
    // Fast I/O
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(NULL);

    int t;
    std::cin >> t;
    while (t--) {
        solve();
    }

    return 0;
}