# brew install openapi-generator
rm -rf src/common_layer/artifactsmmo/models/
openapi-generator generate -i https://api.beta.artifactsmmo.com/openapi.json -g python-aiohttp -o openapi/ -p noservice --additional-properties=packageName=artifactsmmo
mkdir -p src/common_layer/artifactsmmo/models/
mv openapi/artifactsmmo/models/* src/common_layer/artifactsmmo/models/
rm -rf openapi/
