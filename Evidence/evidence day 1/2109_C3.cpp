#include <iostream>
#include <string>
#include <vector>

// Helper function to send a command with a value and read the jury's response.
void query(const std::string& cmd, const std::string& val_str) {
    std::cout << cmd << " " << val_str << std::endl;
    int response;
    std::cin >> response;
    // Our constructed commands are guaranteed to succeed, so we don't need to check the response.
}

// Helper function to send a command without a value.
void query_no_val(const std::string& cmd) {
    std::cout << cmd << std::endl;
    int response;
    std::cin >> response;
}

void solve() {
    long long n;
    std::cin >> n;

    // Case 1: Optimal 5-command solution exists.
    // This is when n = 9*k for some 1 <= k <= 18.
    if (n % 9 == 0 && n >= 9 && n <= 162) {
        int k = n / 9;
        long long multiplier = 1;
        for (int i = 0; i < k; ++i) {
            multiplier *= 10;
        }
        multiplier -= 1;
        
        query_no_val("digit");
        query_no_val("digit");
        query_no_val("digit");
        query("mul", std::to_string(multiplier));
        query_no_val("digit");
    } 
    // Case 2: General 6-command solution (or 5 for n=9).
    else {
        // These 5 commands deterministically transform x to 9.
        query_no_val("digit");
        query_no_val("digit");
        query_no_val("digit");
        query("mul", "9");
        query_no_val("digit");
        
        // If the target is not 9, one more command is needed.
        if (n != 9) {
            query("add", std::to_string(n - 9));
        }
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