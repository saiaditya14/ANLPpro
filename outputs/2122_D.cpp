#include <iostream>
#include <vector>
#include <queue>
#include <tuple>
#include <utility>

using namespace std;

const long long INF = 1e18;
const int C = 600; // Heuristic constant for time delta window

// State for priority queue
struct State {
    long long total_time;
    long long wait_time;
    int u;

    bool operator>(const State& other) const {
        if (total_time != other.total_time) {
            return total_time > other.total_time;
        }
        return wait_time > other.wait_time;
    }
};

void solve() {
    int n;
    int m;
    cin >> n >> m;

    vector<vector<pair<int, int>>> adj_input_order(n + 1);
    for (int i = 0; i < m; ++i) {
        int u, v;
        cin >> u >> v;
        adj_input_order[u].push_back({v, 0});
        adj_input_order[v].push_back({u, 0});
    }

    vector<vector<pair<int, int>>> adj(n + 1);
    vector<int> deg(n + 1, 0);
    for (int i = 1; i <= n; ++i) {
        deg[i] = adj_input_order[i].size();
        int edge_idx = 1;
        for(auto p : adj_input_order[i]) {
            adj[i].push_back({p.first, edge_idx++});
        }
    }

    vector<long long> min_t(n + 1, INF);
    vector<vector<long long>> min_w(n + 1, vector<long long>(C, INF));

    priority_queue<State, vector<State>, greater<State>> pq;

    min_t[1] = 0;
    min_w[1][0] = 0;
    pq.push({0, 0, 1});

    pair<long long, long long> ans = {INF, INF};

    while (!pq.empty()) {
        auto [t, w, u] = pq.top();
        pq.pop();

        if (min_t[u] == INF || t > min_t[u] + C) {
            continue;
        }
        int dt = t - min_t[u];
        if (dt >= C || w > min_w[u][dt]) {
            continue;
        }

        if (u == n) {
             if (t < ans.first || (t == ans.first && w < ans.second)) {
                ans = {t, w};
            }
        }
        
        if (t > ans.first) continue;

        // Option 1: Wait
        long long t_new_wait = t + 1;
        long long w_new_wait = w + 1;

        if (t_new_wait < min_t[u] + C) {
            int dt_new = dt + 1;
            if (w_new_wait < min_w[u][dt_new]) {
                min_w[u][dt_new] = w_new_wait;
                pq.push({t_new_wait, w_new_wait, u});
            }
        }

        // Option 2: Move
        if (deg[u] > 0) {
            int edge_idx_to_take = (t % deg[u]) + 1;
            int v = -1;
            for (const auto& edge : adj[u]) {
                if (edge.second == edge_idx_to_take) {
                    v = edge.first;
                    break;
                }
            }
            
            if (v != -1) {
                long long t_new_move = t + 1;
                long long w_new_move = w;

                if (t_new_move < min_t[v]) {
                    min_t[v] = t_new_move;
                    min_w[v][0] = w_new_move;
                    pq.push({t_new_move, w_new_move, v});
                } else {
                    int dt_new = t_new_move - min_t[v];
                    if (dt_new < C) {
                        if (w_new_move < min_w[v][dt_new]) {
                            min_w[v][dt_new] = w_new_move;
                            pq.push({t_new_move, w_new_move, v});
                        }
                    }
                }
            }
        }
    }
    
    cout << ans.first << " " << ans.second << endl;
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