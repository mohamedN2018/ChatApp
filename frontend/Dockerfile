# Multi-stage build for the Nuxt 3 frontend.
#   build   -> installs deps and produces the Nitro server bundle (.output)
#   runtime -> slim Node image running the server bundle
FROM node:20-alpine AS build
WORKDIR /app
ENV NUXT_TELEMETRY_DISABLED=1
COPY package.json ./
RUN npm install
COPY . .
RUN npm run build

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production \
    NUXT_TELEMETRY_DISABLED=1 \
    HOST=0.0.0.0 \
    PORT=3000
COPY --from=build /app/.output ./.output
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
