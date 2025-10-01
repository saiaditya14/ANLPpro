#include <iostream>
#include <vector>
#include <numeric>
#include <algorithm>

// Function to solve a single test case
void solve() {
    int n;
    int j_one_based, k;
    std::cin >> n >> j_one_based >> k;
    
    std::vector<int> a(n);
    int max_strength = 0;
    for (int i = 0; i < n; ++i) {
        std::cin >> a[i];
        if (a[i] > max_strength) {
            max_strength = a[i];
        }
    }

    // Convert 1-based j to 0-based index
    int j_zero_based = j_one_based - 1;

    // Case 1: k >= 2
    // We need to perform n-k eliminations. The process stops when k players remain.
    // The eliminations happen when the number of players m is n, n-1, ..., k+1.
    // To protect player j, we can always choose two *other* players to compete,
    // as long as there are at least two other players. This requires m >= 3.
    // This condition holds for all elimination rounds if the last round has at least 3 players,
    // i.e., k+1 >= 3, which means k >= 2.
    // If k >= 2, we can always ensure player j is not chosen for any match,
    // and thus player j will be among the final k survivors.
    if (k >= 2) {
        std::cout << "YES\n";
        return;
    }

    // Case 2: k = 1
    // The tournament continues until only one player remains.
    // We can protect player j until only 2 players are left: player j and another player.
    // The other player will be the winner of a tournament among the other n-1 players.
    // Since we control pairings, we can ensure the strongest of the other players wins that.
    // To be the final winner, player j must defeat this strongest opponent.
    // This is possible if and only if player j is one of the players with the
    // maximum strength in the entire tournament.
    if (a[j_zero_based] == max_strength) {
        std::cout << "YES\n";
    } else {
        std::cout << "NO\n";
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