#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
GENERATED_DIR="$ROOT_DIR/infra/azure/generated"
mkdir -p "$GENERATED_DIR"

require_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

slugify() {
  printf "%s" "$1" \
    | tr "[:upper:]" "[:lower:]" \
    | sed -E "s/[^a-z0-9-]+/-/g; s/^-+//; s/-+$//; s/-+/-/g"
}

acr_slugify() {
  printf "%s" "$1" | tr "[:upper:]" "[:lower:]" | tr -cd "a-z0-9"
}

url_encode() {
  python3 -c "import sys, urllib.parse; print(urllib.parse.quote(sys.argv[1], safe=''))" "$1"
}

pem_to_env() {
  python3 -c "import pathlib, sys; print(pathlib.Path(sys.argv[1]).read_text().replace('\r\n', '\n').replace('\n', '\\n'))" "$1"
}

az_resource_exists() {
  az "$@" >/dev/null 2>&1
}

require_command az
require_command openssl
require_command python3

APP_NAME_PREFIX="$(slugify "${APP_NAME_PREFIX:-allora}")"
AZURE_LOCATION="${AZURE_LOCATION:-eastus}"
AZURE_RESOURCE_GROUP="${AZURE_RESOURCE_GROUP:-rg-${APP_NAME_PREFIX}-dev}"
IMAGE_TAG="${IMAGE_TAG:-$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}"

SUBSCRIPTION_ID="$(az account show --query id -o tsv)"
UNIQUE_SUFFIX="${AZURE_UNIQUE_SUFFIX:-$(printf "%s" "$SUBSCRIPTION_ID" | tr -cd "a-zA-Z0-9" | tr "[:upper:]" "[:lower:]" | cut -c1-8)}"
ACR_PREFIX="$(acr_slugify "$APP_NAME_PREFIX")"
AZURE_ACR_NAME="${AZURE_ACR_NAME:-${ACR_PREFIX}acr${UNIQUE_SUFFIX}}"
AZURE_COSMOS_ACCOUNT_NAME="${AZURE_COSMOS_ACCOUNT_NAME:-${APP_NAME_PREFIX}-mongo-${UNIQUE_SUFFIX}}"
AZURE_REDIS_NAME="${AZURE_REDIS_NAME:-${APP_NAME_PREFIX}-redis-${UNIQUE_SUFFIX}}"
CONTAINERAPPS_ENVIRONMENT="${CONTAINERAPPS_ENVIRONMENT:-${APP_NAME_PREFIX}-aca-env}"

AUTH_APP_NAME="${AUTH_APP_NAME:-auth-service}"
CHAT_APP_NAME="${CHAT_APP_NAME:-chat-service}"
GATEWAY_APP_NAME="${GATEWAY_APP_NAME:-api-gateway}"

MONGO_DB_NAME="${MONGO_DB_NAME:-allora_auth}"
CHAT_MONGO_DB_NAME="${CHAT_MONGO_DB_NAME:-allora_chat}"
CHAT_EVENTS_EXCHANGE="${CHAT_EVENTS_EXCHANGE:-allora.chat.events}"
COSMOS_MONGO_SERVER_VERSION="${COSMOS_MONGO_SERVER_VERSION:-7.0}"
COSMOS_DB_THROUGHPUT="${COSMOS_DB_THROUGHPUT:-400}"

AUTH_MIN_REPLICAS="${AUTH_MIN_REPLICAS:-1}"
AUTH_MAX_REPLICAS="${AUTH_MAX_REPLICAS:-3}"
CHAT_MIN_REPLICAS="${CHAT_MIN_REPLICAS:-1}"
CHAT_MAX_REPLICAS="${CHAT_MAX_REPLICAS:-1}"
GATEWAY_MIN_REPLICAS="${GATEWAY_MIN_REPLICAS:-1}"
GATEWAY_MAX_REPLICAS="${GATEWAY_MAX_REPLICAS:-3}"

JWT_SECRET="${JWT_SECRET:-$(openssl rand -hex 32)}"
JWT_ALGORITHM="${JWT_ALGORITHM:-RS256}"
JWT_EXPIRE_MINUTES="${JWT_EXPIRE_MINUTES:-60}"
JWT_ISSUER="${JWT_ISSUER:-auth-service}"
JWT_KEY_ID="${JWT_KEY_ID:-allora-auth-key-1}"
REFRESH_TOKEN_EXPIRE_DAYS="${REFRESH_TOKEN_EXPIRE_DAYS:-30}"
VERIFICATION_CODE_EXPIRE_MINUTES="${VERIFICATION_CODE_EXPIRE_MINUTES:-10}"
DEV_RETURN_CODES="${DEV_RETURN_CODES:-false}"

JWT_PRIVATE_KEY_FILE="${JWT_PRIVATE_KEY_FILE:-$GENERATED_DIR/jwt-private.pem}"
JWT_PUBLIC_KEY_FILE="${JWT_PUBLIC_KEY_FILE:-$GENERATED_DIR/jwt-public.pem}"

echo "Using resource group: $AZURE_RESOURCE_GROUP"
echo "Using location: $AZURE_LOCATION"
echo "Using image tag: $IMAGE_TAG"

