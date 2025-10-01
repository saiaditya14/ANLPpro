#include <iostream>
#include <vector>
#include <numeric>

// Function to calculate Least Common Multiple (LCM) safely to avoid overflow.
long long lcm(long long a, long long b) {
    if (a == 0 || b == 0) return 0;
    if (a == 1) return b;
    if (b == 1) return a;
    long long common = std::gcd(a, b);
    // (a / common) * b is safer than (a * b) / common
    return (a / common) * b;
}

void solve() {
    int n;
    std::cin >> n;
    std::vector<long long> p(n), s(n);
    for (int i = 0; i < n; ++i) std::cin >> p[i];
    for (int i = 0; i < n; ++i) std::cin >> s[i];

    if (n == 1) {
        // For n=1, a_1 = p_1 and a_1 = s_1, so p_1 must equal s_1.
        if (p[0] == s[0]) {
            std::cout << "Yes\n";
        } else {
            std::cout << "No\n";
        }
        return;
    }

    // Check 1: Monotonicity of p (p_i must divide p_{i-1})
    for (int i = 1; i < n; ++i) {
        if (p[i - 1] % p[i] != 0) {
            std::cout << "No\n";
            return;
        }
    }

    // Check 2: Monotonicity of s (s_i must divide s_{i+1})
    for (int i = 0; i < n - 1; ++i) {
        if (s[i + 1] % s[i] != 0) {
            std::cout << "No\n";
            return;
        }
    }

    // Check 3: Global GCD (p_n must equal s_1)
    if (p[n - 1] != s[0]) {
        std::cout << "No\n";
        return;
    }

    // Check 4: Local constructibility at boundaries
    // For a_1 (0-indexed a_0)
    if (s[0] != std::gcd(p[0], s[1])) {
        std::cout << "No\n";
        return;
    }
    // For a_n (0-indexed a_{n-1})
    if (p[n - 1] != std::gcd(p[n - 2], s[n - 1])) {
        std::cout << "No\n";
        return;
    }
    
    // Check 5: Local constructibility for intermediate elements
    for (int i = 1; i < n - 1; ++i) {
        long long m_i = lcm(p[i], s[i]);
        if (p[i] != std::gcd(p[i - 1], m_i) || s[i] != std::gcd(m_i, s[i + 1])) {
            std::cout << "No\n";
            return;
        }
    }

    std::cout << "Yes\n";
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