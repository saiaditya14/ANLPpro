#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>
#include <queue>

// Function to solve a single test case
void solve() {
    int n;
    std::cin >> n;
    std::vector<long long> a(2 * n);
    for (int i = 0; i < 2 * n; ++i) {
        std::cin >> a[i];
    }

    if (n == 0) {
        std::cout << std::endl;
        return;
    }

    // ans[k] will store the answer for capacity k
    std::vector<long long> ans(n + 1);

    // Calculate ans[n] (unconstrained capacity)
    // The maximum sum is achieved by taking the n smallest times as entries
    // and the n largest times as exits.
    long long current_total_stay = 0;
    for (int i = 0; i < n; ++i) {
        current_total_stay -= a[i];
    }
    for (int i = n; i < 2 * n; ++i) {
        current_total_stay += a[i];
    }
    ans[n] = current_total_stay;

    // A boolean vector to track which set each time a[i] belongs to.
    // false for Entry set, true for Exit set.
    std::vector<bool> is_in_x_set(2 * n);
    for (int i = 0; i < n; ++i) {
        is_in_x_set[i] = false;
    }
    for (int i = n; i < 2 * n; ++i) {
        is_in_x_set[i] = true;
    }

    // Min-priority queue to find the smallest difference between adjacent
    // elements from different sets. Stores {difference, index_of_first_element}.
    std::priority_queue<std::pair<long long, int>, std::vector<std::pair<long long, int>>, std::greater<std::pair<long long, int>>> pq;
    
    // active[i] is true if the boundary (a[i], a[i+1]) is currently in the PQ.
    // This helps invalidate entries in the PQ lazily.
    std::vector<bool> active(2 * n - 1, false);

    if (n > 0) {
        pq.push({a[n] - a[n - 1], n - 1});
        active[n - 1] = true;
    }

    // Iteratively compute ans[k] for k from n-1 down to 1
    for (int k = n - 1; k >= 1; --k) {
        // Find the best swap to make by getting the minimum difference
        while (!pq.empty() && !active[pq.top().second]) {
            pq.pop();
        }

        if (pq.empty()) break; 

        std::pair<long long, int> top = pq.top();
        pq.pop();

        long long diff = top.first;
        int i = top.second;
        int j = i + 1;

        // The total stay decreases by 2 * difference
        current_total_stay -= 2 * diff;
        ans[k] = current_total_stay;

        active[i] = false;
        std::swap(is_in_x_set[i], is_in_x_set[j]);

        // After swapping sets for a[i] and a[j], the boundary at 'i' is gone.
        // New potential boundaries are at i-1 and j.
        
        // Check left of swapped pair (new boundary at i-1)
        if (i > 0) {
            int p = i - 1;
            if (is_in_x_set[p] != is_in_x_set[i]) { // New boundary formed
                pq.push({a[i] - a[p], p});
                active[p] = true;
            } else { // Boundary at p destroyed
                if (active[p]) {
                    active[p] = false;
                }
            }
        }
        
        // Check right of swapped pair (new boundary at j)
        if (j < 2 * n - 1) {
            int q = j + 1;
            if (is_in_x_set[j] != is_in_x_set[q]) { // New boundary formed
                pq.push({a[q] - a[j], j});
                active[j] = true;
            } else { // Boundary at j destroyed
                if(active[j]) {
                    active[j] = false;
                }
            }
        }
    }

    // Print results for k=1 to n
    for (int k = 1; k <= n; ++k) {
        std::cout << ans[k] << (k == n ? "" : " ");
    }
    std::cout << std::endl;
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