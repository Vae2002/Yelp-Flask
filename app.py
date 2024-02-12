from flask import *
from pymongo import MongoClient
from datetime import datetime
import uuid
from flask_mail import Mail, Message
from concurrent.futures import ThreadPoolExecutor
import atexit
from apscheduler.schedulers.background import BackgroundScheduler
import pandas as pd
import plotly as plt
import plotly.express as px
import dash
from tabulate import tabulate
from django.shortcuts import render


app = Flask(__name__)

client = MongoClient("mongodb://localhost:27017/")
db = client['yelp']
review_collection = db['review']
user_collection = db['user']
business_collection = db['business']
admin_collection = db['admin']
notification_collection = db['notification_status']

@app.route('/')
def index():
    # year = datetime.year
    # years = [year - i for i in range(10)]
    return render_template('page.html')

def username_exist(username):
    existing_admin = admin_collection.find_one({"admin_username": username})
    return existing_admin is not None


@app.route('/add_admin', methods=['POST'])
def add_admin():
    app.logger.info(request.form)

    business_name = request.form.get('admin_business_name')
    business_address = request.form.get('admin_business_address')
    business_city = request.form.get('admin_business_city')
    admin_name = request.form.get('admin_admin_name')
    admin_username = request.form.get('admin_admin_username')
    admin_email = request.form.get('admin_admin_email')
    admin_password = request.form.get('admin_admin_password')
    admin_password_confirm = request.form.get('admin_admin_password_confirm')
    threshold_percentage = request.form.get('admin_threshold_percentage')
    last_n_reviews = request.form.get('admin_last_n_reviews')

    
    if username_exist(admin_username):
        return render_template('page.html', admin_message="Username already exists for another admin")
    
    business = business_collection.find_one({"name": business_name, "address": business_address, "city": business_city})
    if not business:
        return render_template('page.html', admin_message= "Business not found")
    
    business_id = business['business_id']

    existing_admin_with_business = admin_collection.find_one({"business_id": business_id})

    if existing_admin_with_business:
        return render_template('page.html', admin_message= "Business already exists for another admin")

    if admin_password != admin_password_confirm:
        return render_template('page.html', admin_message="Passwords do not match")
    
    admin_id = str(uuid.uuid4())

    admin_doc = {
        "_id": admin_id,
        "admin_id": str(uuid.uuid4()),
        "admin_name": admin_name,
        "business_id": business_id,
        "admin_username": admin_username,
        "admin_email": admin_email,
        "admin_password": admin_password,
        "threshold_percentage": int(threshold_percentage),
        "last_n_reviews": int(last_n_reviews)
    }

    admin_collection.insert_one(admin_doc)

    return render_template('page.html', admin_message='Admin data received successfully')

@app.route('/add_review', methods=['POST'])
def add_review():
    if request.method == 'POST':
        user_name = request.form['user_name']
        business_name = request.form['business_name']
        business_address = request.form['business_address']
        business_city = request.form['business_city']
        stars = request.form['stars']
        useful = request.form['useful']
        funny = request.form['funny']
        cool = request.form['cool']
        text = request.form['text']
        

        _id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        review_id = str(uuid.uuid4())


        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        business = business_collection.find_one({"name": business_name, "address": business_address, "city": business_city})

        if not business:
            return "Business not found"
        business_id = business['business_id']

        admin_username = admin_collection.find_one({"business_id": business_id})["admin_username"]

        admin_id = admin_collection.find_one({"business_id": business_id})["admin_id"]
        
        app.logger.info(admin_username)

        user = user_collection.find_one({"name": user_name})

        if not user:
            return "User not found"
        user_id = user['user_id']

        stars = int(stars)
        useful = int(useful)
        funny = int(funny)
        cool = int(cool)

        review_doc = {
            "_id": _id,
            "review_id": review_id,
            "user_id": user_id,
            "business_id": business_id,
            "stars": stars,
            "useful": useful,
            "funny": funny,
            "cool": cool,
            "text": text,
            "date": current_date
        }

        review_collection.insert_one(review_doc)
        

        add_review_array(admin_id, business_id)
        
        return render_template('page.html', review_message='Review data received successfully')
    
    #######################

