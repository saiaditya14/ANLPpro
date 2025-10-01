#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>

void print_vector(const std::vector<long long>& v) {
    for (size_t i = 0; i < v.size(); ++i) {
        std::cout << v[i] << (i == v.size() - 1 ? "" : " ");
    }
    std::cout << std::endl;
}

void solve() {
    int n;
    std::cin >> n;
    std::vector<long long> a(n);
    long long total_sum = 0;
    for (int i = 0; i < n; ++i) {
        std::cin >> a[i];
        total_sum += a[i];
    }

    if (total_sum % 2 != 0) {
        std::cout << -1 << std::endl;
        return;
    }

    long long target_prefix_sum = total_sum / 2;
    long long current_prefix_sum = 0;
    for (int i = 0; i < n - 1; ++i) {
        current_prefix_sum += a[i];
        if (current_prefix_sum == target_prefix_sum) {
            std::cout << 1 << std::endl;
            print_vector(a);
            return;
        }
    }

    if (n == 3) {
        long long s_half = total_sum / 2;
        if (a[0] <= s_half && a[1] <= s_half && a[2] <= s_half) {
            long long x12 = s_half - a[2];
            long long x13 = s_half - a[1];
            long long x23 = s_half - a[0];
            
            std::cout << 3 << std::endl;
            std::vector<long long> b1 = {x12, x12, 0};
            std::vector<long long> b2 = {x13, 0, x13};
            std::vector<long long> b3 = {0, x23, x23};
            print_vector(b1);
            print_vector(b2);
            print_vector(b3);
            return;
        }
    }
    
    // A general 2-operation solution.
    // This is based on finding two basis vectors for the solution space.
    // We use b with split at index 1, and b with split at index n-1.
    // Let a = b + c.
    // b_1 = b_2 + ... + b_n
    // c_1 + ... + c_{n-1} = c_n
    // This gives a system of equations we can solve.
    std::cout << 2 << std::endl;
    long long s_half = total_sum / 2;
    
    // b satisfies prefix_sum(1) = suffix_sum(1)
    std::vector<long long> b(n);
    b[0] = s_half;
    b[1] = a[0] - s_half;
    for (int i = 2; i < n; ++i) {
        b[i] = a[i];
    }

    // c satisfies prefix_sum(n-1) = suffix_sum(n-1)
    std::vector<long long> c(n);
    for (int i = 0; i < n - 1; ++i) {
        c[i] = a[i] - b[i];
    }
    c[n - 1] = a[n - 1] - b[n - 1];

    print_vector(b);
    print_vector(c);
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