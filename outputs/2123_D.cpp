#include <iostream>
#include <string>
#include <numeric>
#include <cmath>
#include <algorithm>

void solve() {
    int n;
    long long k;
    std::cin >> n >> k;
    std::string s;
    std::cin >> s;

    long long ones_count = 0;
    for (char c : s) {
        if (c == '1') {
            ones_count++;
        }
    }

    if (ones_count == 0) {
        std::cout << "Alice" << std::endl;
        return;
    }

    if (ones_count <= k) {
        std::cout << "Alice" << std::endl;
        return;
    }

    if (k == 1) {
        // With k=1, if there's more than one '1', Bob can always
        // counter Alice's move. Alice removes one '1', Bob adds one back.
        // Alice can't make progress.
        std::cout << "Bob" << std::endl;
        return;
    }

    // For k > 1 and ones_count > k:
    // Alice needs m = ceil(ones_count / k) moves.
    // Bob gets m-1 moves.
    // Alice wins if she can remove ones faster than Bob can add them.
    // Assuming Alice can prevent Bob from making a full +k move,
    // Alice wins if m*k >= C + (m-1)*(k-1)
    // which simplifies to m + k - 1 >= C
    long long m = (ones_count + k - 1) / k; // Equivalent to ceil(ones_count / k)
    if (m + k - 1 >= ones_count) {
        std::cout << "Alice" << std::endl;
    } else {
        std::cout << "Bob" << std::endl;
    }
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