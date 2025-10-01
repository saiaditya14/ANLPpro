#include <iostream>
#include <vector>

long long power(long long base, long long exp) {
    long long res = 1;
    base %= 998244353;
    while (exp > 0) {
        if (exp % 2 == 1) res = (res * base) % 998244353;
        base = (base * base) % 998244353;
        exp /= 2;
    }
    return res;
}

long long modInverse(long long n) {
    return power(n, 998244353 - 2);
}

const int MAX_2N = 400005;
long long fact[MAX_2N];
long long invFact[MAX_2N];

void precompute_factorials() {
    fact[0] = 1;
    for (int i = 1; i < MAX_2N; i++) {
        fact[i] = (fact[i - 1] * i) % 998244353;
    }
    invFact[MAX_2N - 1] = modInverse(fact[MAX_2N - 1]);
    for (int i = MAX_2N - 2; i >= 0; i--) {
        invFact[i] = (invFact[i + 1] * (i + 1)) % 998244353;
    }
}

long long nCr_mod_p(int n, int r) {
    if (r < 0 || r > n) {
        return 0;
    }
    return (((fact[n] * invFact[r]) % 998244353) * invFact[n - r]) % 998244353;
}

long long double_factorial(int m) {
    // Computes (2m-1)!! = (2m)! / (2^m * m!)
    if (m == 0) return 1;
    long long term1 = fact[2 * m];
    long long term2 = invFact[m];
    long long term3 = modInverse(power(2, m));
    return (((term1 * term2) % 998244353) * term3) % 998244353;
}

void solve() {
    int n, k;
    std::cin >> n >> k;

    if (k >= n) {
        std::cout << 0 << std::endl;
        return;
    }

    long long term1 = double_factorial(n);
    long long term2 = nCr_mod_p(n - 2, k - 1);
    
    long long ans = (term1 * term2) % 998244353;

    if (n > 2) {
        ans = (ans * 2) % 998244353;
    }

    std::cout << ans << std::endl;
}

int main() {
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(NULL);
    precompute_factorials();
    int t;
    std::cin >> t;
    while (t--) {
        solve();
    }
    return 0;
}