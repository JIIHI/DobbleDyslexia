# Word Spot online - for hosting on Fly.io, Render, Railway, a VPS, etc.
FROM python:3.12-slim
WORKDIR /app
COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt
COPY wordspot ./wordspot
ENV PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "python -m wordspot.online --port ${PORT}"]
