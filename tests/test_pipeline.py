import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'etl'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'cloud'))

from transform import BloomFilter, MergeSorter, SlidingWindowAnomalyDetector, TopologicalSort


def test_bloom_filter_no_false_negatives():
    bf = BloomFilter(size=10000, hash_count=3)
    keys = [f"key_{i}" for i in range(1000)]
    for k in keys:
        bf.add(k)
    for k in keys:
        assert bf.might_contain(k), f"False negative for {k}"
    print("PASS: Bloom filter has zero false negatives")


def test_merge_sort():
    sorter = MergeSorter()
    arr = [5, 2, 9, 1, 7, 3, 8, 4, 6, 0]
    sorted_arr = sorter.merge_sort(arr)
    assert sorted_arr == sorted(arr), f"Got {sorted_arr}"
    print("PASS: Merge sort correctly sorts 10 elements")


def test_sliding_window_anomaly_detection():
    detector = SlidingWindowAnomalyDetector(window_size=3, threshold=2.0)
    import pandas as pd
    series = pd.Series([10, 12, 11, 13, 12, 100, 11, 12, 10, 13])
    anomalies = detector.detect(series)
    assert any(anomalies), "Expected at least one anomaly spike"
    print("PASS: Sliding window detects spike anomaly")


def test_topological_sort():
    topo = TopologicalSort()
    topo.add_edge('products', 'order_items')
    topo.add_edge('orders', 'order_items')
    topo.add_edge('orders', 'shipments')
    topo.add_edge('customers', 'orders')
    result = topo.sort()
    assert result.index('products') < result.index('order_items')
    assert result.index('orders') < result.index('order_items')
    assert result.index('customers') < result.index('orders')
    print(f"PASS: Topological order valid: {result}")


def test_dijkstra_on_small_graph():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'analytics'))
    from inventory_optimizer import dijkstra_shortest_path

    graph = {
        'A': {'B': 1.0, 'C': 4.0},
        'B': {'C': 2.0, 'D': 5.0},
        'C': {'D': 1.0},
        'D': {},
    }
    path, cost = dijkstra_shortest_path(graph, 'A', 'D')
    assert path == ['A', 'B', 'C', 'D'], f"Got {path}"
    assert cost == 4.0, f"Got cost {cost}"
    print("PASS: Dijkstra finds shortest path A->B->C->D at cost 4.0")


def test_mysql_connections():
    from load import execute_oltp_query, execute_dw_query
    oltp = execute_oltp_query("SELECT COUNT(*) AS n FROM orders")
    dw = execute_dw_query("SELECT COUNT(*) AS n FROM fact_sales")
    assert oltp['n'].iloc[0] > 0, "OLTP orders should be > 0"
    assert dw['n'].iloc[0] > 0, "DW fact_sales should be > 0"
    print(f"PASS: MySQL OLTP has {oltp['n'].iloc[0]} orders, DW has {dw['n'].iloc[0]} sales")


if __name__ == '__main__':
    tests = [
        test_bloom_filter_no_false_negatives,
        test_merge_sort,
        test_sliding_window_anomaly_detection,
        test_topological_sort,
        test_dijkstra_on_small_graph,
        test_mysql_connections,
    ]
    passed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"FAIL: {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")