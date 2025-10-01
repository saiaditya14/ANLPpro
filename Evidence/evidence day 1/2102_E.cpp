#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>

// A large negative value to represent an unreachable state in DP
const long long INF = 1e18;

void solve() {
    int n;
    std::cin >> n;
    std::vector<int> a(n);
    for (int i = 0; i < n; ++i) {
        std::cin >> a[i];
    }

    // dp[k] will store the max beauty with k open intervals
    // We use two vectors to represent dp states at step i-1 and i
    std::vector<long long> prev_dp(n + 1, -INF);
    std::vector<long long> current_dp(n + 1, -INF);

    // Base case: before processing any element, 0 open intervals, beauty is 0
    prev_dp[0] = 0;

    // Iterate through each element of the array a
    for (int i = 1; i <= n; ++i) {
        int current_a = a[i - 1];
        std::fill(current_dp.begin(), current_dp.end(), -INF);

        for (int k = 0; k <= i; ++k) {
            // Case 1: The i-th element is a middle or unique occurrence.
            // The number of open intervals k remains k.
            current_dp[k] = prev_dp[k];

            // Case 2: The i-th element is a start point.
            // The number of open intervals becomes k from k-1.
            // This requires assigning value k, so a[i-1] must be at least k.
            if (k > 0 && current_a >= k) {
                if (prev_dp[k - 1] > -INF + 1e9) { // Check if state is reachable
                    current_dp[k] = std::max(current_dp[k], prev_dp[k - 1] - i);
                }
            }
            
            // Case 3: The i-th element is an end point.
            // The number of open intervals becomes k from k+1.
            // We can always close one of the open intervals (e.g., value 1),
            // since a[i-1] >= 1.
            if (k + 1 <= i) { // k+1 must be a valid state from previous step
                if (prev_dp[k + 1] > -INF + 1e9) { // Check if state is reachable
                    current_dp[k] = std::max(current_dp[k], prev_dp[k + 1] + i);
                }
            }
        }
        prev_dp = current_dp;
    }

    // The final answer is when all intervals are closed (k=0)
    std::cout << prev_dp[0] << std::endl;
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