storage "file" {
  path = "/vault/data"
}

listener "tcp" {
  address       = "0.0.0.0:8200"
  tls_cert_file = "/vault/certs/vault.crt"
  tls_key_file  = "/vault/certs/vault.key"
}

# Biến thể production-intent: TLS native trong Vault.
# Stack lab (docker-compose.yml gốc) terminate TLS ở nginx và giữ Vault
# HTTP nội bộ; xem docs/evidence/T13_2026-11-16.md.
api_addr = "https://127.0.0.1:8200"

disable_mlock = true
ui = true