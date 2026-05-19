#!/bin/bash
# Ejemplos de requests al Match Service
# Usar con: bash examples.sh

BASE_URL="http://localhost:8002"

echo "================================"
echo "Match Service API Examples"
echo "================================"

# 1. Health Check
echo -e "\n1. Health Check"
echo "GET $BASE_URL/health"
curl -X GET "$BASE_URL/health" \
  -H "Content-Type: application/json" | jq .

# 2. Calcular Compatibilidad
echo -e "\n\n2. Calculate Compatibility"
echo "POST $BASE_URL/compatibility"
curl -X POST "$BASE_URL/compatibility" \
  -H "Content-Type: application/json" \
  -d '{
    "user_a_id": "507f1f77bcf86cd799439011",
    "user_b_id": "507f1f77bcf86cd799439012"
  }' | jq .

# 3. Crear Match
echo -e "\n\n3. Create Match"
echo "POST $BASE_URL/matches"
MATCH=$(curl -s -X POST "$BASE_URL/matches" \
  -H "Content-Type: application/json" \
  -d '{
    "user_a_id": "507f1f77bcf86cd799439011",
    "user_b_id": "507f1f77bcf86cd799439012"
  }')
echo $MATCH | jq .
MATCH_ID=$(echo $MATCH | jq -r '.id')

# 4. Obtener Match
if [ ! -z "$MATCH_ID" ] && [ "$MATCH_ID" != "null" ]; then
  echo -e "\n\n4. Get Match Details"
  echo "GET $BASE_URL/matches/$MATCH_ID"
  curl -X GET "$BASE_URL/matches/$MATCH_ID" \
    -H "Content-Type: application/json" | jq .
  
  # 5. Actualizar Status
  echo -e "\n\n5. Update Match Status"
  echo "PUT $BASE_URL/matches/$MATCH_ID"
  curl -X PUT "$BASE_URL/matches/$MATCH_ID" \
    -H "Content-Type: application/json" \
    -d '{
      "status": "ACCEPTED"
    }' | jq .
  
  # 6. Eliminar Match
  echo -e "\n\n6. Delete Match"
  echo "DELETE $BASE_URL/matches/$MATCH_ID"
  curl -X DELETE "$BASE_URL/matches/$MATCH_ID" \
    -H "Content-Type: application/json"
fi

# 7. Obtener Matches Potenciales
echo -e "\n\n7. Get Potential Matches"
echo "GET $BASE_URL/users/507f1f77bcf86cd799439011/matches?limit=5"
curl -X GET "$BASE_URL/users/507f1f77bcf86cd799439011/matches?limit=5" \
  -H "Content-Type: application/json" | jq .

# 8. Obtener Todos los Matches de un Usuario
echo -e "\n\n8. Get All User Matches"
echo "GET $BASE_URL/users/507f1f77bcf86cd799439011/all-matches?status=PENDING"
curl -X GET "$BASE_URL/users/507f1f77bcf86cd799439011/all-matches?status=PENDING" \
  -H "Content-Type: application/json" | jq .

echo -e "\n\n================================"
echo "Examples completed"
echo "================================"