# old review array : ... ... ... ... ... - first, fill in this array, until full, and continue to the new array
# new review array : ... ... ... ... ... - if full, overwrite old array, new array becomes empty

        
# bikin document isi nya array review_id nya last_n_reviews, masukkin ke notification_collection
def add_review_array(admin_id, business_id):
    
    app.logger.info("inside add review array")
    app.logger.info(admin_id)

    last_n_reviews = admin_collection.find_one({"business_id": business_id})['last_n_reviews']
    app.logger.info(last_n_reviews)
    # last_n_reviews = last_n_reviews["last_n_reviews"]
    # last_review = review_collection.find({"business_id": business_id}).sort([("date", -1)]).limit(1)
    last_review = review_collection.find({"business_id": business_id}).sort([("date", -1)]).limit(1)[0]
    # app.logger.info(last_review)

    if not notification_collection.find({"old_review_array": {"$size": last_n_reviews}}):
        notification_collection.update_one({'admin_id': admin_id}, {'$push': {'old_review_array': last_review}})

        
    else:
        if not notification_collection.find({"new_review_array": {"$size": last_n_reviews}}):
            notification_collection.update_one({'admin_id': admin_id}, {'$push': {'new_review_array': last_review}})
        else:
            new_review_array = notification_collection.find_one({"admin_id": admin_id})['new_review_array']

            notification_collection.update_one({'admin_id': admin_id}, {"$set": {"old_review_array": []}})
            notification_collection.update_one({"admin_id": admin_id}, {"$set": {"old_review_array": new_review_array}})
            

            # notification_collection.update_one({
            #     "admin_id": admin_id
            # }, {
            #     "$set": {
            #         "new_review_array":[
            #             last_review
            #     ]
            #     }
            # })

            notification_collection.update_one({'admin_id': admin_id}, {"$set": {"new_review_array": []}})
            notification_collection.update_one({'admin_id': admin_id}, {'$push': {'new_review_array': last_review}})

            notification_collection.update_one({'admin_id': admin_id}, {"$set": {"executed": "0"}})


    ####################################


@app.route('/check_admin', methods=['POST'])
def check_admin():
    username = str(request.form['input_username'])
    password = request.form['input_password']
    find_admin = admin_collection.find_one({"admin_username": str(username), "admin_password": str(password)})
    app.logger.info('--- Debug Input ---')
    app.logger.info('username: ', username)
    # app.logger.info('password: ', password)
    
    if not find_admin:
        error_message = "Incorrect Username or Password. Please enter the correct username and password."
        return error_message
    else:
        return username + password + " found"
    

app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USERNAME'] = 'eunicelimuria@gmail.com'  
app.config['MAIL_PASSWORD'] = 'qtyo xhpj mpuk znjt'  
app.config['MAIL_USE_TLS'] = False
app.config['MAIL_USE_SSL'] = True
mail = Mail(app)

@app.route('/send_mail', methods=['POST'])
def send_mail():
    email = request.form['recipient']
    message = Message(subject="Hello", recipients=[email], sender=app.config['MAIL_USERNAME'], body="This is a test email I sent with Gmail and Python!")
    mail.send(message= message)
    return render_template('page.html', result_message='Email sent!')
##########################################################################################
# scheduler = BackgroundScheduler()


# def job():
#     print("Scheduled job executed")

# scheduler.add_job(job, 'interval', seconds=1)

# # @app.before_first_request
# # def start_scheduler():
# #     scheduler.start()

# # @app.teardown_appcontext
# # def stop_scheduler(exception=None):
# #     scheduler.shutdown()
# scheduler.start()


##########################################################################################


