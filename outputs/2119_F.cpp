#include <iostream>
#include <vector>
#include <algorithm>
#include <queue>

using namespace std;

int n, st;
vector<int> w;
vector<vector<int>> adj;
vector<int> depth;
long long max_moves;

// Pre-calculates the depth of each node from the root (vertex 1)
void bfs_depth() {
    depth.assign(n + 1, -1);
    queue<int> q;

    q.push(1);
    depth[1] = 0;

    while (!q.empty()) {
        int u = q.front();
        q.pop();

        for (int v : adj[u]) {
            if (depth[v] == -1) {
                depth[v] = depth[u] + 1;
                q.push(v);
            }
        }
    }
}

// DFS to explore paths and stalling maneuvers
void solve_dfs(int u, int p, int t, long long life) {
    long long current_life = life + w[u];

    // Check death conditions
    if (depth[u] <= t || current_life <= 0) {
        return;
    }

    // Update max_moves for the simple path ending at u
    max_moves = max(max_moves, (long long)t);

    // Option 1: Stall at (u, v)
    for (int v : adj[u]) {
        // Check if a full u->v->u cycle is possible
        if (current_life + w[v] <= 0 || depth[v] <= t + 1) continue;
        if (current_life + w[v] + w[u] <= 0 || depth[u] <= t + 2) continue;

        // If a cycle is possible, calculate max number of cycles 'm'
        long long m_lava = 0;
        if (depth[u] > t + 1 && depth[v] > t) {
            m_lava = min((long long)depth[u] - t - 1, (long long)depth[v] - t) / 2;
        }
        if (m_lava <= 0) continue;

        long long m;
        long long weight_sum_cycle = w[u] + w[v];

        if (weight_sum_cycle >= 0) {
            m = m_lava;
        } else { // weight_sum_cycle is -2
            long long m_life = (current_life - 1) / 2;
            m = min(m_lava, m_life);
        }

        if (m > 0) {
            long long time_at_u_after_cycles = t + 2 * m;
            max_moves = max(max_moves, time_at_u_after_cycles);

            // Check if one last u->v move is possible
            long long life_at_u_after_cycles = current_life + m * weight_sum_cycle;
            if (life_at_u_after_cycles + w[v] > 0 && depth[v] > time_at_u_after_cycles + 1) {
                max_moves = max(max_moves, time_at_u_after_cycles + 1);
            }
        }
    }

    // Option 2: Extend simple path
    for (int v : adj[u]) {
        if (v != p) {
            solve_dfs(v, u, t + 1, current_life);
        }
    }
}

void solve_test_case() {
    cin >> n >> st;
    w.assign(n + 1, 0);
    adj.assign(n + 1, vector<int>());
    for (int i = 1; i <= n; ++i) {
        cin >> w[i];
    }
    for (int i = 0; i < n - 1; ++i) {
        int u, v;
        cin >> u >> v;
        adj[u].push_back(v);
        adj[v].push_back(u);
    }

    bfs_depth();

    max_moves = 0;
    // Initial call: at st, time 0, life is 1 before collecting w[st]
    solve_dfs(st, 0, 0, 1);

    cout << max_moves << endl;
}

int main() {
    ios_base::sync_with_stdio(false);
    cin.tie(NULL);
    int t;
    cin >> t;
    while (t--) {
        solve_test_case();
    }
    return 0;
}