#include <iostream>
#include <vector>
#include <algorithm>

void solve() {
    int n;
    std::cin >> n;
    
    std::vector<int> odds;
    std::vector<int> evens;
    
    for (int i = 0; i < n; ++i) {
        int val;
        std::cin >> val;
        if ((i + 1) % 2 != 0) { // 1-based odd indices
            odds.push_back(val);
        } else { // 1-based even indices
            evens.push_back(val);
        }
    }
    
    std::sort(odds.begin(), odds.end());
    std::sort(evens.begin(), evens.end());
    
    std::vector<int> result(n);
    int odd_idx = 0;
    int even_idx = 0;
    
    for (int i = 0; i < n; ++i) {
        if ((i + 1) % 2 != 0) { // 1-based odd indices
            result[i] = odds[odd_idx++];
        } else { // 1-based even indices
            result[i] = evens[even_idx++];
        }
    }
    
    for (int i = 0; i < n; ++i) {
        std::cout << result[i] << (i == n - 1 ? "" : " ");
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