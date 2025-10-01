#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>

void solve() {
    int n, k;
    std::cin >> n >> k;
    std::vector<int> a(n);
    for (int i = 0; i < n; ++i) {
        std::cin >> a[i];
    }

    if (2 * k <= n) {
        std::cout << "YES\n";
        return;
    }

    // Case 2: 2 * k > n
    int p = 0;
    while (p < n / 2 && a[p] == a[n - 1 - p]) {
        p++;
    }

    // The palindromic frame is a[0...p-1] and a[n-p...n-1]
    // The middle part is a[p...n-1-p]
    
    // If p >= k, we have a frame of size k on each side, which gives enough
    // flexibility to remove any element from the middle.
    // The middle part can be cleared to form a palindrome.
    if (p >= k) {
        std::cout << "YES\n";
        return;
    }
    
    // If p < k, we are constrained.
    // The elements from index p to k-1 are "stuck" on the left side
    // of the middle part, and n-k to n-1-p on the right.
    // These two segments must form a palindrome with each other.
    bool possible = true;
    int len_stuck = k - p;
    for (int i = 0; i < len_stuck; ++i) {
        if (a[p + i] != a[n - k + i]) {
            possible = false;
            break;
        }
    }

    if (possible) {
        std::cout << "YES\n";
    } else {
        std::cout << "NO\n";
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