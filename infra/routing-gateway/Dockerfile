# Pin the nginx base to an audited digest before enabling public deployment.
FROM nginx:stable-alpine
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY 01-validate-upstreams.sh /docker-entrypoint.d/01-validate-upstreams.sh
RUN chmod 0755 /docker-entrypoint.d/01-validate-upstreams.sh
