from models.enco_deco import encode_text, decode_word
import mysql.connector
from dotenv import load_dotenv
import datetime
import os

load_dotenv()
# MySQL Configuration
MYSQL_HOST = os.getenv('MYSQL_HOST')
MYSQL_USER = os.getenv('MYSQL_USER')
MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD')
MYSQL_DB = os.getenv('MYSQL_DB')

db = mysql.connector.connect(
    host=MYSQL_HOST,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    database=MYSQL_DB
)

def login():
    username_email = "vaibhav_dev_65"
    password = "vaibhav65#"

    cursor = db.cursor()
    cursor.execute("SELECT * FROM users WHERE (username = %s OR email = %s)", 
                    (username_email, username_email))
    user = cursor.fetchone()
    cursor.close()
    print(user[3])
    print(decode_word(user[3]))

    if user and decode_word(user[3]) == password:  # Assuming password is in the 4th column
        print("Login successful!")
        # Here you can set session or cookie logic if needed

if __name__ == '__main__':
    login()