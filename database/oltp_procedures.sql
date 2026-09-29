-- ============================================================
-- DataFusion — Stored Procedures (PL/SQL Style)
-- Business logic implemented in MySQL stored procedures
-- ============================================================

USE datafusion_oltp;

-- ============================================================
-- 1. SP: Place a new order with stock validation
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_place_order;

CREATE PROCEDURE sp_place_order(
    IN p_customer_id INT,
    IN p_warehouse_id INT,
    IN p_product_id INT,
    IN p_quantity INT,
    IN p_payment_method VARCHAR(20)
)
BEGIN
    DECLARE v_stock INT;
    DECLARE v_price DECIMAL(10,2);
    DECLARE v_discount DECIMAL(5,2);
    DECLARE v_order_id INT;
    DECLARE v_final DECIMAL(12,2);

    -- Check stock availability
    SELECT quantity INTO v_stock
    FROM inventory
    WHERE product_id = p_product_id AND warehouse_id = p_warehouse_id;

    IF v_stock IS NULL OR v_stock < p_quantity THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Insufficient stock for this product in the selected warehouse';
    END IF;

    -- Get product price
    SELECT unit_price INTO v_price
    FROM products
    WHERE product_id = p_product_id;

    -- Calculate discount based on quantity
    SET v_discount = CASE
        WHEN p_quantity >= 50 THEN 15.00
        WHEN p_quantity >= 20 THEN 10.00
        WHEN p_quantity >= 10 THEN 5.00
        ELSE 0.00
    END;

    SET v_final = (v_price * p_quantity) * (1 - v_discount / 100);

    -- Insert order
    INSERT INTO orders (customer_id, warehouse_id, order_date, status, total_amount, discount_pct, final_amount, payment_method)
    VALUES (p_customer_id, p_warehouse_id, CURDATE(), 'pending', v_price * p_quantity, v_discount, v_final, p_payment_method);

    SET v_order_id = LAST_INSERT_ID();

    -- Insert order item
    INSERT INTO order_items (order_id, product_id, quantity, unit_price)
    VALUES (v_order_id, p_product_id, p_quantity, v_price);

    -- Deduct inventory
    UPDATE inventory
    SET quantity = quantity - p_quantity
    WHERE product_id = p_product_id AND warehouse_id = p_warehouse_id;

    SELECT v_order_id AS order_id, v_final AS final_amount, v_discount AS discount_applied;
END //

DELIMITER ;

-- ============================================================
-- 2. SP: Reorder check — find products below reorder level
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_reorder_check;

CREATE PROCEDURE sp_reorder_check()
BEGIN
    SELECT
        p.product_id,
        p.product_name,
        p.category,
        w.warehouse_name,
        i.quantity AS current_stock,
        i.reorder_level,
        i.max_stock,
        (i.reorder_level - i.quantity) AS units_needed,
        s.supplier_name,
        s.region AS supplier_region,
        ps.lead_time_days,
        ps.supply_price
    FROM inventory i
    JOIN products p ON i.product_id = p.product_id
    JOIN warehouses w ON i.warehouse_id = w.warehouse_id
    LEFT JOIN product_suppliers ps ON p.product_id = ps.product_id AND ps.is_preferred = 1
    LEFT JOIN suppliers s ON ps.supplier_id = s.supplier_id
    WHERE i.quantity <= i.reorder_level
      AND p.is_active = 1
    ORDER BY (i.reorder_level - i.quantity) DESC;
END //

DELIMITER ;

-- ============================================================
-- 3. SP: Monthly sales report
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_monthly_sales_report;

