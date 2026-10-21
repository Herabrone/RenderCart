FROM python:3.13-slim
WORKDIR /app
COPY infra/egress-proxy/proxy.py ./proxy.py
# The proxy only opens outbound sockets and serves files already copied into
# the image, so use the base image's unprivileged account without reserving a
# fixed UID/GID that may collide with upstream image changes.
USER nobody
EXPOSE 3128
ENTRYPOINT ["python", "-B", "/app/proxy.py"]
