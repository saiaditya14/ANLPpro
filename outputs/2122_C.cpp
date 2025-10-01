#include <iostream>
#include <vector>
#include <algorithm>
#include <cmath>

// Structure to store point data including its original index
struct Point {
    long long x, y;
    int id;
};

// Comparison function for sorting points based on x-coordinate
bool comparePoints(const Point& a, const Point& b) {
    if (a.x != b.x) {
        return a.x < b.x;
    }
    // Tie-breaking by y-coordinate, although not strictly necessary for this problem's logic
    return a.y < b.y;
}

void solve() {
    int n;
    std::cin >> n;
    std::vector<Point> points(n);
    for (int i = 0; i < n; ++i) {
        std::cin >> points[i].x >> points[i].y;
        points[i].id = i + 1;
    }

    // Sort points based on their x-coordinate
    std::sort(points.begin(), points.end(), comparePoints);

    // Pair the i-th point from the first half with the i-th point from the second half
    for (int i = 0; i < n / 2; ++i) {
        std::cout << points[i].id << " " << points[i + n / 2].id << "\n";
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