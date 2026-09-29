import heapq
from collections import defaultdict
import pandas as pd

from load import execute_oltp_query, execute_dw_query


def build_supplier_graph():
    """Build a graph connecting warehouses and suppliers via shared products.

    Node = warehouse or supplier. Edge weight = effective sourcing cost
    (supply price * lead time penalty). Finding shortest path = cheapest
    + fastest restocking route. Uses Dijkstra's algorithm.
    """
    product_suppliers = execute_oltp_query("""
        SELECT ps.product_id, ps.supplier_id, ps.supply_price, ps.lead_time_days
        FROM product_suppliers ps
    """)
    inventory = execute_oltp_query("""
        SELECT i.warehouse_id, i.product_id, i.quantity, i.reorder_level
        FROM inventory i
    """)
    warehouses = execute_oltp_query("""
        SELECT warehouse_id, warehouse_name, city, region FROM warehouses
    """)
    suppliers = execute_oltp_query("""
        SELECT supplier_id, supplier_name, region, city, rating FROM suppliers
    """)

    game = defaultdict(dict)

    # Map each supplier to products they supply
    supplier_products = defaultdict(set)
    product_lead_time = {}
    for _, row in product_suppliers.iterrows():
        supplier_products[int(row['supplier_id'])].add(int(row['product_id']))
        product_lead_time[int(row['product_id'])] = row['lead_time_days']

    # Edge: warehouse -> supplier if warehouse needs a product the supplier supplies
    # Weight: base 1 + lead-time penalty (higher lead time = heavier edge)
    for _, inv in inventory.iterrows():
        wid = int(inv['warehouse_id'])
        product_id = int(inv['product_id'])
        for supplier_id, products in supplier_products.items():
            if product_id in products:
                lead = product_lead_time.get(product_id, 10)
                weight = 1.0 + (lead / 10.0)
                game[f'wh_{wid}'][f'sup_{supplier_id}'] = min(
                    game[f'wh_{wid}'].get(f'sup_{supplier_id}', float('inf')), weight
                )
                game[f'sup_{supplier_id}'][f'wh_{wid}'] = max(
                    game[f'sup_{supplier_id}'].get(f'wh_{wid}', 0.0), weight
                )

    return game, suppliers, warehouses


def dijkstra_shortest_path(graph, start, target):
    """Dijkstra's algorithm using a priority queue (heap)."""
    distances = {node: float('inf') for node in graph}
    previous = {node: None for node in graph}
    distances[start] = 0
    pq = [(0, start)]

    while pq:
        dist, node = heapq.heappop(pq)
        if dist > distances[node]:
            continue
        if node == target:
            break
        for neighbor, weight in graph[node].items():
            new_dist = dist + weight
            if new_dist < distances[neighbor]:
                distances[neighbor] = new_dist
                previous[neighbor] = node
                heapq.heappush(pq, (new_dist, neighbor))

    path = []
    node = target
    while node is not None:
        path.append(node)
        node = previous[node]
    path.reverse()

    return path, distances.get(target)


def find_critical_supply_paths():
    """Find the 3 lowest-cost sourcing routes between each pair of warehouses."""
    game, suppliers, warehouses = build_supplier_graph()
    results = []

    wh_ids = sorted(warehouses['warehouse_id'].tolist())
    for i in range(len(wh_ids)):
        for j in range(i + 1, len(wh_ids)):
            start = f'wh_{wh_ids[i]}'
            target = f'wh_{wh_ids[j]}'
            try:
                path, total_cost = dijkstra_shortest_path(game, start, target)
                if path and total_cost != float('inf'):
                    results.append({
                        'from_warehouse': wh_ids[i],
                        'to_warehouse': wh_ids[j],
                        'path': ' -> '.join(path),
                        'cost_score': round(total_cost, 2),
                        'hops': len(path) - 1,
                    })
            except (KeyError, ValueError):
                continue

    return pd.DataFrame(results).sort_values('cost_score').head(5)


def analyze_network_centrality():
    """Find which nodes (warehouses/suppliers) are most central in the sourcing graph."""
    game, suppliers, warehouses = build_supplier_graph()
    degree = defaultdict(int)
    for node, neighbors in game.items():
        degree[node] += len(neighbors)
    for node, neighbors in game.items():
        for n in neighbors:
            if n != node:
                degree[n] += 1

    suppliers_map = {f'sup_{int(r["supplier_id"])}': r for _, r in suppliers.iterrows()}
    warehouses_map = {f'wh_{int(r["warehouse_id"])}': r for _, r in warehouses.iterrows()}

    rows = []
    for node, deg in degree.items():
        if node.startswith('sup_'):
            info = suppliers_map[node]
            rows.append({'node': info['supplier_name'], 'type': 'Supplier',
                         'region': info['region'], 'degree': deg})
        elif node.startswith('wh_'):
            info = warehouses_map[node]
            rows.append({'node': info['warehouse_name'], 'type': 'Warehouse',
                         'region': info['region'], 'degree': deg})

    return pd.DataFrame(rows).sort_values('degree', ascending=False).head(10)


if __name__ == '__main__':
    print("=" * 60)
    print("  DataFusion — Inventory Optimizer (Graph Algorithms)")
    print("=" * 60)

    print("\n[1] Top 5 lowest-cost warehouse-to-warehouse sourcing routes (Dijkstra's):")
    routes = find_critical_supply_paths()
    if not routes.empty:
        print(routes.to_string(index=False))
    else:
        print("  No routes found.")

    print("\n[2] Most central nodes in the supply network (degree centrality):")
    centrality = analyze_network_centrality()
    if not centrality.empty:
        print(centrality.to_string(index=False))

    print("\nDone!")