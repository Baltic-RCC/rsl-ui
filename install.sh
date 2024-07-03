sudo docker kill $(sudo docker ps -q)
sudo docker-compose build #--no-cache
docker-compose up -d
docker ps
