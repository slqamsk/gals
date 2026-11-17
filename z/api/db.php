<?php
// /z/api/db.php
// Подключение к MySQL через .env, проверка ключа, установка схемы.

require_once __DIR__ . '/env_loader.php';

function get_pdo(): PDO {
    static $pdo = null;
    if ($pdo === null) {
        $dsn = sprintf(
            'mysql:host=%s;dbname=%s;charset=utf8mb4',
            env('DB_HOST', 'localhost'),
            env('DB_NAME', '')
        );
        $pdo = new PDO($dsn, env('DB_USER', ''), env('DB_PASS', ''), [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            PDO::ATTR_EMULATE_PREPARES   => false,
        ]);
    }
    return $pdo;
}

function check_api_key(): void {
    $expected = env('API_KEY', '');
    $key = $_SERVER['HTTP_X_API_KEY'] ?? '';
    if (!hash_equals($expected, $key)) {
        http_response_code(401);
        echo json_encode(['error' => 'unauthorized']);
        exit;
    }
}

function ensure_schema(): array {
    $pdo = get_pdo();

    $exists = $pdo->query("SHOW TABLES LIKE 'sleep_events'")->fetchColumn();
    if ($exists) {
        return ['action' => 'exists', 'table' => 'sleep_events'];
    }

    $pdo->exec("
        CREATE TABLE sleep_events (
            id          INT AUTO_INCREMENT PRIMARY KEY,
            event_type  ENUM('wake','sleep') NOT NULL,
            event_time  DATETIME NOT NULL,
            created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced      BOOLEAN DEFAULT FALSE,
            INDEX idx_synced (synced),
            INDEX idx_event_time (event_time)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    ");

    return ['action' => 'created', 'table' => 'sleep_events'];
}