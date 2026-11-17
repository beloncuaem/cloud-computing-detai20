#!/usr/bin/env bash
# Sinh CA lab tự ký + cert server cho nginx / postgres / vault.
# CHỈ dùng cho lab. Private key không được commit (.gitignore chặn *.key, *.pem).
# Chạy: bash infrastructure/certs/gen-certs.sh   (cần openssl >= 3)
set -euo pipefail
cd "$(dirname "$0")"

DAYS=365
mkdir -p out

if [ ! -f out/ca.key ]; then
  openssl req -x509 -newkey rsa:4096 -sha256 -days "$DAYS" -nodes \
    -keyout out/ca.key -out out/ca.crt \
    -subj "/C=VN/O=UTH Lab/CN=UTH Lab CA" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign"
fi

gen_server() {
  local name="$1" san="$2"
  openssl req -newkey rsa:2048 -sha256 -nodes \
    -keyout "out/${name}.key" -out "out/${name}.csr" \
    -subj "/C=VN/O=UTH Lab/CN=${name}"
  printf "subjectAltName=%s\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth\n" "$san" > "out/${name}.ext"
  openssl x509 -req -in "out/${name}.csr" -CA out/ca.crt -CAkey out/ca.key \
    -CAcreateserial -days "$DAYS" -sha256 -out "out/${name}.crt" \
    -extfile "out/${name}.ext"
  rm -f "out/${name}.csr" "out/${name}.ext"
}

gen_server nginx  "DNS:localhost,DNS:nginx,DNS:api,IP:127.0.0.1"
gen_server postgres "DNS:postgres,DNS:localhost,IP:127.0.0.1"
gen_server vault  "DNS:vault,DNS:localhost,IP:127.0.0.1"

chmod 600 out/*.key
echo "OK: out/ca.crt out/{nginx,postgres,vault}.{crt,key}"