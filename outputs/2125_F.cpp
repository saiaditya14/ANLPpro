#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include <map>

using namespace std;

const long long INF = 1e18;
const string DOCKER = "docker";

// Calculates the cost to change s[i...i+5] to "docker"
int calculate_change_cost(const string& s, int i) {
    int cost = 0;
    for (int j = 0; j < 6; ++j) {
        if (s[i + j] != DOCKER[j]) {
            cost++;
        }
    }
    return cost;
}

// Segment Tree for Range Minimum Query
vector<long long> seg_tree;
vector<long long> costs_arr;
int seg_tree_size;

void build_seg_tree(int node, int start, int end) {
    if (start == end) {
        seg_tree[node] = costs_arr[start];
        return;
    }
    int mid = (start + end) / 2;
    build_seg_tree(2 * node, start, mid);
    build_seg_tree(2 * node + 1, mid + 1, end);
    seg_tree[node] = min(seg_tree[2 * node], seg_tree[2 * node + 1]);
}

long long query_seg_tree(int node, int start, int end, int l, int r) {
    if (r < start || end < l || l > r) {
        return INF;
    }
    if (l <= start && end <= r) {
        return seg_tree[node];
    }
    int mid = (start + end) / 2;
    long long p1 = query_seg_tree(2 * node, start, mid, l, r);
    long long p2 = query_seg_tree(2 * node + 1, mid + 1, end, l, r);
    return min(p1, p2);
}

void solve() {
    string s;
    cin >> s;
    int n;
    cin >> n;

    int len = s.length();
    int k_max = len / 6;

    vector<pair<int, int>> ranges(n);
    for (int i = 0; i < n; ++i) {
        cin >> ranges[i].first >> ranges[i].second;
    }

    if (k_max == 0) {
        cout << 0 << endl;
        return;
    }

    vector<int> change_costs;
    if (len >= 6) {
        for (int i = 0; i <= len - 6; ++i) {
            change_costs.push_back(calculate_change_cost(s, i));
        }
    }
    int m = change_costs.size();

    costs_arr.assign(k_max + 1, INF);
    costs_arr[0] = 0;

    vector<long long> prev_min_dp(m + 1, 0);

    for (int k = 1; k <= k_max; ++k) {
        vector<long long> current_dp(m + 1, INF);
        for (int i = 1; i <= m; ++i) {
            if (i >= 6 && prev_min_dp[i - 6] != INF) {
                current_dp[i] = change_costs[i - 1] + prev_min_dp[i - 6];
            }
        }
        
        vector<long long> current_min_dp(m + 1, INF);
        for (int i = 1; i <= m; ++i) {
            current_min_dp[i] = min(current_min_dp[i - 1], current_dp[i]);
        }

        costs_arr[k] = current_min_dp[m];
        prev_min_dp = current_min_dp;
    }

    map<int, int> diff;
    for (const auto& r : ranges) {
        int l = r.first;
        int R = r.second;
        if (l > k_max) continue;
        diff[l]++;
        if (R + 1 <= k_max) {
            diff[R + 1]--;
        }
    }

    int max_attendees = 0;
    int current_attendees = 0;
    if (n > 0) {
        int last_k = 0;
        for (auto const& [k_val, d] : diff) {
            if (k_val > k_max) break;
            if (k_val > last_k) {
                max_attendees = max(max_attendees, current_attendees);
            }
            current_attendees += d;
            last_k = k_val;
        }
        max_attendees = max(max_attendees, current_attendees);
    }
    
    long long min_cost_overall = INF;
    if (max_attendees == 0) {
        min_cost_overall = 0;
    } else {
        seg_tree_size = k_max + 1;
        seg_tree.assign(4 * seg_tree_size, INF);
        build_seg_tree(1, 0, seg_tree_size - 1);

        current_attendees = 0;
        int last_k = 0;
        for (auto const& [k_val, d] : diff) {
             if (k_val > k_max) break;
            if (k_val > last_k) {
                if (current_attendees == max_attendees) {
                    min_cost_overall = min(min_cost_overall, query_seg_tree(1, 0, seg_tree_size - 1, last_k, k_val - 1));
                }
            }
            current_attendees += d;
            last_k = k_val;
        }
        if(last_k <= k_max && current_attendees == max_attendees) {
             min_cost_overall = min(min_cost_overall, query_seg_tree(1, 0, seg_tree_size - 1, last_k, k_max));
        }
    }

    cout << min_cost_overall << endl;
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