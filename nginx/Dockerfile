# Custom Nginx Reverse Proxy with built-in OpenSSL self-signed TLS/HTTPS certificate generation
FROM nginx:alpine

RUN apk add --no-cache openssl && \
    mkdir -p /etc/nginx/certs && \
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
      -keyout /etc/nginx/certs/selfsigned.key \
      -out /etc/nginx/certs/selfsigned.crt \
      -subj "/C=IN/ST=Rajasthan/L=Jaipur/O=CapstoneAnalytics/CN=localhost" \
      -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80 443