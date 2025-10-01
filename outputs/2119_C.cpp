#include <iostream>

void solve() {
    long long n, l, r, k;
    std::cin >> n >> l >> r >> k;

    if (n % 2 != 0) {
        // If n is odd, the array [l, l, ..., l] is the lexicographically smallest solution.
        // AND(l, l, ...) = l
        // XOR(l, l, ...) = l (since n is odd)
        // So a_k is always l.
        std::cout << l << std::endl;
    } else {
        // If n is even, for each bit, the count of set bits must be even and less than n.
        // The array [l, l, ..., l] is not a solution as c_b=n for bits set in l.
        // The lexicographically smallest array is likely of the form [l, ..., l, x, x].
        // This requires l & x = 0. We need the smallest x >= l in [l, r] satisfying this.
        // Since l > 0, l&l != 0, so x must be > l.
        // The smallest x > l such that l & x = 0 is the smallest power of 2 strictly greater than l.
        long long p2 = 1;
        while (p2 <= l) {
            p2 *= 2;
        }

        if (p2 <= r) {
            // A solution exists. The array is [l, ..., l, p2, p2].
            // n is large, so k <= n-2 is highly likely.
            // Note: Since n can be 10^18, n-2 is not small. But k is also up to 10^18.
            if (k <= n - 2) {
                std::cout << l << std::endl;
            } else {
                std::cout << p2 << std::endl;
            }
        } else {
            // If the smallest such x is out of range, no simple solution exists.
            // Assume no solution exists.
            std::cout << -1 << std::endl;
        }
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