# def send_email(admin_username, email_body):
#     receiver_email = admin_collection.find_one({"admin_username": admin_username})['admin_email']
#     msg = Message(subject="Negative Reviews Notification", recipients=[receiver_email], sender=app.config['MAIL_USERNAME'], body=email_body)
#     app.logger.info('--- Send email executed ---')
#     with app.app_context():
#         mail.send(message=msg)
#         app.logger.info('--- Email sent! ---')

# def notify_low_rating_reviews(admin_username):
#     previous_review_ids = set() 
#     app.logger.info('--- Notify low rating reviews executed ---')
#     business_id = admin_collection.find_one({"admin_username": admin_username})['business_id']
#     business_name = business_collection.find_one({"business_id": business_id})['name']
#     last_n_reviews = admin_collection.find_one({"admin_username": admin_username})['last_n_reviews']
#     threshold_percentage = admin_collection.find_one({"admin_username": admin_username})['threshold_percentage']
    
#     current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

#     # Find the last 'n' reviews for the given business_id based on the "date" field
#     recent_reviews = list(review_collection.find(
#         {"business_id": business_id}
#     ).sort([("date", -1)]).limit(last_n_reviews))

#     print("Recent reviews:")
#     for review in recent_reviews:
#         print(f"Review: {review['_id']} - Stars: {review['stars']} - Date: {review['date']}")
    
#     app.logger.info('--- Recent reviews executed ---')

#     # Get the set of current review IDs
#     current_review_ids = {review['_id'] for review in recent_reviews}

#     # Check if there are new reviews by comparing review IDs
#     new_reviews = current_review_ids - previous_review_ids

#     # Update previous_review_ids with the current review IDs
#     previous_review_ids.update(current_review_ids)

#     if new_reviews:
#         low_rating_count = sum(1 for review in recent_reviews if review['stars'] in [1, 2])
#         total_reviews = len(recent_reviews)
#         percentage = (low_rating_count / total_reviews) * 100 if total_reviews > 0 else 0
#         print(f"Percentage of low rating reviews: {percentage:.2f}%")

#         # Notify if the threshold percentage is exceeded
#         if percentage >= threshold_percentage:
#             app.logger.info("Threshold exceeded! Sending email notification...")

#             # Send email notification
#             email_body = f"Dear {business_name} Admin,\n\nYour business has received {percentage:.2f}% negative reviews of the last {last_n_reviews} reviews.\n\nChecked on {current_date}\n\nSincerely,\nYelp Review System."
#             send_email(admin_username, email_body)
#             app.logger.info("Email notification sent!")

#             print(f"Checked on {current_date}. Threshold exceeded: {percentage:.2f}% of the last {last_n_reviews} reviews for '{business_name}' have low ratings.")
#             return render_template('page.html', notification_message='Email notification sent!')
#         else:
#             app.logger.info("Threshold not exceeded. No email notification sent.")
#             return render_template('page.html', notification_message='No email notification sent.')
#     else:
#         app.logger.info("No new reviews found. No email notification sent.")
#         return 'No new reviews found. No email notification sent.'

# executor = ThreadPoolExecutor(max_workers=5)  # Adjust the number of workers as needed

# def perform_review_check(username):
#     app.logger.info('--- Perform review executed ---')
#     result = notify_low_rating_reviews(username)
#     if result:
#         print(result)

# def initiate_review_check(username):
#     app.logger.info('--- Initiate review executed ---')
#     return executor.submit(perform_review_check, username)

# @atexit.register
# def shutdown():
#     executor.shutdown(wait=False)

# # @scheduler.task('interval', id='check_reviews', seconds=10)
# @app.route('/check_reviews', methods=['POST'])
# def check_reviews():
#     print("Checking for new low-rated reviews...")
#     if "Start" in request.form:
#         with app.app_context():
#             try:
#                 admin_username = str(request.form['admin_username'])
#                 admin_password = str(request.form['admin_password'])
#                 find_admin = admin_collection.find_one({"admin_username": str(admin_username)}, {"admin_password": str(admin_password)})
#                 app.logger.info('--- username : ---', admin_username, '--- password : ---', admin_password)
                
