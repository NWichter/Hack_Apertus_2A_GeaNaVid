FROM nginx:alpine
RUN apk add --no-cache apache2-utils
COPY auth.sh /docker-entrypoint.d/05-auth.sh
RUN chmod +x /docker-entrypoint.d/05-auth.sh
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html 404.html style.css og.png report.pdf /usr/share/nginx/html/
COPY assets /usr/share/nginx/html/assets
COPY pitch/index.html pitch/pitch.css pitch/pitch.js pitch/pitch.pdf pitch/og.png /usr/share/nginx/html/pitch/
COPY demo /usr/share/nginx/html/demo/
EXPOSE 80
