#include <iostream>
#include <vector>
#include <string>
#include <numeric>
#include <algorithm>

using namespace std;

const long long INF = 4e18; // A value larger than any possible sum

void solve() {
    int n;
    long long k;
    cin >> n >> k;
    string s;
    cin >> s;
    vector<long long> a(n);
    int free_count = 0;
    for (int i = 0; i < n; ++i) {
        cin >> a[i];
        if (s[i] == '0') {
            free_count++;
        }
    }

    if (n == 0) {
        cout << "No\n";
        return;
    }

    // Precomputation
    // max_sum_ending_at[i]
    vector<long long> max_sum_ending_at(n);
    max_sum_ending_at[0] = a[0];
    for (int i = 1; i < n; ++i) {
        max_sum_ending_at[i] = max(a[i], a[i] + max_sum_ending_at[i - 1]);
    }

    // max_sum_starting_at[i]
    vector<long long> max_sum_starting_at(n);
    max_sum_starting_at[n-1] = a[n-1];
    for (int i = n - 2; i >= 0; --i) {
        max_sum_starting_at[i] = max(a[i], a[i] + max_sum_starting_at[i + 1]);
    }

    // max_sum_in_prefix[i] = max subarray sum in a[0...i]
    vector<long long> max_sum_in_prefix(n);
    max_sum_in_prefix[0] = max_sum_ending_at[0];
    for (int i = 1; i < n; ++i) {
        max_sum_in_prefix[i] = max(max_sum_in_prefix[i-1], max_sum_ending_at[i]);
    }

    // max_sum_in_suffix[i] = max subarray sum in a[i...n-1]
    vector<long long> max_sum_in_suffix(n);
    max_sum_in_suffix[n-1] = max_sum_starting_at[n-1];
    for (int i = n - 2; i >= 0; --i) {
        max_sum_in_suffix[i] = max(max_sum_in_suffix[i+1], max_sum_starting_at[i]);
    }


    if (free_count == 0) {
        if (max_sum_in_prefix[n-1] == k) {
            cout << "Yes" << endl;
            for (int i = 0; i < n; ++i) {
                cout << a[i] << (i == n - 1 ? "" : " ");
            }
            cout << endl;
        } else {
            cout << "No" << endl;
        }
        return;
    }

    int p = 0;
    while (p < n) {
        if (s[p] == '1') {
            p++;
            continue;
        }
        int q = p;
        while (q + 1 < n && s[q + 1] == '0') {
            q++;
        }

        long long l_sum = (p > 0) ? max(0LL, max_sum_ending_at[p - 1]) : 0;
        long long r_sum = (q < n - 1) ? max(0LL, max_sum_starting_at[q + 1]) : 0;
        
        long long max_l = (p > 0) ? max_sum_in_prefix[p - 1] : -INF;
        long long max_r = (q < n - 1) ? max_sum_in_suffix[q + 1] : -INF;

        if (max_l <= k && max_r <= k) {
            long long v = k - l_sum - r_sum;
            
            vector<long long> res_a = a;
            int len = q - p + 1;
            
            if (len == 1) {
                res_a[p] = v;
            } else {
                if (v >= 0) {
                    res_a[p] = v;
                    for (int i = p + 1; i <= q; ++i) res_a[i] = 0;
                } else { // v < 0
                    for (int i = p; i <= q; ++i) res_a[i] = v;
                }
            }
            
            cout << "Yes" << endl;
            for (int i = 0; i < n; ++i) {
                cout << res_a[i] << (i == n - 1 ? "" : " ");
            }
            cout << endl;
            return;
        }

        p = q + 1;
    }

    cout << "No" << endl;
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