#                 if not find_admin:
#                     app.logger.info("find admin not executed")
#                     error_message = "Incorrect Username or Password. Please enter the correct username and password."
#                     return render_template('page.html', error_message=error_message)
                
#                 else:
#                     initiate_review_check(admin_username)
#                     app.logger.info("find admin executed")
#                     return render_template('page.html', notification_message='Review checking started!')
                    
#             except ValueError as err:
#                 error_message = str(err)  
#                 return render_template('page.html', error_message=error_message)
            
#     elif "Stop" in request.form:
#         return render_template('page.html', notification_message='Review checking stopped!')
        
# # scheduler.add_job(func=check_reviews, trigger='interval', seconds=10)
# # scheduler.start()
        
##########################################################################################
def get_admin_id(admin_username):
    admin_id = admin_collection.find_one({"admin_username": admin_username})['admin_id']
    return admin_id

def admin_id_exist(admin_username):
    admin_id = get_admin_id(admin_username)
    existing_admin = notification_collection.find_one({"admin_id": admin_id})
    return existing_admin is not None

@app.route('/start_stop_notification', methods=['POST'])
def start_stop_notification():
    admin_username = str(request.form['admin_username'])
    admin_password = str(request.form['admin_password'])
    find_admin = admin_collection.find_one({"admin_username": admin_username, "admin_password": admin_password})
    
    if not find_admin:
        app.logger.info("admin not found")
        error_message = "Please enter the correct username and password."
        return render_template('page.html', error_message=error_message)
    else:
        if 'Start' in request.form: 
            app.logger.info('--- Debug Input Start ---')
            status = '1'
            input_admin(admin_username, admin_password, status)
            return render_template('page.html', notification_message='Review checking started!')
        elif 'Stop' in request.form:
            app.logger.info('--- Debug Input Stop ---')
            status = '0'
            input_admin(admin_username, admin_password, status)
            return render_template('page.html', notification_message='Review checking stopped!')
        

# @app.route('/input_admin', methods=['POST'])
def input_admin(admin_username, admin_password, status):
    admin_id = get_admin_id(admin_username)
    app.logger.info('--- username : ---', admin_username, '--- password : ---', admin_password)

    try:
        app.logger.info('--- Debug Input inside input admin ---')
        
             
        if not admin_id_exist(admin_username):
            app.logger.info('--- admin_id_exist : ', admin_id_exist(admin_username))
            notif_doc = {
                "_id": str(uuid.uuid4()),
                "admin_id": admin_id,
                "status": status,
                "old_review_array": [],
                "new_review_array": [],
                "executed": 0
            }
            notification_collection.insert_one(notif_doc)
            app.logger.info("admin not exist executed, admin added to notification collection")

            # return automatic_check_reviews()
        else:
            app.logger.info('--- admin_id_exist : ---', admin_id_exist(admin_username))
            notification_collection.update_one({"admin_id": admin_collection.find_one({"admin_username": admin_username})['admin_id']}, {"$set": {"status": status}})
            app.logger.info("admin exist executed, admin updated in notification collection")

            # return automatic_check_reviews()

    
    except ValueError as err:
        error_message = str(err)  
        return error_message
    


def automatic_check_reviews():
    app.logger.info('--- Automatic check reviews executed ---')
    for x in notification_collection.find({"status": '1'}):
        check_review_array(admin_collection.find_one({"admin_id": x['admin_id']}))


    # for i in notification_collection.find():
    #     app.logger.info('--- Notification collection loop executed ---')
    #     app.logger.info(i)
    #     app.logger.info(i['status'])
    #     if i['status'] == '1':
    #         print("Checking for new low-rated reviews...")
    #         with app.app_context():
    #             app.logger.info(i['admin_id'] + " is the admin in the loop")
    #             # initiate_review_check(i['admin_id']) --- finish later
    #             return i['admin_id'] + " is the admin in the loop"
                
    #     elif i['status'] == '0':
    #         return "Notification is off, not checking for new low-rated reviews."

