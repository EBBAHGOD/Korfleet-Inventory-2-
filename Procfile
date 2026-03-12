web: gunicorn korfleet_inventory.wsgi --log-file - 
#or works good with external database
web: python manage.py migrate && gunicorn korfleet_inventory.wsgi