# Central Comercial — imagem única (painel + API + agentes)
FROM node:22-alpine AS construcao
WORKDIR /app
COPY package.json package-lock.json ./
COPY server/package.json server/
COPY web/package.json web/
RUN npm ci
COPY . .
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production TZ=America/Sao_Paulo CAMINHO_BANCO=/dados/comercial.db
RUN apk add --no-cache tzdata
COPY package.json package-lock.json ./
COPY server/package.json server/
COPY web/package.json web/
RUN npm ci --omit=dev -w server && npm cache clean --force
COPY server/src server/src
COPY --from=construcao /app/web/dist web/dist
VOLUME /dados
EXPOSE 3333
WORKDIR /app/server
CMD ["node", "--disable-warning=ExperimentalWarning", "src/index.ts"]