scheduler = BackgroundScheduler()        

scheduler.add_job(
    automatic_check_reviews, 
    'interval', 
    minutes=1)
scheduler.start()
atexit.register(lambda: scheduler.shutdown())
    
def check_review_array(admin_id):
    app.logger.info("check_review_array started")
    # app.logger.info(notification_collection.find_one({"admin_id": admin_id}))

    admin_id = admin_id["admin_id"]
    # app.logger.info(admin_id)

    new_review_array = notification_collection.find_one({"admin_id": admin_id})["new_review_array"]
    old_review_array = notification_collection.find_one({"admin_id": admin_id})["old_review_array"]
    last_n_reviews = admin_collection.find_one({"admin_id": admin_id})['last_n_reviews']
    business_id = admin_collection.find_one({"admin_id": admin_id})['business_id']
    admin_username = admin_collection.find_one({"admin_id": admin_id})['admin_username']

    recent_reviews = list(review_collection.find(
        {"business_id": business_id}
    ).sort([("date", -1)]).limit(last_n_reviews))

    # app.logger.info(old_review_array)
    app.logger.info(admin_username)
    app.logger.info(new_review_array)
    

    if old_review_array == []:
        if new_review_array != []:
            # old_review_array jadi new array
            notification_collection.update_one({
                "admin_id": admin_id
            }, {
                "$set": {
                    "old_review_array":[
                        new_review_array
                ]
                }
            })

            notification_collection.update_one({
                "admin_id": admin_id
            }, {
                "$set": {
                    "new_review_array":[
                        []
                ]
                }
            })

            notification_collection.update_one({
                "admin_id": admin_id}, {"$set": {"executed": "0"}})
            
        else:
            # old_review_array jadi recent_reviews
            notification_collection.update_one({
                "admin_id": admin_id
            }, {
                "$set": {
                    "old_review_array":[
                        recent_reviews
                ]
                }
            })

    else:
        executed = notification_collection.find_one({"admin_id": admin_id})['executed']
        app.logger.info(executed)
        new_array_size = notification_collection.find({"new_review_array": {"$size": 1}})
        if new_array_size and executed == "0":
            notification_collection.update_one({"admin_id": admin_id}, {"$set": {"executed": "1"}})
            return notify_low_rating_reviews(admin_username, recent_reviews)
        else:
            return app.logger.info('No new reviews. Skip notification.')

executor = ThreadPoolExecutor(max_workers=5)  # Adjust the number of workers as needed

def initiate_review_check(username):
    app.logger.info('--- Initiate review executed ---')
    return executor.submit(perform_review_check, username)

def perform_review_check(username):
    app.logger.info('--- Perform review executed ---')
    result = notify_low_rating_reviews(username)
    if result:
        print(result)

def notify_low_rating_reviews(admin_username, recent_reviews):
    app.logger.info('--- Notify low rating reviews executed ---')
    business_id = admin_collection.find_one({"admin_username": admin_username})['business_id']
    business_name = business_collection.find_one({"business_id": business_id})['name']
    last_n_reviews = admin_collection.find_one({"admin_username": admin_username})['last_n_reviews']
    threshold_percentage = admin_collection.find_one({"admin_username": admin_username})['threshold_percentage']
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    low_rating_count = sum(1 for review in recent_reviews if review['stars'] in [1, 2])
    total_reviews = len(recent_reviews)
    percentage = (low_rating_count / total_reviews) * 100 if total_reviews > 0 else 0
    app.logger.info(percentage)

    if percentage >= threshold_percentage:
        app.logger.info("Threshold exceeded! Sending email notification...")

        email_body = f"Dear {business_name} Admin,\n\nYour business has received {percentage:.2f}% negative reviews of the last {last_n_reviews} reviews.\n\nChecked on {current_date}\n\nSincerely,\nYelp Review System."
        send_email(admin_username, email_body)

        print(f"Checked on {current_date}. Threshold exceeded: {percentage:.2f}% of the last {last_n_reviews} reviews for '{business_name}' have low ratings.")
        return 'Email notification sent!'
    else:
        app.logger.info(business_name, "threshold not exceeded")
        return 'No email notification sent.'

