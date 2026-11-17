<?php
// /z/api/index.php — front controller.
// Маршруты:
//   POST   /z/api/install        — создать таблицу sleep_events (если нет)
//   POST   /z/api/events/        — создать событие
//   GET    /z/api/events/        — получить несинхронизированные события
//   DELETE /z/api/events/{id}    — удалить событие по id

require __DIR__ . '/db.php';

header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(204);
    exit;
}

check_api_key();

$request_uri = parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH);
$path = preg_replace('#^/z/api#', '', $request_uri);
$path = rtrim($path, '/');
$method = $_SERVER['REQUEST_METHOD'];

try {
    if ($method === 'POST' && $path === '/install') {
        echo json_encode(ensure_schema());
        exit;
    }

    if ($method === 'POST' && $path === '/events') {
        handle_create_event();
        exit;
    }

    if ($method === 'GET' && $path === '/events') {
        handle_list_events();
        exit;
    }

    if ($method === 'DELETE' && preg_match('#^/events/(\d+)$#', $path, $m)) {
        handle_delete_event((int)$m[1]);
        exit;
    }

    http_response_code(404);
    echo json_encode(['error' => 'not_found', 'path' => $path, 'method' => $method]);

} catch (PDOException $e) {
    error_log('[z/api] PDO error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'db_error']);
} catch (Throwable $e) {
    error_log('[z/api] error: ' . $e->getMessage());
    http_response_code(500);
    echo json_encode(['error' => 'internal_error']);
}

function handle_create_event(): void {
    $body = json_decode(file_get_contents('php://input'), true);

    if (!is_array($body)
        || !in_array($body['event_type'] ?? '', ['wake', 'sleep'], true)
        || empty($body['event_time'])) {
        http_response_code(400);
        echo json_encode(['error' => 'invalid_body', 'received' => $body]);
        return;
    }

    $ts = strtotime($body['event_time']);
    if ($ts === false) {
        http_response_code(400);
        echo json_encode(['error' => 'invalid_event_time']);
        return;
    }
    $time_mysql = gmdate('Y-m-d H:i:s', $ts);

    $pdo = get_pdo();
    $stmt = $pdo->prepare(
        'INSERT INTO sleep_events (event_type, event_time) VALUES (:type, :time)'
    );
    $stmt->execute([':type' => $body['event_type'], ':time' => $time_mysql]);
    $id = (int)$pdo->lastInsertId();

    http_response_code(201);
    echo json_encode([
        'id'         => $id,
        'event_type' => $body['event_type'],
        'event_time' => $time_mysql,
    ]);
}

function handle_list_events(): void {
    $pdo = get_pdo();
    $rows = $pdo->query(
        'SELECT id, event_type, event_time, created_at
         FROM sleep_events WHERE synced = 0
         ORDER BY event_time ASC, id ASC'
    )->fetchAll();

    foreach ($rows as &$r) {
        $r['id'] = (int)$r['id'];
    }
    unset($r);

    echo json_encode($rows);
}

function handle_delete_event(int $id): void {
    $pdo = get_pdo();
    $stmt = $pdo->prepare('DELETE FROM sleep_events WHERE id = :id');
    $stmt->execute([':id' => $id]);

    if ($stmt->rowCount() === 0) {
        http_response_code(404);
        echo json_encode(['error' => 'not_found', 'id' => $id]);
        return;
    }

    http_response_code(204);
}