az extension add --name containerapp --upgrade >/dev/null

az group create \
  --name "$AZURE_RESOURCE_GROUP" \
  --location "$AZURE_LOCATION" \
  --output none

if ! az_resource_exists acr show --name "$AZURE_ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP"; then
  az acr create \
    --name "$AZURE_ACR_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --sku Basic \
    --admin-enabled true \
    --output none
fi

ACR_LOGIN_SERVER="$(az acr show --name "$AZURE_ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query loginServer -o tsv)"
ACR_USERNAME="$(az acr credential show --name "$AZURE_ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query username -o tsv)"
ACR_PASSWORD="$(az acr credential show --name "$AZURE_ACR_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query passwords[0].value -o tsv)"

echo "Building container images in ACR..."
az acr build --registry "$AZURE_ACR_NAME" --image "allora-auth:${IMAGE_TAG}" "$ROOT_DIR/services/auth-service" --output none
az acr build --registry "$AZURE_ACR_NAME" --image "allora-chat:${IMAGE_TAG}" "$ROOT_DIR/services/chat-service" --output none
az acr build --registry "$AZURE_ACR_NAME" --image "allora-gateway:${IMAGE_TAG}" "$ROOT_DIR/services/api-gateway" --output none

if ! az_resource_exists cosmosdb show --name "$AZURE_COSMOS_ACCOUNT_NAME" --resource-group "$AZURE_RESOURCE_GROUP"; then
  az cosmosdb create \
    --name "$AZURE_COSMOS_ACCOUNT_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --kind MongoDB \
    --server-version "$COSMOS_MONGO_SERVER_VERSION" \
    --default-consistency-level Session \
    --locations regionName="$AZURE_LOCATION" failoverPriority=0 isZoneRedundant=False \
    --output none
fi

for database_name in "$MONGO_DB_NAME" "$CHAT_MONGO_DB_NAME"; do
  if ! az_resource_exists cosmosdb mongodb database show \
    --account-name "$AZURE_COSMOS_ACCOUNT_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$database_name"; then
    az cosmosdb mongodb database create \
      --account-name "$AZURE_COSMOS_ACCOUNT_NAME" \
      --resource-group "$AZURE_RESOURCE_GROUP" \
      --name "$database_name" \
      --throughput "$COSMOS_DB_THROUGHPUT" \
      --output none
  fi
done

MONGO_URI="$(az cosmosdb keys list \
  --name "$AZURE_COSMOS_ACCOUNT_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --type connection-strings \
  --query "connectionStrings[0].connectionString" \
  -o tsv)"

if ! az_resource_exists redis show --name "$AZURE_REDIS_NAME" --resource-group "$AZURE_RESOURCE_GROUP"; then
  az redis create \
    --name "$AZURE_REDIS_NAME" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --location "$AZURE_LOCATION" \
    --sku Basic \
    --vm-size c0 \
    --enable-non-ssl-port false \
    --output none
fi

REDIS_HOST="$(az redis show --name "$AZURE_REDIS_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query hostName -o tsv)"
REDIS_KEY="$(az redis list-keys --name "$AZURE_REDIS_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query primaryKey -o tsv)"
REDIS_URL="rediss://:$(url_encode "$REDIS_KEY")@${REDIS_HOST}:6380/0"

if ! az_resource_exists containerapp env show --name "$CONTAINERAPPS_ENVIRONMENT" --resource-group "$AZURE_RESOURCE_GROUP"; then
  az containerapp env create \
    --name "$CONTAINERAPPS_ENVIRONMENT" \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --location "$AZURE_LOCATION" \
    --output none
fi

if [[ ! -f "$JWT_PRIVATE_KEY_FILE" || ! -f "$JWT_PUBLIC_KEY_FILE" ]]; then
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$JWT_PRIVATE_KEY_FILE" >/dev/null 2>&1
  openssl rsa -pubout -in "$JWT_PRIVATE_KEY_FILE" -out "$JWT_PUBLIC_KEY_FILE" >/dev/null 2>&1
fi

JWT_PRIVATE_KEY="$(pem_to_env "$JWT_PRIVATE_KEY_FILE")"
JWT_PUBLIC_KEY="$(pem_to_env "$JWT_PUBLIC_KEY_FILE")"

AUTH_IMAGE="${ACR_LOGIN_SERVER}/allora-auth:${IMAGE_TAG}"
CHAT_IMAGE="${ACR_LOGIN_SERVER}/allora-chat:${IMAGE_TAG}"
GATEWAY_IMAGE="${ACR_LOGIN_SERVER}/allora-gateway:${IMAGE_TAG}"

