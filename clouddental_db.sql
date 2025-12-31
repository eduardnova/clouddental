-- Tablas existentes (con mejoras aplicadas de todas las sugerencias)

CREATE TABLE accounts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    plan ENUM('basic', 'pro', 'enterprise') NOT NULL,
    stripe_customer_id VARCHAR(255),  -- ID de cliente en Stripe
    paypal_payer_id VARCHAR(255),     -- ID de payer en PayPal
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password VARCHAR(255),
    google_id VARCHAR(255),
    microsoft_id VARCHAR(255),
    role ENUM('platform_admin', 'account_admin', 'receptionist', 'dentist', 'employee') NOT NULL,
    name VARCHAR(255) NOT NULL,
    two_factor_secret VARCHAR(255),  -- Nuevo: Para 2FA (e.g., TOTP secret)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE patients (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    date_of_birth DATE,
    gender ENUM('male', 'female', 'other'),
    phone VARCHAR(50),
    email VARCHAR(255),
    address TEXT,
    attachments JSON,  -- Nuevo: Array de paths a archivos adjuntos (e.g., radiografías)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE branches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    address TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE appointments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    branch_id INT,
    patient_id INT NOT NULL,
    dentist_id INT NOT NULL,
    date_time DATETIME NOT NULL,
    status ENUM('scheduled', 'completed', 'cancelled') DEFAULT 'scheduled',
    notes TEXT,
    sync_id VARCHAR(255),  -- Nuevo: ID para sincronización con calendarios externos (e.g., Google Calendar)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE SET NULL,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (dentist_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE procedure_catalog (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE clinic_procedures (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    procedure_catalog_id INT NOT NULL,
    cost DECIMAL(10,2) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (procedure_catalog_id) REFERENCES procedure_catalog(id) ON DELETE CASCADE
);

CREATE TABLE patient_procedures (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    clinic_procedure_id INT NOT NULL,
    appointment_id INT,
    dentist_id INT NOT NULL,
    date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (clinic_procedure_id) REFERENCES clinic_procedures(id) ON DELETE CASCADE,
    FOREIGN KEY (appointment_id) REFERENCES appointments(id) ON DELETE SET NULL,
    FOREIGN KEY (dentist_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE prescriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    dentist_id INT NOT NULL,
    date DATE NOT NULL,
    details TEXT NOT NULL,
    attachments JSON,  -- Nuevo: Array de paths a archivos adjuntos (e.g., recetas escaneadas)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (dentist_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE supplies (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    branch_id INT,
    name VARCHAR(255) NOT NULL,
    quantity INT NOT NULL DEFAULT 0,
    unit VARCHAR(50),
    min_stock INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE SET NULL
);

CREATE TABLE supply_usages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    supply_id INT NOT NULL,
    patient_procedure_id INT,
    quantity_used INT NOT NULL,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (supply_id) REFERENCES supplies(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_procedure_id) REFERENCES patient_procedures(id) ON DELETE SET NULL
);

CREATE TABLE payrolls (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    status ENUM('pending', 'paid') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (employee_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE payment_types (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL UNIQUE
);

CREATE TABLE banks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    name VARCHAR(255) NOT NULL,
    account_number VARCHAR(100),
    account_type ENUM('checking', 'savings'),
    owner_name VARCHAR(255),
    id_number VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

CREATE TABLE payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    patient_id INT NOT NULL,
    patient_procedure_id INT,
    amount DECIMAL(10,2) NOT NULL,
    payment_type_id INT NOT NULL,
    bank_id INT,
    proof VARCHAR(255),
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_procedure_id) REFERENCES patient_procedures(id) ON DELETE SET NULL,
    FOREIGN KEY (payment_type_id) REFERENCES payment_types(id) ON DELETE RESTRICT,
    FOREIGN KEY (bank_id) REFERENCES banks(id) ON DELETE SET NULL
);

CREATE TABLE quotations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    patient_id INT NOT NULL,
    details TEXT NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    status ENUM('pending', 'accepted', 'rejected') DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

CREATE TABLE expenses (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    branch_id INT,
    category VARCHAR(100),
    amount DECIMAL(10,2) NOT NULL,
    description TEXT,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (branch_id) REFERENCES branches(id) ON DELETE SET NULL
);

CREATE TABLE permissions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    module VARCHAR(100) NOT NULL,
    access_level ENUM('read', 'write', 'none') DEFAULT 'none',
    UNIQUE KEY (user_id, module),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE TABLE subscriptions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    gateway ENUM('stripe', 'paypal') NOT NULL,
    subscription_id VARCHAR(255) NOT NULL,
    plan ENUM('basic', 'pro', 'enterprise') NOT NULL,
    status ENUM('active', 'trialing', 'past_due', 'canceled', 'unpaid', 'paused', 'suspended') NOT NULL DEFAULT 'active',
    start_date DATE NOT NULL,
    current_period_start DATE,
    current_period_end DATE,
    metadata JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    UNIQUE KEY (account_id, gateway)
);

CREATE TABLE subscription_payments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    subscription_id INT NOT NULL,
    gateway_invoice_id VARCHAR(255),
    amount DECIMAL(10,2) NOT NULL,
    status ENUM('paid', 'failed', 'pending', 'void') NOT NULL DEFAULT 'pending',
    payment_date DATE NOT NULL,
    failure_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (subscription_id) REFERENCES subscriptions(id) ON DELETE CASCADE
);

CREATE TABLE support_tickets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    user_id INT,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    status ENUM('open', 'in_progress', 'closed') DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Nueva tabla para notificaciones (sugerencia 1)
CREATE TABLE notifications (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    message TEXT NOT NULL,
    type ENUM('email', 'in_app', 'sms') NOT NULL,
    read_status BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Nueva tabla para reportes avanzados (sugerencia 3)
CREATE TABLE reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    account_id INT NOT NULL,
    type VARCHAR(100) NOT NULL,  -- e.g., 'monthly_income', 'supply_usage'
    data JSON NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (account_id) REFERENCES accounts(id) ON DELETE CASCADE
);

-- Nueva tabla para fidelidad/puntos (sugerencia 5)
CREATE TABLE loyalty_points (
    id INT AUTO_INCREMENT PRIMARY KEY,
    patient_id INT NOT NULL,
    points INT NOT NULL DEFAULT 0,
    redeemed INT DEFAULT 0,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
);

-- Nueva tabla para intentos de login (sugerencia 6)
CREATE TABLE login_attempts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    ip_address VARCHAR(45),
    success BOOLEAN NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- Nueva tabla para recursos/capacitación (sugerencia 9)
CREATE TABLE resources (
    id INT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    category VARCHAR(100),  -- e.g., 'procedures', 'training'
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE audit_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    table_name VARCHAR(100) NOT NULL,
    record_id INT NOT NULL,
    action ENUM('insert', 'update', 'delete') NOT NULL,
    old_data JSON,
    new_data JSON,
    user_id INT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

-- Optimizaciones: Agregar índices (sugerencia 10)
ALTER TABLE appointments ADD INDEX idx_account_date (account_id, date_time);
ALTER TABLE payments ADD INDEX idx_account_date (account_id, date);
ALTER TABLE expenses ADD INDEX idx_account_date (account_id, date);
ALTER TABLE subscriptions ADD INDEX idx_account_status (account_id, status);
ALTER TABLE notifications ADD INDEX idx_user_read (user_id, read_status);
ALTER TABLE loyalty_points ADD INDEX idx_patient_points (patient_id);

-- Triggers para todas las tablas (extendidos a nuevas)

DELIMITER //
CREATE TRIGGER accounts_insert AFTER INSERT ON accounts
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_data, user_id)
    VALUES ('accounts', NEW.id, 'insert', JSON_OBJECT('name', NEW.name, 'plan', NEW.plan, 'stripe_customer_id', NEW.stripe_customer_id, 'paypal_payer_id', NEW.paypal_payer_id), NULL);
END;
//

CREATE TRIGGER accounts_update BEFORE UPDATE ON accounts
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, new_data, user_id)
    VALUES ('accounts', OLD.id, 'update', JSON_OBJECT('name', OLD.name, 'plan', OLD.plan, 'stripe_customer_id', OLD.stripe_customer_id, 'paypal_payer_id', OLD.paypal_payer_id), JSON_OBJECT('name', NEW.name, 'plan', NEW.plan, 'stripe_customer_id', NEW.stripe_customer_id, 'paypal_payer_id', NEW.paypal_payer_id), NULL);
END;
//

CREATE TRIGGER accounts_delete BEFORE DELETE ON accounts
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, user_id)
    VALUES ('accounts', OLD.id, 'delete', JSON_OBJECT('name', OLD.name, 'plan', OLD.plan, 'stripe_customer_id', OLD.stripe_customer_id, 'paypal_payer_id', OLD.paypal_payer_id), NULL);
END;
//
DELIMITER ;

DELIMITER //
CREATE TRIGGER users_insert AFTER INSERT ON users
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_data, user_id)
    VALUES ('users', NEW.id, 'insert', JSON_OBJECT('account_id', NEW.account_id, 'email', NEW.email, 'role', NEW.role, 'name', NEW.name, 'two_factor_secret', NEW.two_factor_secret), NULL);