######################

def send_email(admin_username, email_body):
    receiver_email = admin_collection.find_one({"admin_username": admin_username})['admin_email']
    msg = Message(subject="Negative Reviews Notification", recipients=[receiver_email], sender=app.config['MAIL_USERNAME'], body=email_body)
    app.logger.info('--- Send email executed ---')
    with app.app_context():
        mail.send(message=msg)
        app.logger.info('--- Email sent! ---')



##########################
@app.route('/show_reports', methods=['POST'])        
def show_reports():
    admin_username = str(request.form['report_admin_username'])
    admin_password = str(request.form['report_admin_password'])
    selected_month = request.form.get('month', None)
    selected_year = int(request.form.get('year', None))

    find_admin = admin_collection.find_one({"admin_username": admin_username, "admin_password": admin_password})
    business_id = admin_collection.find_one({"admin_username": admin_username})["business_id"]
    app.logger.info(business_id)

    if not find_admin:
        app.logger.info("admin not found")
        error_message = "Please enter the correct username and password."
        return render_template('page.html', error_message=error_message)
    else:
        months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
        # year = datetime.date.today().year
        # years = [year - i for i in range(10)]
        month_index = months.index(selected_month) + 1

        if month_index < 10:
            start_date = str(str(selected_year) + "-0" + str(month_index) + "-01")
            if month_index != 9:
                end_date = str(str(selected_year) + "-0" + str(month_index + 1) + "-01")
            else:
                end_date = str(str(selected_year) + "-10-01")
        else:
            start_date = str(str(selected_year) + "-" + str(month_index) + "-01")
            if month_index != 12:
                end_date = str(str(selected_year) + "-" + str(month_index+1) + "-01")
            else:
                end_date = str(str(selected_year+1) + "-01-01")

        
        recent_reviews = list(review_collection.find(
            {"business_id": business_id, "date": {"$gte": start_date, "$lt": end_date}}
        ).sort([("date", -1)]))

        if recent_reviews == []:
            notification_message = "No reviews in selected month."
            return render_template('page.html', notification_message=notification_message)
        else:      
            return render_template('table.html', reports=recent_reviews)
            # return render_template('page.html', years = years)


# @app.route('/monthly_report', methods=['POST'])        
# def monthly_report(business_id): 
#         selected_month = request.form.get('month', None)
#         selected_year = int(request.form.get('year', None))
#         months = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

#         month_index = months.index(selected_month) + 1

#         if month_index < 10:
#             start_date = str(str(selected_year) + "-0" + str(month_index) + "-01")
#             if month_index != 9:
#                 end_date = str(str(selected_year) + "-0" + str(month_index + 1) + "-01")
#             else:
#                 end_date = str(str(selected_year) + "-10-01")
#         else:
#             start_date = str(str(selected_year) + "-" + str(month_index) + "-01")
#             if month_index != 12:
#                 end_date = str(str(selected_year) + "-" + str(month_index+1) + "-01")
#             else:
#                 end_date = str(str(selected_year+1) + "-01-01")

        
#         recent_reviews = list(review_collection.find(
#             {"business_id": business_id, "date": {"$gte": start_date, "$lt": end_date}}
#         ).sort([("date", -1)]))

#         return render_template('table.html', reports=recent_reviews)

if __name__ == '__main__':
    app.run(use_reloader=False, debug=True)


