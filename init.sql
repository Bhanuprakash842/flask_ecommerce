CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    description TEXT NOT NULL,
    price FLOAT NOT NULL,
    category VARCHAR(50) NOT NULL,
    image_base64 TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO products (name, description, price, category, image_base64) VALUES
('Nova Headphones', 'Premium wireless noise-cancelling headphones for an immersive experience.', 199.99, 'Electronics', NULL),
('Smart Watch Pro', 'Tracks your health, notifications, and fitness goals with style.', 249.50, 'Wearables', NULL),
('Minimalist Lamp', 'Sleek wooden base lamp for a modern and warm workspace ambiance.', 45.00, 'Home Decor', NULL);
