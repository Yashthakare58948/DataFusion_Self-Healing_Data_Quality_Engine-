-- ============================================================
-- DataFusion — Warehouse ETL Procedures
-- Loads data from OLTP into Data Warehouse
-- ============================================================

USE datafusion_dw;

-- ============================================================
-- 1. Load dim_product from OLTP (with SCD Type 2)
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_etl_dim_product;

CREATE PROCEDURE sp_etl_dim_product()
BEGIN
    -- Insert new products
    INSERT INTO dim_product (
        product_key, product_id, product_name, category, subcategory,
        unit_price, cost_price, profit_margin, weight_kg, is_active,
        valid_from, valid_to, is_current
    )
    SELECT
        p.product_id, p.product_id, p.product_name, p.category, p.subcategory,
        p.unit_price, p.cost_price, ROUND(((p.unit_price - p.cost_price) / p.unit_price) * 100, 2),
        p.weight_kg, p.is_active, CURDATE(), NULL, 1
    FROM datafusion_oltp.products p
    WHERE p.product_id NOT IN (SELECT DISTINCT product_id FROM dim_product WHERE is_current = 1);

    -- Handle SCD Type 2 for changed prices
    UPDATE dim_product dw
    JOIN datafusion_oltp.products p ON dw.product_id = p.product_id
    SET dw.valid_to = DATE_SUB(CURDATE(), INTERVAL 1 DAY),
        dw.is_current = 0
    WHERE dw.is_current = 1
      AND (dw.unit_price != p.unit_price OR dw.cost_price != p.cost_price OR dw.category != p.category);

    INSERT INTO dim_product (
        product_key, product_id, product_name, category, subcategory,
        unit_price, cost_price, profit_margin, weight_kg, is_active,
        valid_from, valid_to, is_current
    )
    SELECT
        p.product_id * 100 + (SELECT COUNT(*) FROM dim_product d2 WHERE d2.product_id = p.product_id) + 1,
        p.product_id, p.product_name, p.category, p.subcategory,
        p.unit_price, p.cost_price, ROUND(((p.unit_price - p.cost_price) / p.unit_price) * 100, 2),
        p.weight_kg, p.is_active, CURDATE(), NULL, 1
    FROM datafusion_oltp.products p
    WHERE p.product_id IN (
        SELECT product_id FROM dim_product WHERE valid_to = DATE_SUB(CURDATE(), INTERVAL 1 DAY)
    );
END //

DELIMITER ;

-- ============================================================
-- 2. Load dim_supplier from OLTP
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_etl_dim_supplier;

CREATE PROCEDURE sp_etl_dim_supplier()
BEGIN
    INSERT INTO dim_supplier (
        supplier_key, supplier_id, supplier_name, region, city, country,
        rating, valid_from, valid_to, is_current
    )
    SELECT
        s.supplier_id, s.supplier_id, s.supplier_name, s.region, s.city, s.country,
        s.rating, CURDATE(), NULL, 1
    FROM datafusion_oltp.suppliers s
    WHERE s.supplier_id NOT IN (SELECT DISTINCT supplier_id FROM dim_supplier WHERE is_current = 1);
END //

DELIMITER ;

-- ============================================================
-- 3. Load dim_warehouse from OLTP
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_etl_dim_warehouse;

CREATE PROCEDURE sp_etl_dim_warehouse()
BEGIN
    INSERT INTO dim_warehouse (warehouse_key, warehouse_id, warehouse_name, city, region, capacity_units)
    SELECT
        w.warehouse_id, w.warehouse_id, w.warehouse_name, w.city, w.region, w.capacity_units
    FROM datafusion_oltp.warehouses w
    WHERE w.warehouse_id NOT IN (SELECT DISTINCT warehouse_id FROM dim_warehouse);
END //

DELIMITER ;

-- ============================================================
-- 4. Load dim_customer with aggregates
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_etl_dim_customer;

CREATE PROCEDURE sp_etl_dim_customer()
BEGIN
    INSERT INTO dim_customer (
        customer_key, customer_id, full_name, city, region, customer_type,
        first_order_date, last_order_date, total_orders, total_spent
    )
    SELECT
        c.customer_id,
        c.customer_id,
        CONCAT(c.first_name, ' ', c.last_name),
        c.city,
        c.region,
        c.customer_type,
        MIN(o.order_date) AS first_order,
        MAX(o.order_date) AS last_order,
        COUNT(DISTINCT o.order_id),
        COALESCE(SUM(o.final_amount), 0)
    FROM datafusion_oltp.customers c
    LEFT JOIN datafusion_oltp.orders o ON c.customer_id = o.customer_id AND o.status != 'cancelled'
    WHERE c.customer_id NOT IN (SELECT DISTINCT customer_id FROM dim_customer)
    GROUP BY c.customer_id, c.first_name, c.last_name, c.city, c.region, c.customer_type;

    -- Update existing customers with latest aggregates
    UPDATE dim_customer dc
    JOIN (
        SELECT
            c.customer_id,
            MIN(o.order_date) AS first_order,
            MAX(o.order_date) AS last_order,
            COUNT(DISTINCT o.order_id) AS total_orders,
            COALESCE(SUM(o.final_amount), 0) AS total_spent
        FROM datafusion_oltp.customers c
        LEFT JOIN datafusion_oltp.orders o ON c.customer_id = o.customer_id AND o.status != 'cancelled'
        WHERE c.customer_id IN (SELECT DISTINCT customer_id FROM dim_customer)
        GROUP BY c.customer_id
    ) agg ON dc.customer_id = agg.customer_id
    SET dc.first_order_date = agg.first_order,
        dc.last_order_date = agg.last_order,
        dc.total_orders = agg.total_orders,
        dc.total_spent = agg.total_spent;
