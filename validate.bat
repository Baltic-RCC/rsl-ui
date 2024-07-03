docker exec -it dockerized-QoCDC rm -r workspace/output/report/
docker exec -it dockerized-QoCDC rm -r logs/
docker exec -it dockerized-QoCDC sh validate.sh -vg full
docker exec -it dockerized-QoCDC python3 /home/tmp/xml_reports_to_excel.py
docker exec -it dockerized-QoCDC python3 /home/tmp/logs_to_table.py
::pause