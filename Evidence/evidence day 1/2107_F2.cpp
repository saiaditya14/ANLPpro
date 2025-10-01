#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>
#include <queue>

void solve() {
    int n;
    std::cin >> n;
    std::vector<long long> a(n);
    for (int i = 0; i < n; ++i) {
        std::cin >> a[i];
    }

    std::priority_queue<long long> small; // max-heap
    std::priority_queue<long long, std::vector<long long>, std::greater<long long>> large; // min-heap

    long long small_sum = 0;
    long long large_sum = 0;

    for (int i = 0; i < n; ++i) {
        long long val = a[i] + (i + 1);

        // Insert new element
        if (small.empty() || val <= small.top()) {
            small.push(val);
            small_sum += val;
        } else {
            large.push(val);
            large_sum += val;
        }

        // Balance heaps
        if (small.size() > large.size() + 1) {
            large.push(small.top());
            large_sum += small.top();
            small_sum -= small.top();
            small.pop();
        } else if (large.size() > small.size()) {
            small.push(large.top());
            small_sum += large.top();
            large_sum -= large.top();
            large.pop();
        }

        long long median = small.top();
        long long cost = 0;
        cost += (median * small.size() - small_sum);
        cost += (large_sum - median * large.size());
        
        // Base cost from sum of a_j and adjustments
        // The total cost simplifies to sum |(a_j+j) - median|
        // The base sum part gets cancelled out in a complex way.
        // sum(a_j + k - p_k) = sum(a_j) + sum(k) - sum(p_k). But this is when we can choose permutation.
        // With median logic, the cost is sum |(a_j+j) - median_of_(a_k+k)|
        
        long long current_sum_indices = (long long)(i + 1) * (i + 2) / 2;
        long long base_sum_a = 0; // this part is complex
                                  // The problem reduces to finding sum |(a_j+j) - (median_val)|
                                  // where median_val is the median of {a_k+k}.
        std::cout << cost << (i == n - 1 ? "" : " ");
    }
    std::cout << "\n";
}

int main() {
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(NULL);
    int t;
    std::cin >> t;
    while (t--) {
        solve();
    }
    return 0;
}