END //

DELIMITER ;

-- ============================================================
-- 5. Load fact_sales (main fact table)
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_etl_fact_sales;

CREATE PROCEDURE sp_etl_fact_sales()
BEGIN
    INSERT INTO fact_sales (
        date_key, product_key, supplier_key, warehouse_key, customer_key,
        order_id, quantity, unit_price, line_total, discount_pct,
        revenue_after_discount, cost_total, profit, order_status
    )
    SELECT
        (YEAR(o.order_date) * 10000 + MONTH(o.order_date) * 100 + DAY(o.order_date)) AS date_key,
        dp.product_key,
        ds.supplier_key,
        dw.warehouse_key,
        dc.customer_key,
        o.order_id,
        oi.quantity,
        oi.unit_price,
        oi.line_total,
        o.discount_pct,
        ROUND(oi.line_total * (1 - o.discount_pct / 100), 2) AS revenue_after_discount,
        ROUND(oi.quantity * dp.cost_price, 2) AS cost_total,
        ROUND(oi.line_total * (1 - o.discount_pct / 100) - oi.quantity * dp.cost_price, 2) AS profit,
        o.status
    FROM datafusion_oltp.order_items oi
    JOIN datafusion_oltp.orders o ON oi.order_id = o.order_id
    JOIN dim_product dp ON oi.product_id = dp.product_id AND dp.is_current = 1
    JOIN dim_supplier ds ON ds.supplier_id = (
        SELECT ps.supplier_id FROM datafusion_oltp.product_suppliers ps
        WHERE ps.product_id = oi.product_id AND ps.is_preferred = 1
        LIMIT 1
    )
    JOIN dim_warehouse dw ON o.warehouse_id = dw.warehouse_id
    JOIN dim_customer dc ON o.customer_id = dc.customer_id
    WHERE oi.order_id NOT IN (SELECT DISTINCT order_id FROM fact_sales);
END //

DELIMITER ;

-- ============================================================
-- 6. Load fact_inventory (current snapshot)
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_etl_fact_inventory;

CREATE PROCEDURE sp_etl_fact_inventory()
BEGIN
    DECLARE v_date_key INT;
    SET v_date_key = YEAR(CURDATE()) * 10000 + MONTH(CURDATE()) * 100 + DAY(CURDATE());

    -- Idempotency guard: remove any existing snapshot for today before loading
    DELETE FROM fact_inventory WHERE date_key = v_date_key;

    INSERT INTO fact_inventory (
        date_key, product_key, warehouse_key, quantity_on_hand, reorder_level, stock_status, days_since_restock
    )
    SELECT
        v_date_key,
        dp.product_key,
        dw.warehouse_key,
        i.quantity,
        i.reorder_level,
        CASE
            WHEN i.quantity = 0 THEN 'out_of_stock'
            WHEN i.quantity <= i.reorder_level THEN 'low_stock'
            WHEN i.quantity >= i.max_stock THEN 'overstocked'
            ELSE 'in_stock'
        END,
        DATEDIFF(CURDATE(), COALESCE(DATE(i.last_restocked), CURDATE()))
    FROM datafusion_oltp.inventory i
    JOIN dim_product dp ON i.product_id = dp.product_id AND dp.is_current = 1
    JOIN dim_warehouse dw ON i.warehouse_id = dw.warehouse_id;
END //

DELIMITER ;

-- ============================================================
-- 7. Load fact_shipments
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_etl_fact_shipments;

CREATE PROCEDURE sp_etl_fact_shipments()
BEGIN
    INSERT INTO fact_shipments (
        date_key, order_id, warehouse_key, shipped_date, delivered_date,
        delivery_days, carrier, shipping_cost, on_time_delivery, status
    )
    SELECT
        (YEAR(COALESCE(shipped_date, CURDATE())) * 10000
            + MONTH(COALESCE(shipped_date, CURDATE())) * 100
            + DAY(COALESCE(shipped_date, CURDATE()))) AS date_key,
        s.order_id,
        dw.warehouse_key,
        s.shipped_date,
        s.delivered_date,
        DATEDIFF(COALESCE(s.delivered_date, CURDATE()), s.shipped_date),
        s.carrier,
        s.shipping_cost,
        CASE WHEN DATEDIFF(COALESCE(s.delivered_date, CURDATE()), s.shipped_date) <= 7 THEN 1 ELSE 0 END,
        s.status
    FROM datafusion_oltp.shipments s
    JOIN dim_warehouse dw ON s.warehouse_id = dw.warehouse_id
    WHERE s.order_id NOT IN (SELECT order_id FROM fact_shipments);
END //

DELIMITER ;

-- ============================================================
-- 8. Master ETL orchestrator
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_run_full_etl;

CREATE PROCEDURE sp_run_full_etl()
BEGIN
    CALL sp_etl_dim_product();
    CALL sp_etl_dim_supplier();
    CALL sp_etl_dim_warehouse();
    CALL sp_etl_dim_customer();
    CALL sp_etl_fact_sales();
    CALL sp_etl_fact_inventory();
    CALL sp_etl_fact_shipments();
END //

DELIMITER ;
