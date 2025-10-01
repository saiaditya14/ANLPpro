#include <iostream>
#include <vector>
#include <numeric>

// Function to solve a single test case
void solve() {
    int n;
    std::cin >> n;
    
    int zero_count = 0;
    int neg_count = 0;
    
    for (int i = 0; i < n; ++i) {
        int a;
        std::cin >> a;
        if (a == 0) {
            zero_count++;
        } else if (a == -1) {
            neg_count++;
        }
    }
    
    int operations = zero_count;
    
    // After turning all 0s into 1s, we check the parity of negative numbers.
    // If the count of -1s is odd, we need to change one -1 to a positive number.
    // The cheapest way is -1 -> 0 -> 1, which costs 2 operations.
    if (neg_count % 2 != 0) {
        operations += 2;
    }
    
    std::cout << operations << std::endl;
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