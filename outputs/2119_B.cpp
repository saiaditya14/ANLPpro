#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>
#include <cmath>

// Fast I/O for performance
void fast_io() {
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(NULL);
}

void solve() {
    int n;
    std::cin >> n;
    long long px, py, qx, qy;
    std::cin >> px >> py >> qx >> qy;

    long long sum_a = 0;
    long long max_a = 0;
    for (int i = 0; i < n; ++i) {
        long long a;
        std::cin >> a;
        sum_a += a;
        if (a > max_a) {
            max_a = a;
        }
    }

    // Calculate the squared Euclidean distance required
    long long dx = px - qx;
    long long dy = py - qy;
    long long dist_sq = dx * dx + dy * dy;

    // Maximum possible displacement is the sum of all move lengths
    long long max_dist_possible = sum_a;
    long long max_dist_possible_sq = max_dist_possible * max_dist_possible;

    // Minimum possible displacement based on polygon inequality
    long long min_dist_possible = std::max(0LL, 2 * max_a - sum_a);
    long long min_dist_possible_sq = min_dist_possible * min_dist_possible;

    // Check if the required distance is within the achievable range
    if (dist_sq >= min_dist_possible_sq && dist_sq <= max_dist_possible_sq) {
        std::cout << "YES\n";
    } else {
        std::cout << "NO\n";
    }
}

int main() {
    fast_io();
    int t;
    std::cin >> t;
    while (t--) {
        solve();
    }
    return 0;
}