CREATE PROCEDURE sp_monthly_sales_report(
    IN p_year INT
)
BEGIN
    SELECT
        DATE_FORMAT(o.order_date, '%Y-%m') AS month,
        COUNT(DISTINCT o.order_id) AS total_orders,
        COUNT(DISTINCT o.customer_id) AS unique_customers,
        SUM(oi.quantity) AS total_units_sold,
        ROUND(SUM(o.total_amount), 2) AS gross_revenue,
        ROUND(SUM(o.final_amount), 2) AS net_revenue,
        ROUND(AVG(o.final_amount), 2) AS avg_order_value,
        ROUND(SUM(o.total_amount - o.final_amount), 2) AS total_discounts,
        SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_orders,
        ROUND(SUM(CASE WHEN o.status = 'cancelled' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) AS cancel_rate_pct
    FROM orders o
    JOIN order_items oi ON o.order_id = oi.order_id
    WHERE YEAR(o.order_date) = p_year
    GROUP BY DATE_FORMAT(o.order_date, '%Y-%m')
    ORDER BY month;
END //

DELIMITER ;

-- ============================================================
-- 4. SP: Warehouse utilization report
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_warehouse_utilization;

CREATE PROCEDURE sp_warehouse_utilization()
BEGIN
    SELECT
        w.warehouse_id,
        w.warehouse_name,
        w.city,
        w.region,
        w.capacity_units,
        SUM(i.quantity) AS total_stock,
        ROUND(SUM(i.quantity) * 100.0 / w.capacity_units, 2) AS utilization_pct,
        COUNT(DISTINCT i.product_id) AS unique_products,
        SUM(CASE WHEN i.quantity <= i.reorder_level THEN 1 ELSE 0 END) AS low_stock_items,
        SUM(CASE WHEN i.quantity = 0 THEN 1 ELSE 0 END) AS out_of_stock_items
    FROM warehouses w
    LEFT JOIN inventory i ON w.warehouse_id = i.warehouse_id
    GROUP BY w.warehouse_id, w.warehouse_name, w.city, w.region, w.capacity_units
    ORDER BY utilization_pct DESC;
END //

DELIMITER ;

-- ============================================================
-- 5. SP: Top performing products
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_top_products;

CREATE PROCEDURE sp_top_products(
    IN p_limit INT,
    IN p_start_date DATE,
    IN p_end_date DATE
)
BEGIN
    SELECT
        p.product_id,
        p.product_name,
        p.category,
        p.subcategory,
        p.unit_price,
        SUM(oi.quantity) AS total_quantity_sold,
        ROUND(SUM(oi.line_total), 2) AS total_revenue,
        COUNT(DISTINCT o.order_id) AS order_count,
        COUNT(DISTINCT o.customer_id) AS unique_buyers,
        ROUND(AVG(oi.quantity), 2) AS avg_qty_per_order
    FROM order_items oi
    JOIN orders o ON oi.order_id = o.order_id
    JOIN products p ON oi.product_id = p.product_id
    WHERE o.order_date BETWEEN p_start_date AND p_end_date
      AND o.status != 'cancelled'
    GROUP BY p.product_id, p.product_name, p.category, p.subcategory, p.unit_price
    ORDER BY total_revenue DESC
    LIMIT p_limit;
END //

DELIMITER ;

-- ============================================================
-- 6. SP: Supplier performance analysis
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_supplier_performance;

CREATE PROCEDURE sp_supplier_performance()
BEGIN
    SELECT
        s.supplier_id,
        s.supplier_name,
        s.region,
        s.rating,
        COUNT(DISTINCT ps.product_id) AS products_supplied,
        ROUND(AVG(ps.supply_price), 2) AS avg_supply_price,
        ROUND(AVG(ps.lead_time_days), 1) AS avg_lead_time,
        SUM(CASE WHEN ps.is_preferred = 1 THEN 1 ELSE 0 END) AS preferred_count,
        ROUND(SUM(ps.supply_price * (SELECT COALESCE(SUM(oi.quantity), 0)
            FROM order_items oi
            JOIN products p2 ON oi.product_id = p2.product_id
            WHERE p2.product_id = ps.product_id)), 2) AS estimated_volume
    FROM suppliers s
    JOIN product_suppliers ps ON s.supplier_id = ps.supplier_id
    WHERE s.is_active = 1
    GROUP BY s.supplier_id, s.supplier_name, s.region, s.rating
    ORDER BY s.rating DESC, products_supplied DESC;
END //

DELIMITER ;

-- ============================================================
-- 7. SP: Cancel an order (with inventory restore)
-- ============================================================
DELIMITER //

DROP PROCEDURE IF EXISTS sp_cancel_order;

CREATE PROCEDURE sp_cancel_order(
    IN p_order_id INT
)
BEGIN
    DECLARE v_status VARCHAR(20);
    DECLARE v_warehouse_id INT;

    SELECT status, warehouse_id INTO v_status, v_warehouse_id FROM orders WHERE order_id = p_order_id;

    IF v_status IS NULL THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Order not found';
    END IF;

    IF v_status IN ('delivered', 'cancelled') THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Cannot cancel a delivered or already cancelled order';
    END IF;

    -- Restore inventory to the CORRECT warehouse that fulfilled the order
    UPDATE inventory i
    JOIN order_items oi ON i.product_id = oi.product_id
    SET i.quantity = i.quantity + oi.quantity
    WHERE oi.order_id = p_order_id
      AND i.warehouse_id = v_warehouse_id;

    -- Update order status
    UPDATE orders
    SET status = 'cancelled', updated_at = NOW()
    WHERE order_id = p_order_id;

    SELECT CONCAT('Order ', p_order_id, ' cancelled and inventory restored to warehouse ', v_warehouse_id) AS result;
END //

DELIMITER ;
