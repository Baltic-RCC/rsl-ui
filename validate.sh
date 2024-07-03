sudo docker exec -it dockerized-QoCDC rm -r workspace/output/report/
sudo docker exec -it dockerized-QoCDC rm -r logs/
sudo docker exec -it dockerized-QoCDC sh validate.sh -vg full
sudo docker exec -it dockerized-QoCDC python3 /home/tmp/xml_reports_to_excel.py
sudo docker exec -it dockerized-QoCDC python3 /home/tmp/logs_to_table.py