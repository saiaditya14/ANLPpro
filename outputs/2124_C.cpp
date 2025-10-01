#include <iostream>
#include <vector>
#include <numeric>

// Function to compute the greatest common divisor
long long gcd(long long a, long long b) {
    while (b) {
        a %= b;
        std::swap(a, b);
    }
    return a;
}

// Function to compute the least common multiple
long long lcm(long long a, long long b) {
    if (a == 0 || b == 0) return 0;
    // To prevent overflow, calculate as (a / gcd(a, b)) * b
    if (a > 2000000000LL || b > 2000000000LL) { // Heuristic to avoid overflow with large numbers
         return (a / gcd(a, b)) * b;
    }
    return (a * b) / gcd(a, b);
}

void solve() {
    int n;
    std::cin >> n;
    std::vector<long long> b(n);
    for (int i = 0; i < n; ++i) {
        std::cin >> b[i];
    }

    // This approach is based on constructing one possible "beautiful" array 'a'
    // and from that, determining a candidate 'x'.
    // A simple way to construct a valid 'a' such that a_i | b_i for all i is
    // by using suffix GCDs. Let a_n = b_n and for i from n-1 down to 1,
    // let a_i = gcd(b_i, a_{i+1}). This ensures a_i | a_{i+1}.
    // By construction, a_i is a divisor of b_i.
    
    std::vector<long long> a(n);
    a[n - 1] = b[n - 1];
    for (int i = n - 2; i >= 0; --i) {
        a[i] = gcd(b[i], a[i + 1]);
    }

    // Now we have a valid beautiful array 'a' where each a_i | b_i.
    // The original a' must be such that b_i / a'_i is either 1 or x.
    // Our constructed 'a' might not be the true one. A potentially "truer"
    // 'a' could be a'_i = a_i / k_i for some integers k_i.
    // The ratios b_i / a'_i would be (b_i/a_i) * k_i.
    // The simplest assumption is that k_i = 1 for all i.
    // Then the ratios are r_i = b_i / a_i.
    // A candidate for x would be the LCM of all these ratios that are greater than 1.
    
    long long result_x = 1;
    for (int i = 0; i < n; ++i) {
        long long ratio = b[i] / a[i];
        result_x = lcm(result_x, ratio);
    }
    
    std::cout << result_x << std::endl;
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