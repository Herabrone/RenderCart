# Build stage
FROM node:20-alpine AS build

WORKDIR /app

COPY package*.json ./
COPY vite.config.js ./
COPY public ./public
COPY src ./src

RUN npm install
RUN npm run build

# Production stage
FROM nginx:stable-alpine

# Copy built assets from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]