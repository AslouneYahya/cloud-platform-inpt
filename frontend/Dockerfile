# =============================================================================
# frontend/Dockerfile — Vite / React development server
# =============================================================================

FROM node:20-alpine

WORKDIR /app

# Copy manifest files first to exploit layer caching for node_modules.
COPY package*.json .

RUN npm install

# Copy the rest of the application source.
COPY . .

EXPOSE 5173

# Bind to 0.0.0.0 so that the Vite server is reachable from outside the
# container (required when nginx proxies requests into this container).
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
