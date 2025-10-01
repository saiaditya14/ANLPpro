#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>

void solve() {
    int n;
    std::cin >> n;
    std::vector<int> x(n);
    bool possible = true;
    for (int i = 0; i < n; ++i) {
        std::cin >> x[i];
    }

    if (x[0] != 1) {
        possible = false;
    }
    for (int i = 1; i < n; ++i) {
        if (x[i] < x[i-1] || x[i] > x[i-1] + 1) {
            possible = false;
            break;
        }
    }

    if (!possible) {
        std::cout << "NO\n";
        return;
    }

    std::vector<int> starts;
    starts.push_back(1);
    for (int i = 1; i < n; ++i) {
        if (x[i] > x[i - 1]) {
            starts.push_back(i + 1);
        }
    }

    std::vector<int> ends;
    for (size_t i = 0; i < starts.size() - 1; ++i) {
        ends.push_back(starts[i+1] - 1);
    }
    ends.push_back(n);

    std::vector<int> p(n);
    int k = ends.size();
    int current_val = n;

    for (int i = 0; i < k; ++i) {
        p[ends[i] - 1] = current_val--;
    }

    std::vector<bool> is_end(n + 1, false);
    for (int end_pos : ends) {
        is_end[end_pos] = true;
    }
    
    std::vector<int> remaining_indices;
    for (int i = 1; i <= n; ++i) {
        if (!is_end[i]) {
            remaining_indices.push_back(i);
        }
    }
    std::sort(remaining_indices.rbegin(), remaining_indices.rend());

    for (int idx : remaining_indices) {
        p[idx - 1] = current_val--;
    }
    
    std::cout << "YES\n";
    for (int i = 0; i < n; ++i) {
        std::cout << p[i] << (i == n - 1 ? "" : " ");
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