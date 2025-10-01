#include <iostream>

// Function to solve a single test case
void solve() {
    int n;
    std::cin >> n;
    
    long long total_operations = 0;
    
    for (int i = 0; i < n; ++i) {
        long long a, b, c, d;
        std::cin >> a >> b >> c >> d;
        
        // Case 1: Pile is a source of ones (b_i > d_i)
        // We must move all a_i zeros to access the b_i - d_i surplus ones.
        if (b > d) {
            total_operations += a + (b - d);
        } 
        // Case 2: Pile is not a source of ones (b_i <= d_i)
        // Check if it's a source of zeros.
        else if (a > c) {
            total_operations += a - c;
        }
    }
    
    std::cout << total_operations << std::endl;
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