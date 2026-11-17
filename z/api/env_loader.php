<?php
// /z/api/env_loader.php
// Минимальный парсер .env (без composer).
// Читает KEY=VALUE, игнорирует пустые строки и #-комментарии.
// Значения в кавычках ("..." или '...') сохраняются как есть, без кавычек.

function load_env(): array {
    static $env = null;
    if ($env !== null) {
        return $env;
    }

    // Единственный путь: z/api/ → ../config/.env → z/config/.env
    $path = realpath(__DIR__ . '/../config/.env');

    if ($path === false || !is_file($path)) {
        http_response_code(500);
        echo json_encode([
            'error' => 'env_not_found',
            'expected' => 'z/config/.env (рядом с z/api/)',
        ]);
        exit;
    }

    $env = [];
    $lines = file($path, FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);
    foreach ($lines as $line) {
        $line = trim($line);
        if ($line === '' || $line[0] === '#') {
            continue;
        }
        $eq = strpos($line, '=');
        if ($eq === false) {
            continue;
        }
        $key = trim(substr($line, 0, $eq));
        $val = trim(substr($line, $eq + 1));
        // Снимаем парные кавычки
        if (strlen($val) >= 2
            && (($val[0] === '"' && $val[strlen($val) - 1] === '"')
                || ($val[0] === "'" && $val[strlen($val) - 1] === "'"))) {
            $val = substr($val, 1, -1);
        }
        $env[$key] = $val;
    }

    return $env;
}

function env(string $key, ?string $default = null): ?string {
    $env = load_env();
    return $env[$key] ?? $default;
}