FROM python:3.13-slim
WORKDIR /app
COPY infra/egress-proxy/proxy.py ./proxy.py
RUN groupadd --gid 10002 proxy && useradd --uid 10002 --gid proxy --no-create-home --shell /usr/sbin/nologin proxy
USER 10002:10002
EXPOSE 3128
ENTRYPOINT ["python", "-B", "/app/proxy.py"]
