#include <iostream>
#include <string>
#include <algorithm>

// Function to solve a single test case
void solve() {
    int n, m;
    std::cin >> n >> m;

    // By symmetry, we can assume n <= m to simplify the conditions.
    if (n > m) {
        std::swap(n, m);
    }

    // Case 1: If either dimension is 1, there's only one path.
    // This path is trivially both greedy and maximal.
    // So, it's impossible to construct the required grid.
    if (n == 1) {
        std::cout << "NO\n";
        return;
    }

    // Case 2: For a 2x2 or 2x3 grid, a greedy path is always a maximal path.
    // A detailed analysis shows that a contradiction arises when trying
    // to construct a counterexample.
    if (n == 2 && (m == 2 || m == 3)) {
        std::cout << "NO\n";
        return;
    }

    // Case 3: For all other grids (e.g., n=2,m>=4 or n>=3,m>=3),
    // it is possible to construct a grid where the greedy choice
    // leads to a sub-optimal path.
    std::cout << "YES\n";
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