END;
//

CREATE TRIGGER users_update BEFORE UPDATE ON users
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, new_data, user_id)
    VALUES ('users', OLD.id, 'update', JSON_OBJECT('account_id', OLD.account_id, 'email', OLD.email, 'role', OLD.role, 'name', OLD.name, 'two_factor_secret', OLD.two_factor_secret), JSON_OBJECT('account_id', NEW.account_id, 'email', NEW.email, 'role', NEW.role, 'name', NEW.name, 'two_factor_secret', NEW.two_factor_secret), NULL);
END;
//

CREATE TRIGGER users_delete BEFORE DELETE ON users
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, user_id)
    VALUES ('users', OLD.id, 'delete', JSON_OBJECT('account_id', OLD.account_id, 'email', OLD.email, 'role', OLD.role, 'name', OLD.name, 'two_factor_secret', OLD.two_factor_secret), NULL);
END;
//
DELIMITER ;

DELIMITER //
CREATE TRIGGER patients_insert AFTER INSERT ON patients
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_data, user_id)
    VALUES ('patients', NEW.id, 'insert', JSON_OBJECT('account_id', NEW.account_id, 'name', NEW.name, 'date_of_birth', NEW.date_of_birth, 'attachments', NEW.attachments), NULL);
END;
//

CREATE TRIGGER patients_update BEFORE UPDATE ON patients
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, new_data, user_id)
    VALUES ('patients', OLD.id, 'update', JSON_OBJECT('account_id', OLD.account_id, 'name', OLD.name, 'date_of_birth', OLD.date_of_birth, 'attachments', OLD.attachments), JSON_OBJECT('account_id', NEW.account_id, 'name', NEW.name, 'date_of_birth', NEW.date_of_birth, 'attachments', NEW.attachments), NULL);
