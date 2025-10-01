#include <iostream>
#include <vector>
#include <numeric>
#include <cmath>

#if defined(__GNUC__) || defined(__clang__)
// Use GCC/Clang built-in function for counting leading zeros for performance.
#else
// Fallback for other compilers (e.g., MSVC).
#include <intrin.h>
long long __builtin_clzll(long long x) {
    unsigned long index;
    _BitScanReverse64(&index, x);
    return 63 - index;
}
#endif

// Finds the smallest integer x such that x >= val and (x & mask) == mask.
long long find_next_supermask(long long val, long long mask) {
    long long missing_bits = mask & ~val;
    if (missing_bits == 0) {
        return val;
    }

    // Find the position of the most significant missing bit.
    int k = 63 - __builtin_clzll(missing_bits);

    // Construct the smallest number > val that has bit k set and matches val's higher bits.
    // This is done by clearing the lower k+1 bits of val and adding 2^k.
    long long base = (val >> (k + 1)) << (k + 1);
    base += (1LL << k);

    // To satisfy the rest of the mask, we can simply OR with the mask.
    // The bits >= k in `base` will not be affected in a way that violates the mask.
    return base | mask;
}

void solve() {
    int n;
    std::cin >> n;
    std::vector<long long> a(n - 1);
    std::vector<long long> b(n);
    for (int i = 0; i < n - 1; ++i) {
        std::cin >> a[i];
    }
    for (int i = 0; i < n; ++i) {
        std::cin >> b[i];
    }

    // Using 0-based indexing for implementation convenience.
    std::vector<long long> c(n);
    if (n > 1) {
        c[0] = a[0];
        c[n - 1] = a[n - 2];
    }
    for (int i = 1; i < n - 1; ++i) {
        c[i] = a[i - 1] | a[i];
    }

    std::vector<long long> L(n);
    for (int i = 0; i < n; ++i) {
        L[i] = find_next_supermask(b[i], c[i]);
    }

    for (int i = 0; i < n - 1; ++i) {
        if ((L[i] & L[i + 1]) != a[i]) {
            std::cout << -1 << std::endl;
            return;
        }
    }

    long long total_ops = 0;
    for (int i = 0; i < n; ++i) {
        total_ops += L[i] - b[i];
    }
    std::cout << total_ops << std::endl;
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