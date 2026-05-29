FROM nginx:alpine

# Create SSL directory
RUN mkdir -p /etc/nginx/ssl

# Copy nginx config
COPY nginx.conf /etc/nginx/nginx.conf

# Copy SSL certificates
COPY ssl/cert.pem /etc/nginx/ssl/cert.pem
COPY ssl/key.pem /etc/nginx/ssl/key.pem

# Copy web files
COPY index.html /usr/share/nginx/html/
COPY app.js /usr/share/nginx/html/
COPY styles.css /usr/share/nginx/html/

# Expose ports
EXPOSE 80 443

CMD ["nginx", "-g", "daemon off;"]
