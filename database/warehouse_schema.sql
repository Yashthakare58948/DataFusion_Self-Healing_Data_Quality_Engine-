-- ============================================================
-- DataFusion — Data Warehouse Schema (Star Schema)
-- Analytical layer with dimension and fact tables
-- ============================================================

CREATE DATABASE IF NOT EXISTS datafusion_dw;
USE datafusion_dw;

-- ------------------------------------------------------------
-- DIMENSION: dim_date
-- ------------------------------------------------------------
CREATE TABLE dim_date (
    date_key            INT PRIMARY KEY,
    full_date           DATE NOT NULL,
    year                INT NOT NULL,
    quarter             INT NOT NULL,
    month               INT NOT NULL,
    month_name          VARCHAR(20) NOT NULL,
    week                INT NOT NULL,
    day_of_month        INT NOT NULL,
    day_of_week         INT NOT NULL,
    day_name            VARCHAR(20) NOT NULL,
    is_weekend          TINYINT(1) DEFAULT 0,
    is_holiday          TINYINT(1) DEFAULT 0,
    fiscal_year         VARCHAR(20),
    INDEX idx_date_full (full_date),
    INDEX idx_year_month (year, month)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- DIMENSION: dim_product (with SCD Type 2 support)
-- ------------------------------------------------------------
CREATE TABLE dim_product (
    product_key         INT PRIMARY KEY,
    product_id          INT NOT NULL,
    product_name        VARCHAR(200) NOT NULL,
    category            VARCHAR(100) NOT NULL,
    subcategory         VARCHAR(100) NOT NULL,
    unit_price          DECIMAL(10,2) NOT NULL,
    cost_price          DECIMAL(10,2) NOT NULL,
    profit_margin       DECIMAL(5,2),
    weight_kg           DECIMAL(8,2) DEFAULT 0,
    is_active           TINYINT(1) DEFAULT 1,
    valid_from          DATE,
    valid_to            DATE,
    is_current          TINYINT(1) DEFAULT 1,
    INDEX idx_product_id (product_id),
    INDEX idx_category (category),
    INDEX idx_current (is_current)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- DIMENSION: dim_supplier
-- ------------------------------------------------------------
CREATE TABLE dim_supplier (
    supplier_key        INT PRIMARY KEY,
    supplier_id         INT NOT NULL,
    supplier_name       VARCHAR(200) NOT NULL,
    region              VARCHAR(50) NOT NULL,
    city                VARCHAR(100) NOT NULL,
    country             VARCHAR(100) DEFAULT 'India',
    rating              DECIMAL(2,1) DEFAULT 3.0,
    valid_from          DATE,
    valid_to            DATE,
    is_current          TINYINT(1) DEFAULT 1,
    INDEX idx_supplier_id (supplier_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- DIMENSION: dim_warehouse
-- ------------------------------------------------------------
CREATE TABLE dim_warehouse (
    warehouse_key       INT PRIMARY KEY,
    warehouse_id        INT NOT NULL,
    warehouse_name      VARCHAR(150) NOT NULL,
    city                VARCHAR(100) NOT NULL,
    region              VARCHAR(50) NOT NULL,
    capacity_units      INT DEFAULT 10000,
    INDEX idx_warehouse_id (warehouse_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- DIMENSION: dim_customer
-- ------------------------------------------------------------
CREATE TABLE dim_customer (
    customer_key        INT PRIMARY KEY,
    customer_id         INT NOT NULL,
    full_name           VARCHAR(200) NOT NULL,
    city                VARCHAR(100) NOT NULL,
    region              VARCHAR(50) NOT NULL,
    customer_type       ENUM('individual','business') DEFAULT 'individual',
    first_order_date    DATE,
    last_order_date     DATE,
    total_orders        INT DEFAULT 0,
    total_spent         DECIMAL(12,2) DEFAULT 0.00,
    INDEX idx_customer_id (customer_id),
    INDEX idx_region (region)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- FACT: fact_sales
-- ------------------------------------------------------------
CREATE TABLE fact_sales (
    sales_key           INT AUTO_INCREMENT PRIMARY KEY,
    date_key            INT NOT NULL,
    product_key         INT NOT NULL,
    supplier_key        INT NOT NULL,
    warehouse_key       INT NOT NULL,
    customer_key        INT NOT NULL,
    order_id            INT NOT NULL,
    quantity            INT NOT NULL,
    unit_price          DECIMAL(10,2) NOT NULL,
    line_total          DECIMAL(12,2) NOT NULL,
    discount_pct        DECIMAL(5,2) DEFAULT 0.00,
    revenue_after_discount DECIMAL(12,2),
    cost_total          DECIMAL(12,2),
    profit              DECIMAL(12,2),
    order_status        VARCHAR(20),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (product_key) REFERENCES dim_product(product_key),
    FOREIGN KEY (supplier_key) REFERENCES dim_supplier(supplier_key),
    FOREIGN KEY (warehouse_key) REFERENCES dim_warehouse(warehouse_key),
    FOREIGN KEY (customer_key) REFERENCES dim_customer(customer_key),
    INDEX idx_date (date_key),
    INDEX idx_product (product_key),
    INDEX idx_warehouse (warehouse_key),
    INDEX idx_order (order_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- FACT: fact_inventory (daily snapshots)
-- ------------------------------------------------------------
CREATE TABLE fact_inventory (
    inventory_key       INT AUTO_INCREMENT PRIMARY KEY,
    date_key            INT NOT NULL,
    product_key         INT NOT NULL,
    warehouse_key       INT NOT NULL,
    quantity_on_hand    INT NOT NULL,
    reorder_level       INT,
    stock_status        ENUM('in_stock','low_stock','out_of_stock','overstocked'),
    days_since_restock  INT,
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (product_key) REFERENCES dim_product(product_key),
    FOREIGN KEY (warehouse_key) REFERENCES dim_warehouse(warehouse_key),
    INDEX idx_date (date_key),
    INDEX idx_product (product_key)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- FACT: fact_shipments
-- ------------------------------------------------------------
CREATE TABLE fact_shipments (
    shipment_key        INT AUTO_INCREMENT PRIMARY KEY,
    date_key            INT NOT NULL,
    order_id            INT NOT NULL,
    warehouse_key       INT NOT NULL,
    shipped_date        DATE,
    delivered_date      DATE,
    delivery_days       INT,
    carrier             VARCHAR(100),
    shipping_cost       DECIMAL(8,2) DEFAULT 0.00,
    on_time_delivery    TINYINT(1),
    status              VARCHAR(20),
    FOREIGN KEY (date_key) REFERENCES dim_date(date_key),
    FOREIGN KEY (warehouse_key) REFERENCES dim_warehouse(warehouse_key),
    INDEX idx_date (date_key),
    INDEX idx_order (order_id)
) ENGINE=InnoDB;

-- ------------------------------------------------------------
-- Populate dim_date (2022-2025)
-- ------------------------------------------------------------
DELIMITER //

CREATE PROCEDURE sp_populate_dim_date(IN p_start_date DATE, IN p_end_date DATE)
BEGIN
    DECLARE v_date DATE DEFAULT p_start_date;

    WHILE v_date <= p_end_date DO
        INSERT INTO dim_date (
            date_key, full_date, year, quarter, month, month_name, week,
            day_of_month, day_of_week, day_name, is_weekend, is_holiday, fiscal_year
        ) VALUES (
            YEAR(v_date) * 10000 + MONTH(v_date) * 100 + DAY(v_date),
            v_date,
            YEAR(v_date),
            QUARTER(v_date),
            MONTH(v_date),
            MONTHNAME(v_date),
            WEEK(v_date),
            DAY(v_date),
            DAYOFWEEK(v_date),
            DAYNAME(v_date),
            IF(DAYOFWEEK(v_date) IN (1, 7), 1, 0),
            0,
            CONCAT('FY', YEAR(v_date))
        );

        SET v_date = DATE_ADD(v_date, INTERVAL 1 DAY);
    END WHILE;
END //

DELIMITER ;

-- ============================================================
-- ETL: Load dim_date for our data range
-- ============================================================
CALL sp_populate_dim_date('2022-01-01', '2025-12-31');

-- ============================================================
-- ETL: warehouse_load_dimensions.sql separate file
-- ============================================================