END;
//

CREATE TRIGGER patients_delete BEFORE DELETE ON patients
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, user_id)
    VALUES ('patients', OLD.id, 'delete', JSON_OBJECT('account_id', OLD.account_id, 'name', OLD.name, 'date_of_birth', OLD.date_of_birth, 'attachments', OLD.attachments), NULL);
END;
//
DELIMITER ;

DELIMITER //
CREATE TRIGGER appointments_insert AFTER INSERT ON appointments
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_data, user_id)
    VALUES ('appointments', NEW.id, 'insert', JSON_OBJECT('account_id', NEW.account_id, 'patient_id', NEW.patient_id, 'dentist_id', NEW.dentist_id, 'date_time', NEW.date_time, 'sync_id', NEW.sync_id), NULL);
    -- Trigger para notificación automática (sugerencia 1)
    INSERT INTO notifications (user_id, message, type)
    VALUES (NEW.dentist_id, CONCAT('Nueva cita programada para ', NEW.date_time), 'in_app');
END;
//

CREATE TRIGGER appointments_update BEFORE UPDATE ON appointments
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, new_data, user_id)
    VALUES ('appointments', OLD.id, 'update', JSON_OBJECT('account_id', OLD.account_id, 'patient_id', OLD.patient_id, 'dentist_id', OLD.dentist_id, 'date_time', OLD.date_time, 'sync_id', OLD.sync_id), JSON_OBJECT('account_id', NEW.account_id, 'patient_id', NEW.patient_id, 'dentist_id', NEW.dentist_id, 'date_time', NEW.date_time, 'sync_id', NEW.sync_id), NULL);
END;
//

CREATE TRIGGER appointments_delete BEFORE DELETE ON appointments
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, user_id)
    VALUES ('appointments', OLD.id, 'delete', JSON_OBJECT('account_id', OLD.account_id, 'patient_id', OLD.patient_id, 'dentist_id', OLD.dentist_id, 'date_time', OLD.date_time, 'sync_id', OLD.sync_id), NULL);
END;
//
DELIMITER ;

DELIMITER //
CREATE TRIGGER prescriptions_insert AFTER INSERT ON prescriptions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_data, user_id)
    VALUES ('prescriptions', NEW.id, 'insert', JSON_OBJECT('patient_id', NEW.patient_id, 'dentist_id', NEW.dentist_id, 'date', NEW.date, 'attachments', NEW.attachments), NULL);
END;
//