echo "Deploying auth-service..."
az containerapp create \
  --name "$AUTH_APP_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --environment "$CONTAINERAPPS_ENVIRONMENT" \
  --image "$AUTH_IMAGE" \
  --target-port 8000 \
  --ingress internal \
  --min-replicas "$AUTH_MIN_REPLICAS" \
  --max-replicas "$AUTH_MAX_REPLICAS" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --secrets \
    mongo-uri="$MONGO_URI" \
    jwt-secret="$JWT_SECRET" \
    jwt-private-key="$JWT_PRIVATE_KEY" \
    jwt-public-key="$JWT_PUBLIC_KEY" \
  --env-vars \
    MONGO_URI=secretref:mongo-uri \
    MONGO_DB_NAME="$MONGO_DB_NAME" \
    JWT_SECRET=secretref:jwt-secret \
    JWT_ALGORITHM="$JWT_ALGORITHM" \
    JWT_EXPIRE_MINUTES="$JWT_EXPIRE_MINUTES" \
    JWT_ISSUER="$JWT_ISSUER" \
    JWT_KEY_ID="$JWT_KEY_ID" \
    JWT_PRIVATE_KEY=secretref:jwt-private-key \
    JWT_PUBLIC_KEY=secretref:jwt-public-key \
    REFRESH_TOKEN_EXPIRE_DAYS="$REFRESH_TOKEN_EXPIRE_DAYS" \
    VERIFICATION_CODE_EXPIRE_MINUTES="$VERIFICATION_CODE_EXPIRE_MINUTES" \
    DEV_RETURN_CODES="$DEV_RETURN_CODES" \
  --output none

MANAGED_ENVIRONMENT_ID="$(az containerapp env show --name "$CONTAINERAPPS_ENVIRONMENT" --resource-group "$AZURE_RESOURCE_GROUP" --query id -o tsv)"
CHAT_YAML="$GENERATED_DIR/chat-service.containerapp.yml"

cat > "$CHAT_YAML" <<EOF
location: $AZURE_LOCATION
name: $CHAT_APP_NAME
type: Microsoft.App/containerApps
properties:
  managedEnvironmentId: $MANAGED_ENVIRONMENT_ID
  configuration:
    activeRevisionsMode: Single
    ingress:
      external: false
      targetPort: 8000
      transport: auto
    registries:
      - server: $ACR_LOGIN_SERVER
        username: $ACR_USERNAME
        passwordSecretRef: acr-password
    secrets:
      - name: acr-password
        value: "$ACR_PASSWORD"
      - name: mongo-uri
        value: "$MONGO_URI"
      - name: redis-url
        value: "$REDIS_URL"
      - name: rabbitmq-default-user
        value: "guest"
      - name: rabbitmq-default-pass
        value: "guest"
  template:
    containers:
      - name: chat-service
        image: $CHAT_IMAGE
        env:
          - name: MONGO_URI
            secretRef: mongo-uri
          - name: CHAT_MONGO_DB_NAME
            value: "$CHAT_MONGO_DB_NAME"
          - name: REDIS_URL
            secretRef: redis-url
          - name: RABBITMQ_URL
            value: "amqp://guest:guest@localhost:5672/"
          - name: CHAT_EVENTS_EXCHANGE
            value: "$CHAT_EVENTS_EXCHANGE"
        resources:
          cpu: 0.5
          memory: 1Gi
      - name: rabbitmq
        image: rabbitmq:3-management
        env:
          - name: RABBITMQ_DEFAULT_USER
            secretRef: rabbitmq-default-user
          - name: RABBITMQ_DEFAULT_PASS
            secretRef: rabbitmq-default-pass
        resources:
          cpu: 0.5
          memory: 1Gi
    scale:
      minReplicas: $CHAT_MIN_REPLICAS
      maxReplicas: $CHAT_MAX_REPLICAS
EOF

echo "Deploying chat-service with RabbitMQ sidecar..."
az containerapp create \
  --name "$CHAT_APP_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --yaml "$CHAT_YAML" \
  --output none

echo "Deploying api-gateway..."
az containerapp create \
  --name "$GATEWAY_APP_NAME" \
  --resource-group "$AZURE_RESOURCE_GROUP" \
  --environment "$CONTAINERAPPS_ENVIRONMENT" \
  --image "$GATEWAY_IMAGE" \
  --target-port 8000 \
  --ingress external \
  --min-replicas "$GATEWAY_MIN_REPLICAS" \
  --max-replicas "$GATEWAY_MAX_REPLICAS" \
  --registry-server "$ACR_LOGIN_SERVER" \
  --registry-username "$ACR_USERNAME" \
  --registry-password "$ACR_PASSWORD" \
  --secrets redis-url="$REDIS_URL" \
  --env-vars \
    AUTH_SERVICE_URL="http://${AUTH_APP_NAME}" \
    CHAT_SERVICE_URL="http://${CHAT_APP_NAME}" \
    REDIS_URL=secretref:redis-url \
    JWT_ALGORITHM="$JWT_ALGORITHM" \
    JWT_ISSUER="$JWT_ISSUER" \
  --output none

GATEWAY_FQDN="$(az containerapp show --name "$GATEWAY_APP_NAME" --resource-group "$AZURE_RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)"

cat <<EOF

Deploy finished.

Gateway:
  https://$GATEWAY_FQDN

Health checks:
  curl https://$GATEWAY_FQDN/health
  curl https://$GATEWAY_FQDN/services/status

Resource group:
  $AZURE_RESOURCE_GROUP
EOF
