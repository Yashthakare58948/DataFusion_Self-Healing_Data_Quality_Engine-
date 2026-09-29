-- ============================================================
-- DataFusion — OLTP Schema (MySQL 8.0)
-- Normalized 3NF design for operational data
-- ============================================================

CREATE DATABASE IF NOT EXISTS datafusion_oltp;
USE datafusion_oltp;

-- ------------------------------------------------------------
-- 1. PRODUCTS
-- ------------------------------------------------------------
CREATE TABLE products (
    product_id      INT AUTO_INCREMENT PRIMARY KEY,
    product_name    VARCHAR(200) NOT NULL,
    category        VARCHAR(100) NOT NULL,
    subcategory     VARCHAR(100) NOT NULL,
    unit_price      DECIMAL(10,2) NOT NULL,
    cost_price      DECIMAL(10,2) NOT NULL,
    weight_kg       DECIMAL(8,2) DEFAULT 0,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_category (category),
    INDEX idx_active (is_active)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 2. SUPPLIERS
-- ------------------------------------------------------------
CREATE TABLE suppliers (
    supplier_id     INT AUTO_INCREMENT PRIMARY KEY,
    supplier_name   VARCHAR(200) NOT NULL,
    contact_person  VARCHAR(150),
    email           VARCHAR(150),
    phone           VARCHAR(20),
    region          VARCHAR(50) NOT NULL,
    city            VARCHAR(100) NOT NULL,
    country         VARCHAR(100) NOT NULL DEFAULT 'India',
    rating          DECIMAL(2,1) DEFAULT 3.0,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_region (region),
    INDEX idx_rating (rating)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 3. WAREHOUSES
-- ------------------------------------------------------------
CREATE TABLE warehouses (
    warehouse_id    INT AUTO_INCREMENT PRIMARY KEY,
    warehouse_name  VARCHAR(150) NOT NULL,
    city            VARCHAR(100) NOT NULL,
    region          VARCHAR(50) NOT NULL,
    capacity_units  INT DEFAULT 10000,
    is_active       TINYINT(1) DEFAULT 1,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 4. CUSTOMERS
-- ------------------------------------------------------------
CREATE TABLE customers (
    customer_id     INT AUTO_INCREMENT PRIMARY KEY,
    first_name      VARCHAR(100) NOT NULL,
    last_name       VARCHAR(100) NOT NULL,
    email           VARCHAR(150),
    phone           VARCHAR(20),
    city            VARCHAR(100) NOT NULL,
    region          VARCHAR(50) NOT NULL,
    customer_type   ENUM('individual', 'business') DEFAULT 'individual',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_region (region),
    INDEX idx_type (customer_type)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 5. PRODUCT_SUPPLIERS (Many-to-Many)
-- ------------------------------------------------------------
CREATE TABLE product_suppliers (
    product_id      INT NOT NULL,
    supplier_id     INT NOT NULL,
    supply_price    DECIMAL(10,2) NOT NULL,
    lead_time_days  INT DEFAULT 7,
    is_preferred    TINYINT(1) DEFAULT 0,
    PRIMARY KEY (product_id, supplier_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    FOREIGN KEY (supplier_id) REFERENCES suppliers(supplier_id) ON DELETE CASCADE
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 6. INVENTORY
-- ------------------------------------------------------------
CREATE TABLE inventory (
    inventory_id    INT AUTO_INCREMENT PRIMARY KEY,
    product_id      INT NOT NULL,
    warehouse_id    INT NOT NULL,
    quantity         INT NOT NULL DEFAULT 0,
    reorder_level   INT DEFAULT 50,
    max_stock       INT DEFAULT 500,
    last_restocked  TIMESTAMP NULL,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_product_warehouse (product_id, warehouse_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    INDEX idx_quantity (quantity)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 7. ORDERS
-- ------------------------------------------------------------
CREATE TABLE orders (
    order_id        INT AUTO_INCREMENT PRIMARY KEY,
    customer_id     INT NOT NULL,
    warehouse_id    INT NOT NULL,
    order_date      DATE NOT NULL,
    status          ENUM('pending','processing','shipped','delivered','cancelled') DEFAULT 'pending',
    total_amount    DECIMAL(12,2) DEFAULT 0.00,
    discount_pct    DECIMAL(5,2) DEFAULT 0.00,
    final_amount    DECIMAL(12,2) DEFAULT 0.00,
    payment_method  ENUM('cod','online','bank_transfer') DEFAULT 'online',
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id) ON DELETE CASCADE,
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    INDEX idx_order_date (order_date),
    INDEX idx_status (status),
    INDEX idx_customer (customer_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 8. ORDER_ITEMS
-- ------------------------------------------------------------
CREATE TABLE order_items (
    item_id         INT AUTO_INCREMENT PRIMARY KEY,
    order_id        INT NOT NULL,
    product_id      INT NOT NULL,
    quantity        INT NOT NULL DEFAULT 1,
    unit_price      DECIMAL(10,2) NOT NULL,
    line_total      DECIMAL(12,2) GENERATED ALWAYS AS (quantity * unit_price) STORED,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE,
    INDEX idx_order (order_id),
    INDEX idx_product (product_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 9. SHIPMENTS
-- ------------------------------------------------------------
CREATE TABLE shipments (
    shipment_id     INT AUTO_INCREMENT PRIMARY KEY,
    order_id        INT NOT NULL,
    warehouse_id    INT NOT NULL,
    shipped_date    DATE,
    delivered_date  DATE,
    carrier         VARCHAR(100),
    tracking_number VARCHAR(100),
    status          ENUM('pending','in_transit','delivered','returned') DEFAULT 'pending',
    shipping_cost   DECIMAL(8,2) DEFAULT 0.00,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    FOREIGN KEY (warehouse_id) REFERENCES warehouses(warehouse_id) ON DELETE CASCADE,
    INDEX idx_order (order_id),
    INDEX idx_status (status)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 10. AUDIT_LOG (for triggers)
-- ------------------------------------------------------------
CREATE TABLE audit_log (
    log_id          INT AUTO_INCREMENT PRIMARY KEY,
    table_name      VARCHAR(100) NOT NULL,
    record_id       INT NOT NULL,
    action          ENUM('INSERT','UPDATE','DELETE') NOT NULL,
    old_values      JSON,
    new_values      JSON,
    changed_by      VARCHAR(100) DEFAULT 'system',
    changed_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_table_record (table_name, record_id),
    INDEX idx_action (action)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- 11. DATA_QUALITY_LOG (for self-healing engine)
-- ------------------------------------------------------------
CREATE TABLE data_quality_log (
    log_id              INT AUTO_INCREMENT PRIMARY KEY,
    pipeline_run        VARCHAR(50) NOT NULL,
    table_name          VARCHAR(100) NOT NULL,
    anomaly_type        VARCHAR(100) NOT NULL,
    records_affected    INT DEFAULT 0,
    action_taken        VARCHAR(200) NOT NULL,
    severity            ENUM('low','medium','high','critical') DEFAULT 'medium',
    detected_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB;