CREATE TRIGGER prescriptions_update BEFORE UPDATE ON prescriptions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, new_data, user_id)
    VALUES ('prescriptions', OLD.id, 'update', JSON_OBJECT('patient_id', OLD.patient_id, 'dentist_id', OLD.dentist_id, 'date', OLD.date, 'attachments', OLD.attachments), JSON_OBJECT('patient_id', NEW.patient_id, 'dentist_id', NEW.dentist_id, 'date', NEW.date, 'attachments', NEW.attachments), NULL);
END;
//

CREATE TRIGGER prescriptions_delete BEFORE DELETE ON prescriptions
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, user_id)
    VALUES ('prescriptions', OLD.id, 'delete', JSON_OBJECT('patient_id', OLD.patient_id, 'dentist_id', OLD.dentist_id, 'date', OLD.date, 'attachments', OLD.attachments), NULL);
END;
//
DELIMITER ;

DELIMITER //
CREATE TRIGGER supplies_update AFTER UPDATE ON supplies
FOR EACH ROW
BEGIN
    IF NEW.quantity < NEW.min_stock THEN
        INSERT INTO notifications (user_id, message, type)
        SELECT id, CONCAT('Bajo stock en ', NEW.name), 'in_app' FROM users WHERE role = 'account_admin' AND account_id = NEW.account_id LIMIT 1;
    END IF;
    INSERT INTO audit_logs (table_name, record_id, action, old_data, new_data, user_id)
    VALUES ('supplies', OLD.id, 'update', JSON_OBJECT('quantity', OLD.quantity), JSON_OBJECT('quantity', NEW.quantity), NULL);
END;
//
DELIMITER ;

-- Triggers para las tablas restantes (branches, procedure_catalog, clinic_procedures, patient_procedures, supply_usages, payrolls, payment_types, banks, payments, quotations, expenses, permissions, subscriptions, subscription_payments, support_tickets) se mantienen como en versiones anteriores.

-- Nuevos triggers para notifications
DELIMITER //
CREATE TRIGGER notifications_insert AFTER INSERT ON notifications
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_data, user_id)
    VALUES ('notifications', NEW.id, 'insert', JSON_OBJECT('user_id', NEW.user_id, 'message', NEW.message, 'type', NEW.type), NULL);
END;
//

CREATE TRIGGER notifications_update BEFORE UPDATE ON notifications
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, new_data, user_id)
    VALUES ('notifications', OLD.id, 'update', JSON_OBJECT('user_id', OLD.user_id, 'message', OLD.message, 'type', OLD.type), JSON_OBJECT('user_id', NEW.user_id, 'message', NEW.message, 'type', NEW.type), NULL);
END;
//

CREATE TRIGGER notifications_delete BEFORE DELETE ON notifications
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, user_id)
    VALUES ('notifications', OLD.id, 'delete', JSON_OBJECT('user_id', OLD.user_id, 'message', OLD.message, 'type', OLD.type), NULL);
END;
//
DELIMITER ;

-- Triggers para reports
DELIMITER //
CREATE TRIGGER reports_insert AFTER INSERT ON reports
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_data, user_id)
    VALUES ('reports', NEW.id, 'insert', JSON_OBJECT('account_id', NEW.account_id, 'type', NEW.type), NULL);
END;
//

CREATE TRIGGER reports_update BEFORE UPDATE ON reports
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, new_data, user_id)
    VALUES ('reports', OLD.id, 'update', JSON_OBJECT('account_id', OLD.account_id, 'type', OLD.type), JSON_OBJECT('account_id', NEW.account_id, 'type', NEW.type), NULL);
END;
//

CREATE TRIGGER reports_delete BEFORE DELETE ON reports
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, user_id)
    VALUES ('reports', OLD.id, 'delete', JSON_OBJECT('account_id', OLD.account_id, 'type', OLD.type), NULL);
END;
//
DELIMITER ;

-- Triggers para loyalty_points
DELIMITER //
CREATE TRIGGER loyalty_points_insert AFTER INSERT ON loyalty_points
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_data, user_id)
    VALUES ('loyalty_points', NEW.id, 'insert', JSON_OBJECT('patient_id', NEW.patient_id, 'points', NEW.points), NULL);
END;
//

CREATE TRIGGER loyalty_points_update BEFORE UPDATE ON loyalty_points
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, new_data, user_id)
    VALUES ('loyalty_points', OLD.id, 'update', JSON_OBJECT('patient_id', OLD.patient_id, 'points', OLD.points), JSON_OBJECT('patient_id', NEW.patient_id, 'points', NEW.points), NULL);
