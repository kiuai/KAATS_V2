FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci

# ── Development target ────────────────────────────────────────────────────────
FROM base AS development
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# ── Build ──────────────────────────────────────────────────────────────────────
FROM base AS builder
ARG VITE_AZURE_CLIENT_ID
ARG VITE_AZURE_TENANT_ID
ENV VITE_AZURE_CLIENT_ID=$VITE_AZURE_CLIENT_ID
ENV VITE_AZURE_TENANT_ID=$VITE_AZURE_TENANT_ID
COPY . .
RUN npx vite build

# ── Production target ─────────────────────────────────────────────────────────
FROM nginx:1.26-alpine AS production
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
