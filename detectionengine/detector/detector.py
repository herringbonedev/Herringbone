from database import MongoDatabaseHandler
import time

while True:

    try:
        mongo = MongoDatabaseHandler()
        rules = mongo.get_rules()
        print(rules)

    except Exception as e:
        print(e)
    
    time.sleep(5)