END;
//

CREATE TRIGGER loyalty_points_delete BEFORE DELETE ON loyalty_points
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, user_id)
    VALUES ('loyalty_points', OLD.id, 'delete', JSON_OBJECT('patient_id', OLD.patient_id, 'points', OLD.points), NULL);
END;
//

-- Ejemplo: Agregar puntos por pago
CREATE TRIGGER payments_insert AFTER INSERT ON payments
FOR EACH ROW
BEGIN
    UPDATE loyalty_points SET points = points + FLOOR(NEW.amount / 10) WHERE patient_id = NEW.patient_id;
END;
//
DELIMITER ;

-- Triggers para login_attempts
DELIMITER //
CREATE TRIGGER login_attempts_insert AFTER INSERT ON login_attempts
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_data, user_id)
    VALUES ('login_attempts', NEW.id, 'insert', JSON_OBJECT('user_id', NEW.user_id, 'success', NEW.success), NULL);
END;
//
DELIMITER ;

-- Triggers para resources
DELIMITER //
CREATE TRIGGER resources_insert AFTER INSERT ON resources
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, new_data, user_id)
    VALUES ('resources', NEW.id, 'insert', JSON_OBJECT('title', NEW.title, 'category', NEW.category), NULL);
END;
//

CREATE TRIGGER resources_update BEFORE UPDATE ON resources
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, new_data, user_id)
    VALUES ('resources', OLD.id, 'update', JSON_OBJECT('title', OLD.title, 'category', OLD.category), JSON_OBJECT('title', NEW.title, 'category', NEW.category), NULL);
END;
//

CREATE TRIGGER resources_delete BEFORE DELETE ON resources
FOR EACH ROW
BEGIN
    INSERT INTO audit_logs (table_name, record_id, action, old_data, user_id)
    VALUES ('resources', OLD.id, 'delete', JSON_OBJECT('title', OLD.title, 'category', OLD.category), NULL);
END;
//
DELIMITER ;

-- Vistas adicionales para análisis y reportes (sugerencias 3 y 7)
CREATE VIEW monthly_income AS
SELECT account_id, YEAR(date) AS year, MONTH(date) AS month, SUM(amount) AS income
FROM payments
GROUP BY account_id, year, month;

CREATE VIEW supply_usage_report AS
SELECT s.name, SUM(su.quantity_used) AS total_used
FROM supplies s
JOIN supply_usages su ON s.id = su.supply_id
GROUP BY s.id;

CREATE VIEW total_accounts_by_plan AS
SELECT plan, COUNT(id) AS count
FROM accounts
GROUP BY plan;

CREATE VIEW churn_rate AS
SELECT COUNT(CASE WHEN status = 'canceled' THEN 1 END) / COUNT(*) * 100 AS churn_percentage
FROM subscriptions;

-- Procedimientos almacenados para dashboard (sugerencia 10)
DELIMITER //
CREATE PROCEDURE get_dashboard_stats(IN acc_id INT)
BEGIN
    SELECT 
        SUM(p.amount) AS income,
        SUM(e.amount) AS expenses,
        SUM(p.amount) - SUM(e.amount) AS profits,
        COUNT(a.id) AS appointments_count
    FROM payments p
    LEFT JOIN expenses e ON p.account_id = e.account_id
    LEFT JOIN appointments a ON p.account_id = a.account_id
    WHERE p.account_id = acc_id;
END;
//
DELIMITER ;

-- Vista existente actualizada
CREATE VIEW view_subscription_revenue AS
SELECT 
    a.id AS account_id,
    a.plan,
    SUM(sp.amount) AS total_revenue,
    COUNT(sp.id) AS payment_count
FROM accounts a
LEFT JOIN subscriptions s ON a.id = s.account_id
LEFT JOIN subscription_payments sp ON s.id = sp.subscription_id
WHERE sp.status = 'paid'
GROUP BY a.id;

CREATE VIEW view_overall_dashboard AS
SELECT 
    COUNT(a.id) AS total_accounts,
    SUM(CASE WHEN s.status = 'active' THEN 1 ELSE 0 END) AS active_subscriptions,
    SUM(sp.amount) AS total_income,
    SUM(e.amount) AS total_expenses,
    SUM(sp.amount) - SUM(e.amount) AS profits
FROM accounts a
LEFT JOIN subscriptions s ON a.id = s.account_id
LEFT JOIN subscription_payments sp ON s.id = sp.subscription_id
LEFT JOIN expenses e ON a.id = e.account_id;