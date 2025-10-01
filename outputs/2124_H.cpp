#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>

using namespace std;

// A simplified representation for the transitive closure matrix
// using vector<bool> for space efficiency.
using TC_Matrix = vector<vector<bool>>;

// Helper to count 'true' values in a TC matrix, used for finding the 'best' one.
int count_ones(const TC_Matrix& tc) {
    int count = 0;
    for (const auto& row : tc) {
        for (bool val : row) {
            if (val) {
                count++;
            }
        }
    }
    return count;
}

void solve() {
    int n;
    cin >> n;
    vector<int> a(n);
    for (int i = 0; i < n; ++i) {
        cin >> a[i];
    }

    if (n == 0) {
        cout << 0 << endl;
        return;
    }

    // dp[k][i] stores the TC matrix for a G.S. of length k ending at index i.
    // Using a pointer to avoid storing large objects directly and to represent non-existence with nullptr.
    vector<vector<unique_ptr<TC_Matrix>>> dp(n + 1, vector<unique_ptr<TC_Matrix>>(n));

    int max_len = 0;

    for (int i = 0; i < n; ++i) {
        // Base case: subsequences of length 1
        if (a[i] == 1) {
            dp[1][i] = make_unique<TC_Matrix>(1, vector<bool>(1, true));
            max_len = max(max_len, 1);
        }
    }

    for (int k = 2; k <= n; ++k) {
        for (int i = 0; i < n; ++i) {
            int v = a[i];
            if (v > k) {
                continue;
            }

            unique_ptr<TC_Matrix> best_tc_for_ik = nullptr;
            int min_ones = -1;

            for (int j = 0; j < i; ++j) {
                if (dp[k - 1][j]) {
                    const auto& tc_prev = *dp[k - 1][j];
                    
                    bool can_extend = true;
                    if (v > 1) {
                        for (int l = v; l < k; ++l) {
                            if (tc_prev[l - 1][v - 2]) { // 1-based to 0-based
                                can_extend = false;
                                break;
                            }
                        }
                    }

                    if (can_extend) {
                        auto tc_new = make_unique<TC_Matrix>(k, vector<bool>(k, false));
                        for(int r = 0; r < k - 1; ++r) {
                            for (int c = 0; c < k - 1; ++c) {
                                (*tc_new)[r][c] = tc_prev[r][c];
                            }
                        }
                        for(int r=0; r<k; ++r) (*tc_new)[r][r] = true;

                        // New reachabilities from vertex k
                        for (int w = 1; w < k; ++w) { // target vertex w
                            for (int l = v; l < k; ++l) { // via edge k->l
                                if (tc_prev[l-1][w-1]) {
                                    (*tc_new)[k-1][w-1] = true;
                                    break;
                                }
                            }
                        }
                        
                        int current_ones = count_ones(*tc_new);
                        if (!best_tc_for_ik || current_ones < min_ones) {
                            min_ones = current_ones;
                            best_tc_for_ik = move(tc_new);
                        }
                    }
                }
            }

            if (best_tc_for_ik) {
                dp[k][i] = move(best_tc_for_ik);
                max_len = max(max_len, k);
            }
        }
    }

    cout << max_len << endl;
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    int t;
    cin >> t;
    while (t--) {
        solve();
    }
    return 0;
}