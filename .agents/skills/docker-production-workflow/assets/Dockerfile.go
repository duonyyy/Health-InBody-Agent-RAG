# syntax=docker/dockerfile:1
# TEMPLATE: Chỉnh Go version đúng go.mod, APP_PATH, port, CGO và base digest theo repo.
ARG GO_VERSION=1.25
FROM --platform=$BUILDPLATFORM golang:${GO_VERSION}-bookworm AS builder
WORKDIR /src

# Nếu repo chưa có go.sum, tạo qua go mod tidy có kiểm soát trước khi build.
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod \
    go mod download

COPY . .
ARG TARGETOS
ARG TARGETARCH
ARG APP_PATH=./cmd/api
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=${TARGETOS} GOARCH=${TARGETARCH} \
    go build -trimpath -ldflags='-s -w' -o /out/app "${APP_PATH}"

FROM gcr.io/distroless/static-debian12:nonroot AS runtime
WORKDIR /
COPY --from=builder --chown=65532:65532 /out/app /app
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/app"]
