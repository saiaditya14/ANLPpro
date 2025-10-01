#include <iostream>
#include <vector>
#include <numeric>

void solve() {
    int n;
    std::cin >> n;

    std::vector<int> p(n + 1);
    std::vector<bool> visited(n + 1, false);

    for (int i = 1; i <= n; ++i) {
        if (visited[i]) {
            continue;
        }

        std::vector<int> chain;
        long long curr = i;
        while (curr <= n) {
            chain.push_back(curr);
            visited[curr] = true;
            curr *= 2;
        }

        if (chain.size() == 1) {
            p[i] = i;
        } else {
            // All chains get a cyclic shift.
            // p[c_1] = c_2, p[c_2] = c_3, ..., p[c_k] = c_1
            for (size_t j = 0; j < chain.size() - 1; ++j) {
                p[chain[j]] = chain[j + 1];
            }
            p[chain.back()] = chain[0];
        }
    }

    for (int i = 1; i <= n; ++i) {
        std::cout << p[i] << (i == n ? "" : " ");
    }
    std::cout << std::endl;
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