-- ============================================================
-- DataFusion — Triggers & Functions
-- Audit logging, data validation, and business logic
-- ============================================================

USE datafusion_oltp;

-- ============================================================
-- FUNCTION: Calculate discount based on order total
-- ============================================================
DELIMITER //

DROP FUNCTION IF EXISTS fn_calc_discount;

CREATE FUNCTION fn_calc_discount(
    p_total DECIMAL(12,2),
    p_customer_type VARCHAR(20)
) RETURNS DECIMAL(5,2)
DETERMINISTIC
BEGIN
    DECLARE v_discount DECIMAL(5,2) DEFAULT 0.00;

    -- Base discount by customer type
    SET v_discount = CASE
        WHEN p_customer_type = 'business' THEN 5.00
        ELSE 0.00
    END;

    -- Volume discount
    SET v_discount = v_discount + CASE
        WHEN p_total >= 100000 THEN 15.00
        WHEN p_total >= 50000 THEN 10.00
        WHEN p_total >= 10000 THEN 5.00
        WHEN p_total >= 5000 THEN 2.50
        ELSE 0.00
    END;

    -- Cap at 25%
    IF v_discount > 25.00 THEN
        SET v_discount = 25.00;
    END IF;

    RETURN v_discount;
END //

DELIMITER ;

-- ============================================================
-- FUNCTION: Get reorder urgency (1=critical, 2=high, 3=medium, 4=low)
-- ============================================================
DELIMITER //

DROP FUNCTION IF EXISTS fn_reorder_urgency;

CREATE FUNCTION fn_reorder_urgency(
    p_current_qty INT,
    p_reorder_level INT
) RETURNS INT
DETERMINISTIC
BEGIN
    IF p_current_qty = 0 THEN RETURN 1;
    ELSEIF p_current_qty <= p_reorder_level * 0.5 THEN RETURN 2;
    ELSEIF p_current_qty <= p_reorder_level THEN RETURN 3;
    ELSE RETURN 4;
    END IF;
END //

DELIMITER ;

-- ============================================================
-- FUNCTION: Calculate profit margin for a product
-- ============================================================
DELIMITER //

DROP FUNCTION IF EXISTS fn_profit_margin;

CREATE FUNCTION fn_profit_margin(
    p_product_id INT
) RETURNS DECIMAL(5,2)
DETERMINISTIC
BEGIN
    DECLARE v_price DECIMAL(10,2);
    DECLARE v_cost DECIMAL(10,2);

    SELECT unit_price, cost_price INTO v_price, v_cost
    FROM products WHERE product_id = p_product_id;

    IF v_cost IS NULL OR v_cost = 0 THEN
        RETURN 0.00;
    END IF;

    RETURN ROUND(((v_price - v_cost) / v_price) * 100, 2);
END //

DELIMITER ;

-- ============================================================
-- TRIGGER: After INSERT on orders — audit log
-- ============================================================
DELIMITER //

DROP TRIGGER IF EXISTS trg_after_insert_order;

CREATE TRIGGER trg_after_insert_order
AFTER INSERT ON orders
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, record_id, action, new_values, changed_by)
    VALUES (
        'orders',
        NEW.order_id,
        'INSERT',
        JSON_OBJECT(
            'customer_id', NEW.customer_id,
            'warehouse_id', NEW.warehouse_id,
            'order_date', NEW.order_date,
            'status', NEW.status,
            'total_amount', NEW.total_amount,
            'discount_pct', NEW.discount_pct,
            'final_amount', NEW.final_amount,
            'payment_method', NEW.payment_method
        ),
        'system'
    );
END //

DELIMITER ;

-- ============================================================
-- TRIGGER: After UPDATE on orders — audit log
-- ============================================================
DELIMITER //

DROP TRIGGER IF EXISTS trg_after_update_order;

CREATE TRIGGER trg_after_update_order
AFTER UPDATE ON orders
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, record_id, action, old_values, new_values, changed_by)
    VALUES (
        'orders',
        NEW.order_id,
        'UPDATE',
        JSON_OBJECT(
            'status', OLD.status,
            'total_amount', OLD.total_amount,
            'discount_pct', OLD.discount_pct,
            'final_amount', OLD.final_amount
        ),
        JSON_OBJECT(
            'status', NEW.status,
            'total_amount', NEW.total_amount,
            'discount_pct', NEW.discount_pct,
            'final_amount', NEW.final_amount
        ),
        'system'
    );
END //

DELIMITER ;

-- ============================================================
-- TRIGGER: After UPDATE on inventory — low stock alert
-- ============================================================
DELIMITER //

DROP TRIGGER IF EXISTS trg_after_update_inventory;

CREATE TRIGGER trg_after_update_inventory
AFTER UPDATE ON inventory
FOR EACH ROW
BEGIN
    IF NEW.quantity <= NEW.reorder_level AND OLD.quantity > OLD.reorder_level THEN
        INSERT INTO data_quality_log (pipeline_run, table_name, anomaly_type, records_affected, action_taken, severity)
        VALUES (
            CONCAT('INV-CHECK-', DATE_FORMAT(NOW(), '%Y%m%d%H%i')),
            'inventory',
            'LOW_STOCK_ALERT',
            1,
            CONCAT('Product ', NEW.product_id, ' at warehouse ', NEW.warehouse_id,
                   ' dropped below reorder level (', NEW.quantity, '/', NEW.reorder_level, ')'),
            'high'
        );
    END IF;
END //

DELIMITER ;

-- ============================================================
-- TRIGGER: Before INSERT on order_items — validate price
-- ============================================================
DELIMITER //

DROP TRIGGER IF EXISTS trg_before_insert_order_item;

CREATE TRIGGER trg_before_insert_order_item
BEFORE INSERT ON order_items
FOR EACH ROW
BEGIN
    DECLARE v_market_price DECIMAL(10,2);

    SELECT unit_price INTO v_market_price
    FROM products WHERE product_id = NEW.product_id;

    -- Validate price is within 20% of market price
    IF NEW.unit_price < v_market_price * 0.80 OR NEW.unit_price > v_market_price * 1.20 THEN
        SET NEW.unit_price = v_market_price;
    END IF;
END //

DELIMITER ;

-- ============================================================
-- TRIGGER: After DELETE on products — soft delete warning
-- ============================================================
DELIMITER //

DROP TRIGGER IF EXISTS trg_before_delete_product;

CREATE TRIGGER trg_before_delete_product
BEFORE DELETE ON products
FOR EACH ROW
BEGIN
    INSERT INTO audit_log (table_name, record_id, action, old_values, changed_by)
    VALUES (
        'products',
        OLD.product_id,
        'DELETE',
        JSON_OBJECT(
            'product_name', OLD.product_name,
            'category', OLD.category,
            'unit_price', OLD.unit_price
        ),
        'system'
    );
END //

DELIMITER ;
