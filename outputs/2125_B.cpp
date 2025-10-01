#include <iostream>
#include <numeric>      // For std::gcd
#include <algorithm>    // For std::max

// Function to solve a single test case
void solve() {
    long long a, b, k;
    std::cin >> a >> b >> k;

    // Calculate the greatest common divisor of a and b.
    long long g = std::gcd(a, b);

    // --- Check for Cost 1 ---
    // A cost of 1 is possible if we can find a single vector (dx, dy)
    // and a number of repetitions 'c' such that c * (dx, dy) = (a, b).
    // This implies (dx, dy) = (a/c, b/c), where c is a common divisor of a and b.
    // To satisfy the move constraints (dx <= k, dy <= k), we need a/c <= k and b/c <= k.
    // To maximize our chances, we should make a/c and b/c as small as possible,
    // which means choosing the largest possible c, i.e., c = gcd(a, b).
    // If the condition holds for c = gcd(a,b), a cost-1 solution exists.
    // Otherwise, it's impossible with one move.
    
    long long required_dx = a / g;
    long long required_dy = b / g;

    if (std::max(required_dx, required_dy) <= k) {
        std::cout << 1 << std::endl;
    } else {
        // --- Cost 2 ---
        // If a cost-1 solution is not possible, a cost-2 solution is always achievable.
        // We can use two vectors:
        // V1 = (gcd(a, k), 0) to cover the x-displacement.
        // V2 = (0, gcd(b, k)) to cover the y-displacement.
        // This construction always works and uses two distinct vectors.
        std::cout << 2 << std::endl;
    }
}

int main() {
    // Fast I/O
    std::ios_base::sync_with_stdio(false);
    std::cin.tie(NULL);

    int t;
    std::cin >> t;
    while (t--) {
        solve();
    }

    return 0;
}