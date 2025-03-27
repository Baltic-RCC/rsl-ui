docker build -t validator-ui .
docker run -d -p 8050:8050 --name validator validator-ui
docker ps


