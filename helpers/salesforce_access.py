from simple_salesforce import Salesforce, SalesforceResourceNotFound, SalesforceMalformedRequest
from dotenv import load_dotenv
import os
from flask import jsonify
import requests
import json
import logging
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Log to standard output
    ]
)

load_dotenv()
username = os.getenv('SF_USERNAME')
password = os.getenv('SF_PASSWORD')
security_token = os.getenv('SF_SECURITY_TOKEN')
access_key = os.getenv('ACCESS_KEY')

sf = Salesforce(username=username, password=password, security_token=security_token, domain='test')
BASEURL = f"https://{os.getenv('SHOP_URL')}/admin/api/{os.getenv('API_VERSION')}"

def find_payment_method_of_user(user_id):
    query = f"SELECT Id, Provider_Name__c, Method_Name__c, Customer_Phone_Number__c, Customer_Name__c, Default_Payment_Method__c FROM Payment__c WHERE Account__c = '{user_id}'"
    response = sf.query(query)

    if response['totalSize'] > 0:
        user_details_list = []
        for account_details in response['records']:
            user_details = {
                "paymentMethodId": account_details.get('Id'),
                "providerName": account_details.get('Provider_Name__c'),
                "methodName": account_details.get('Method_Name__c'),
                "customerPhone": account_details.get('Customer_Phone_Number__c'),
                "customerName": account_details.get('Customer_Name__c'),
                "defaultPaymentMethod": account_details.get('Default_Payment_Method__c')
            }
            user_details_list.append(user_details)
        return user_details_list
    else:
        return []
    
def find_user(user_id):
    query = f"SELECT Name, Display_Photo_URL__c, Account_ID__c, Geolocation__c, ShippingAddress, Phone, CurrencyIsoCode, Alternate_Phone__c, Total_Order_Amount__c, Orders_Placed__c, Country__c, (SELECT Id, AccountId, Name, OtherPhone, Member_ID__c, Age__c, HOH_Relationship__c FROM Contacts), (SELECT Name, Customer__c, Subscription_Start_Date__c, Subscription_End_Date__c, Delivery_Frequency__c FROM Subscriptions__r) FROM Account WHERE ID = '{user_id}'"
    response = sf.query(query)

    if response['totalSize'] > 0:
        account_details = response['records'][0]
        
        user_details = {
            "name": account_details.get('Name'),
            "accountIdCH": account_details.get('Account_ID__c'),
            "phoneNumber": account_details.get('Phone'),
            "altPhoneNumber": account_details.get('Alternate_Phone__c'),
            "cumulativeOrders": account_details.get('Orders_Placed__c'),
            "cumulativeAmount": account_details.get('Total_Order_Amount__c'),
            "currency": account_details.get('CurrencyIsoCode'),
            "country": account_details.get('Country__c'),
            "displayPhoto": account_details.get('Display_Photo_URL__c'),
            "shippingAddress": account_details.get('ShippingAddress'),
            "geolocation": account_details.get('Geolocation__c'),
            "contacts": [],
            "subscriptions":[]
        }
        contacts_data = account_details.get('Contacts', {})
        if contacts_data:
            contacts_data = contacts_data.get('records', [])
            for contact in contacts_data:
                contact_details = {
                    "contactId": contact.get('Id'),
                    "accountId": contact.get('AccountId'),
                    "contactName": contact.get('Name'),
                    "otherPhone": contact.get('OtherPhone'),
                    "memberID": contact.get('Member_ID__c'),
                    "age": contact.get('Age__c'),
                    "relationship":contact.get('HOH_Relationship__c')
                }
                user_details["contacts"].append(contact_details)

        subscriptions_data = account_details.get('Subscriptions__r', {})
        if subscriptions_data:
            subscriptions_data = subscriptions_data.get('records', [])
            for subscription in subscriptions_data:
                subscription_details = {
                    "name": subscription.get('Name'),
                    "customerName": subscription.get('Customer__c'),
                    "startDate": subscription.get('Subscription_Start_Date__c'),
                    "endDate": subscription.get('Subscription_End_Date__c'),
                    "deliveryFrequency":subscription.get('Delivery_Frequency__c')
                }
                user_details["subscriptions"].append(subscription_details)

        return user_details
    else:
        return None

def find_user_order(user_id, stage):
    # Modify the query to conditionally include the StageName filter
    if stage.lower() == "all":
        query = f"SELECT ID, Amount, Delivery_SLA_Date__c, CurrencyIsoCode, Payment_Status__c, Net_Promoter_Score__c, CloseDate, Created_Date__c, Shopify_Order_Number__c, Name, StageName, Payment_Method__r.Customer_Phone_Number__c, Payment_Method__r.CurrencyIsoCode, Payment_Method__r.Customer_Name__c, Payment_Method__r.Method_Name__c, Payment_Method__r.Provider_Name__c, Payment_Method__r.Name, Prescription__r.Name, Prescription__r.Id, Opportunity_Number__c, Patient_Name__r.Name, Subscription__c FROM Opportunity WHERE AccountId = '{user_id}'"
    elif stage.lower() == "pending":
        query = f"SELECT ID, Amount, Delivery_SLA_Date__c, CurrencyIsoCode, Payment_Status__c, Net_Promoter_Score__c, CloseDate, Created_Date__c, Shopify_Order_Number__c, Name, StageName, Payment_Method__r.Customer_Phone_Number__c, Payment_Method__r.CurrencyIsoCode, Payment_Method__r.Customer_Name__c, Payment_Method__r.Method_Name__c, Payment_Method__r.Provider_Name__c, Payment_Method__r.Name, Prescription__r.Name, Prescription__r.Id, Opportunity_Number__c, Patient_Name__r.Name, Subscription__c FROM Opportunity WHERE AccountId = '{user_id}' AND StageName IN ('Qualification', 'Quoted', 'Ordered', 'Picked Up')"
    elif stage.lower() == "past":
        query = f"SELECT ID, Amount, Delivery_SLA_Date__c, CurrencyIsoCode, Payment_Status__c, Net_Promoter_Score__c, CloseDate, Created_Date__c, Shopify_Order_Number__c, Name, StageName, Payment_Method__r.Customer_Phone_Number__c, Payment_Method__r.CurrencyIsoCode, Payment_Method__r.Customer_Name__c, Payment_Method__r.Method_Name__c, Payment_Method__r.Provider_Name__c, Payment_Method__r.Name, Prescription__r.Name, Prescription__r.Id, Opportunity_Number__c, Patient_Name__r.Name, Subscription__c FROM Opportunity WHERE AccountId = '{user_id}' AND StageName IN ('Delivered', 'Delivered-Paid', 'Closed Won')"
    else:
        raise ValueError("Invalid stage provided. Please use 'pending' or 'past'.")

    response = sf.query(query)

    if response['totalSize'] > 0:
        order_summaries = []
        opportunity_ids = [opportunity_details.get('Id') for opportunity_details in response['records']]

        # Query delivery details separately
        if stage.lower() == "past":
            ids_string = ', '.join(f"'{oid}'" for oid in opportunity_ids)
            delivery_query = f"""
            SELECT Opportunity__c, Delivery_Date__c, Delivery_Time__c, Delivery_Timestamp__c
            FROM Delivery__c
            WHERE Opportunity__c IN ({ids_string})
            """
            delivery_response = sf.query(delivery_query)
            delivery_details_map = {delivery.get('Opportunity__c'): delivery for delivery in delivery_response['records']}
        else:
            delivery_details_map = {}

        for opportunity_details in response['records']:
            opportunity_id = opportunity_details.get('Id')
            opportunity_number = opportunity_details.get('Opportunity_Number__c')
            opportunity_patient_name = opportunity_details.get('Patient_Name__r')
            payment_method = opportunity_details.get('Payment_Method__r', {})
            prescription = opportunity_details.get('Prescription__r', {})
            opportunity_amount = opportunity_details.get('Amount')
            opportunity_shopify_order_no = opportunity_details.get('Shopify_Order_Number__c')
            opportunity_close_date = opportunity_details.get('CloseDate')
            opportunity_name = opportunity_details.get('Name')
            opportunity_stage = opportunity_details.get('StageName')
            opportunity_created_date = opportunity_details.get('Created_Date__c')
            opportunity_delivery_date = opportunity_details.get('Delivery_SLA_Date__c')
            opportunity_payment_status = opportunity_details.get('Payment_Status__c')
            opportunity_currency = opportunity_details.get('CurrencyIsoCode')
            if stage == 'pending':
                opportunity_rating = None
            else:
                opportunity_rating = opportunity_details.get('Net_Promoter_Score__c')

            # Fetch delivery details if stage is past
            delivery_details = delivery_details_map.get(opportunity_id, {})
            delivery_date = delivery_details.get('Delivery_Date__c')
            delivery_time = delivery_details.get('Delivery_Time__c')
            delivery_timestamp = delivery_details.get('Delivery_Timestamp__c')

            subscription_id = opportunity_details.get('Subscription__c')
            subscription_details = []
            if subscription_id:
                subscription_query = f"SELECT Name, Customer__r.Name, Account__r.Name FROM Subscription__c WHERE Subscription__c.Id = '{subscription_id}'"
                subscriptions_data = sf.query(subscription_query)
                if subscriptions_data['totalSize'] > 0:
                    for subscription in subscriptions_data['records']:
                        customer_name = subscription.get('Customer__r')
                        if customer_name:
                            customer_name = customer_name.get('Name')
                        else:
                            customer_name = None
                        subscription_detail = {
                            "name": subscription.get('Name'),
                            "customerName": customer_name,
                            "accountHolder": subscription.get('Account__r').get('Name')
                        }
                        subscription_details.append(subscription_detail)

            opp_item_query = f"SELECT Product__c, Price__c, Total_Line_Item_Price__c, Quantity__c, Shopify_Order_Number__c, Date__c FROM Opportunity_Item__c WHERE Opportunity__c = '{opportunity_id}'"
            opp_item_response = sf.query(opp_item_query)
            prescription_details = {}
            payment_method_details = {}

            opportunity_items = []
            if opp_item_response['totalSize'] > 0:
                for item in opp_item_response['records']:
                    opp_item = {
                        "products": item.get('Product__c'),
                        "price": item.get('Price__c'),
                        "quantity": item.get('Quantity__c'),
                        "shopifyOrderNumber": item.get('Shopify_Order_Number__c'),
                        "totalPrice": item.get('Total_Line_Item_Price__c'),
                        "date": item.get('Date__c')
                    }
                    opportunity_items.append(opp_item)

            if opportunity_patient_name:
                opportunity_patient_name = opportunity_patient_name.get('Name')

            if payment_method:
                payment_method_details = {
                    "customerPhoneNumber": payment_method.get('Customer_Phone_Number__c'),
                    "currencyIsoCode": payment_method.get('CurrencyIsoCode'),
                    "customerName": payment_method.get('Customer_Name__c'),
                    "methodName": payment_method.get('Method_Name__c'),
                    "providerName": payment_method.get('Provider_Name__c'),
                    "name": payment_method.get('Name')
                }
            if prescription:
                prescription_details = {
                    "name": prescription.get('Name', 'N/A'),
                    "prescriptionId": prescription.get('Id', 'N/A')
                }
            order_summary = {
                "opportunityId": opportunity_id,
                "opportunityName": opportunity_name,
                "opportunityNumber": opportunity_number,
                "patientName": opportunity_patient_name,
                "prescription": prescription_details,
                "paymentMethod": payment_method_details,
                "shopifyOrderNumber": opportunity_shopify_order_no,
                "deliveryDate": opportunity_delivery_date,
                "deliveryRating": opportunity_rating,
                "amount": opportunity_amount,
                "closeDate": opportunity_close_date,
                "createdDate": opportunity_created_date,
                "currentStage": opportunity_stage,
                "paymentStatus": opportunity_payment_status,
                "currency": opportunity_currency,
                "opportunityItems": opportunity_items,  # List of all items
                "subscription": subscription_details,
                "deliveryDetails": {
                    "deliveryDate": delivery_date,
                    "deliveryTime": delivery_time,
                    "deliveryTimestamp": delivery_timestamp
                } if stage.lower() == "past" else None  # Added delivery details conditionally
            }
            order_summaries.append(order_summary)

        return order_summaries
    else:
        return {"msg": "No Opportunities found associated with the user"}

    
def find_user_prescription(patient_id, prescription_id):
    # Modify the query to conditionally include the StageName filter
    if prescription_id is None:
        query = f"SELECT ID, Account__c, Instructions__c, Patient__c, Age__c, Prescribing_Practitioner__c, Prescribing_Clinic__c, Prescription_Created_Date__c, Name FROM Prescription__c WHERE Patient__c = '{patient_id}'"
    else:
        query = f"SELECT ID, Account__c, Instructions__c, Patient__c, Age__c, Prescribing_Practitioner__c, Prescribing_Clinic__c, Prescription_Created_Date__c, Name FROM Prescription__c WHERE Patient__c = '{patient_id}' AND ID = '{prescription_id}'"

    response = sf.query(query)

    if response['totalSize'] > 0:
        prescription_summaries = []
        for prescription_details in response['records']:
            prescription_id = prescription_details.get('Id')
            prescription_account_holder = prescription_details.get('Account__c')
            prescription_patient_id = prescription_details.get('Patient__c')
            prescription_age = prescription_details.get('Age__c')
            prescription_prescribing_practitioner_id = prescription_details.get('Prescribing_Practitioner__c')
            prescription_prescribing_clinic_id = prescription_details.get('Prescribing_Clinic__c')
            prescription_creation_date = prescription_details.get('Prescription_Created_Date__c')
            prescription_name = prescription_details.get('Name')
            prescription_instructions = prescription_details.get('Instructions__c')

            if prescription_patient_id:
                patient_query = f"SELECT Name FROM Contact WHERE ID = '{prescription_patient_id}'"
                patient_response = sf.query(patient_query)
                if patient_response['totalSize'] > 0:
                    prescription_patient_name = patient_response['records'][0].get('Name')
                else:
                    prescription_patient_name = None
            else:
                prescription_patient_name = None

            # Query for practitioner name
            if prescription_prescribing_practitioner_id:
                practitioner_query = f"SELECT Name FROM Contact WHERE ID = '{prescription_prescribing_practitioner_id}'"
                practitioner_response = sf.query(practitioner_query)
                if practitioner_response['totalSize'] > 0:
                    prescription_prescribing_practitioner = practitioner_response['records'][0].get('Name')
                else:
                    prescription_prescribing_practitioner = None
            else:
                prescription_prescribing_practitioner = None

            # Query for clinic name
            if prescription_prescribing_clinic_id:
                clinic_query = f"SELECT Name FROM Account WHERE ID = '{prescription_prescribing_clinic_id}'"
                clinic_response = sf.query(clinic_query)
                if (clinic_response['totalSize'] > 0):
                    prescription_prescribing_clinic = clinic_response['records'][0].get('Name')
                else:
                    prescription_prescribing_clinic = None
            else:
                prescription_prescribing_clinic = None

            # Query for prescription line items
            line_items_query = f"SELECT ID, Inventory_Name__c, Generic_Name__c, Notes__c, Status__c, Tablet__c, Prescription__c, Frequency__c, Units_per_Day__c FROM Prescription_Line_Item__c WHERE Prescription__c = '{prescription_id}'"
            line_items_response = sf.query(line_items_query)

            line_items = []
            if line_items_response['totalSize'] > 0:
                for item in line_items_response['records']:
                    opp_item = {
                        "inventoryName": item.get('Inventory_Name__c'),
                        "genericName": item.get('Generic_Name__c'),
                        "tablet": item.get('Tablet__c'),
                        "notes": item.get('Notes__c'),
                        "status": item.get('Status__c'),
                        "frequency": item.get('Frequency__c'),
                        "unitsPerDayInsulin": item.get('Units_per_Day__c')
                    }
                    line_items.append(opp_item)

            prescription_summary = {
                "prescriptionId": prescription_id,
                "accountHolder": prescription_account_holder,
                "patientName": prescription_patient_name,
                "age": prescription_age,
                "prescribingPractitioner": prescription_prescribing_practitioner,
                "prescribingClinic": prescription_prescribing_clinic,
                "creationDate": prescription_creation_date,
                "prescriptionNumber": prescription_name,
                "instructions": prescription_instructions,
                "prescriptionLineItems": line_items  # List of all items
            }
            prescription_summaries.append(prescription_summary)

        return prescription_summaries
    else:
        return {"msg": "No Prescriptions found associated with the user"}

    
def get_contact_related_data(contact_id):
    try:
        # Querying only the Name, Id, Phone, and Age of the contact
        contact_data = sf.query(f"SELECT Id, Screening_Date__c, Risk_Percentage_for_Cardiovascular_Disea__c, Blood_Pressure__c, Random_Blood_Sugar__c, BMI__c, Height_cm__c, Weight_kg__c, Display_Photo_URL__c, Name, Phone, Age__c FROM Contact WHERE Id = '{contact_id}'")['records'][0]
        contact_info = {
            'id': contact_data['Id'],
            'name': contact_data['Name'],
            'phone': contact_data['Phone'],
            'age': contact_data['Age__c'],
            'displayPhoto': contact_data['Display_Photo_URL__c'],
            'screeningDate': contact_data['Screening_Date__c'],
            'riskPercentageForCVD': contact_data['Risk_Percentage_for_Cardiovascular_Disea__c'],
            'bloodPressure': contact_data['Blood_Pressure__c'],
            'randomBloodSugar': contact_data['Random_Blood_Sugar__c'],
            'bmi': contact_data['BMI__c'],
            'heightCm': contact_data['Height_cm__c'],
            'weightKg': contact_data['Weight_kg__c']
        }

        # Querying prescriptions and their line items
        prescription_query = sf.query_all(f"""
            SELECT Id, Name, Prescribing_Practitioner__c, (SELECT Id, Name, Inventory_Name__c, Tablet__c, Notes__c, Generic_Name__c, Status__c, Frequency__c FROM Prescription_Line_Items__r)
            FROM Prescription__c
            WHERE Patient__c = '{contact_id}'
        """)['records']

        # Extract unique practitioner IDs
        practitioner_ids = list(set(pres['Prescribing_Practitioner__c'] for pres in prescription_query if pres.get('Prescribing_Practitioner__c')))

        # Second query to get practitioner names
        if practitioner_ids:
            practitioners_query = sf.query_all(f"""
                SELECT Id, Name
                FROM Contact
                WHERE Id IN ({",".join([f"'{id}'" for id in practitioner_ids])})
            """)['records']
            # Create a dictionary for quick lookup of practitioner names
            practitioners_dict = {pract['Id']: pract['Name'] for pract in practitioners_query}
        else:
            practitioners_dict = {}

        # Formatting prescriptions to include only specific fields
        prescriptions = [
            {
                'prescriptionId': pres['Id'],
                'prescriptionName': pres['Name'],
                'expirationDate': None,
                'prescriber': practitioners_dict.get(pres.get('Prescribing_Practitioner__c')),
                'prescriptionLineItems': [
                    {
                        'id': item['Id'],
                        'name': item['Name'],
                        'inventoryName': item['Inventory_Name__c'],
                        'genericName': item['Generic_Name__c'],
                        'status': item['Status__c'],
                        "tablet": item['Tablet__c'],
                        "notes": item['Notes__c'],
                        'frequency': item['Frequency__c']
                    } for item in pres['Prescription_Line_Items__r']['records']
                ] if pres.get('Prescription_Line_Items__r') and 'records' in pres['Prescription_Line_Items__r'] else []
            } for pres in prescription_query
        ]

        # Querying subscriptions
        subscription_query = sf.query_all(f"""
            SELECT Id, Name, Delivery_Frequency__c, Next_Billing_Date__c, Next_Delivery_Date__c
            FROM Subscription__c
            WHERE Customer__c = '{contact_id}'
        """)['records']

        # Formatting subscriptions to include only specified fields
        subscriptions = [
            {
                'subscriptionId': sub['Id'],
                'subscriptionName': sub['Name'],
                'deliveryFrequency': sub['Delivery_Frequency__c'],
                'nextBillingDate':sub['Next_Billing_Date__c'],
                'nextDeliveryDate':sub['Next_Delivery_Date__c']
            } for sub in subscription_query
        ]

        # Querying opportunities associated with the contact and their line items
        opportunity_query = sf.query_all(f"""
            SELECT Id, Opportunity_Number__c, Name, CloseDate, Order_Duration__c, Amount
            FROM Opportunity
            WHERE StageName IN ('Delivered', 'Delivered-Paid', 'Closed Won') AND Patient_Name__c = '{contact_id}'
        """)['records']

        opportunities = []
        for opportunity in opportunity_query:
            opp_id = opportunity['Id']

            opportunity_info = {
                'opportunityId': opp_id,
                'opportunityNumber': opportunity['Opportunity_Number__c'],
                'opportunityName': opportunity['Name'],
                'closeDate': opportunity['CloseDate'],
                'orderDuration': opportunity.get('Order_Duration__c'),
                'price': opportunity.get('Amount')
            }
            opportunities.append(opportunity_info)

        return {
            "contact": contact_info,
            "prescriptions": prescriptions,
            "subscriptions": subscriptions,
            "opportunities": opportunities
        }
    except Exception as e:
        return {"error": str(e)}

def create_shopify_customer(first_name, last_name, phone):
    url = BASEURL+"/customers.json"
    headers = {
        "Content-Type": "application/json",
        "X-Shopify-Access-Token": access_key
    }
    customer_data = {
        "customer": {
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone
        }
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(customer_data))
    
    if response.status_code == 201:
        print("Customer created successfully!")
        return response.json()
    else:
        print(f"Failed to create customer. Status code: {response.status_code}, Response: {response.text}")
        return None

def check_user_status(user_phone):
    existing_accounts = sf.query(f"SELECT Id, PIN_Code__c, Name, Shopify_Customer_ID__c FROM Account WHERE Phone = '{user_phone}'")
    # user_phone = format_phone_number(user_phone)
    shopify_check_user_url = BASEURL + f"/customers/search.json"
    params = {
        'query': f'phone:{user_phone}'
    }

    response = requests.get(shopify_check_user_url, params=params, headers={"X-Shopify-Access-Token": access_key})
    response_data = response.json()

    if response.status_code != 200 or response_data['customers'] == []:
        shopify_status = "no_account"
    else:
        shopify_status = "account_exists"

    if existing_accounts['totalSize'] > 0:
        # Account exists
        account = existing_accounts['records'][0]
        account_id = account['Id']
        account_name = account['Name']
        
        if not account['PIN_Code__c'] and shopify_status == "no_account":
            return {"status": "exists_no_pin", "account_id": account_id, "shopify_status": shopify_status}
        elif not account['PIN_Code__c'] and shopify_status == "account_exists":
            return {"status": "exists_no_pin", "account_id": account_id, "shopify_status": shopify_status}
        elif account['PIN_Code__c'] and shopify_status == "no_account":
            if not account['Shopify_Customer_ID__c']:
                new_customer = create_shopify_customer(first_name="", last_name=account_name, phone=user_phone)
                if new_customer:
                    shopify_id = new_customer['customer']['id']
                    if shopify_id:
                        shopify_status = "account_exists"
            return {"status": "exists_with_pin", "account_id": account_id, "shopify_status": shopify_status}
        elif account['PIN_Code__c'] and shopify_status == "account_exists":
            return {"status": "exists_with_pin", "account_id": account_id, "shopify_status": shopify_status}
    else:
        return {"status": "not_exists", "shopify_status": shopify_status}

def handle_existing_customer_new_app_user(account_id, fcm_token, user_pin, firebase_uid, shopify_status):
    account = sf.query(f"SELECT Name, Phone FROM Account WHERE Id = '{account_id}'")
    user_name = account['records'][0]['Name']
    user_phone = account['records'][0]['Phone']

    shopify_id = ""

    if shopify_status != "account_exists":
        new_customer = create_shopify_customer(first_name="",last_name=user_name,phone=user_phone)
        if new_customer:
            shopify_id = new_customer['customer']['id']
    else:
        shopify_check_user_url = BASEURL + f"/customers/search.json"
        params = {
            'query': f'phone:{user_phone}'
        }

        response = requests.get(shopify_check_user_url, params=params, headers={"X-Shopify-Access-Token": access_key})
        response_data = response.json()

        if response.status_code != 200 or response_data['customers'] == []:
            raise ValueError('Invalid Phone Number or Shopify Status')
        else:
            shopify_id=response_data['customers'][0]['id']
    
    sf.Account.update(account_id, {'PIN_Code__c': user_pin, 'FCM_Token__c': fcm_token, 'Firebase_UID__c': firebase_uid, 'Shopify_Customer_ID__c': shopify_id})
    return {
        'fcmToken': fcm_token,
        'userId': account_id,
        'firebaseUid': firebase_uid,
        'Shopify_Customer_ID__c': shopify_id
    }

def create_new_user(user_name, user_phone, fcm_token, user_country, user_pin, firebase_uid, shopify_status):
    
    if user_country == "Philippines":
        currency = 'USD'
    elif user_country == "Myanmar":
        currency = 'MMK'
    shopify_id = ""

    if shopify_status != "account_exists":
        new_customer = create_shopify_customer(first_name="",last_name=user_name,phone=user_phone)
        if new_customer:
            shopify_id = new_customer['customer']['id']
    else:
        shopify_check_user_url = BASEURL + f"/customers/search.json"
        params = {
            'query': f'phone:{user_phone}'
        }

        response = requests.get(shopify_check_user_url, params=params, headers={"X-Shopify-Access-Token": access_key})
        response_data = response.json()

        if response.status_code != 200 or response_data['customers'] == []:
            raise ValueError('Invalid Phone Number or Shopify Status')
        else:
            shopify_id=response_data['customers'][0]['id']

    new_account = {
        'Name': user_name,
        'Phone': user_phone,
        'RecordTypeId': '0124x000000ZGecAAG',
        'CurrencyIsoCode': currency,
        'Country__c':user_country,
        'FCM_Token__c': fcm_token,
        'PIN_Code__c': user_pin,
        'Firebase_UID__c':firebase_uid,
        'Shopify_Customer_ID__c': shopify_id
    }
    response = sf.Account.create(new_account)
    new_contact = {
        'LastName': user_name,
        'AccountId': response.get('id'),
        'RecordTypeId': '0124x000000ZGiKAAW',
        'Phone': user_phone,
        'CurrencyIsoCode': currency
    }
    response_contact = sf.Contact.create(new_contact)
    new_user_response = {
        'name':user_name,
        'fcmToken':fcm_token,
        'userId':response.get('id'),
        'firebaseUid':firebase_uid
    }
    return new_user_response

def update_user_fcm(fcm_token, user_id):
    new_account_details = {
        'FCM_Token__c': fcm_token
    }

    response = sf.Account.update(user_id, new_account_details)
    new_user_response = {
        'response': 'Account updated successfully!',
        'fcmToken':fcm_token,
        'userId':user_id
    }
    return new_user_response

def update_user(update_data, user_id):
    try:
        sf.Account.update(user_id, update_data)
        new_user_response = {
            'response': 'Account updated successfully!',
            'userId': user_id
        }
        return new_user_response
    except SalesforceResourceNotFound:
        return jsonify({'error': 'User not found in Salesforce with ID: {}'.format(user_id)}), 404
    except SalesforceMalformedRequest as e:
        return jsonify({'error': 'Invalid data provided; Salesforce could not process the request. Details: {}'.format(e)}),400
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred: {}'.format(e)}),500

def update_user_pin(user_id, pin):
    try:
        sf.Account.update(user_id, {'PIN_Code__c':pin})
        new_user_response = {
            'response': 'Account updated successfully!',
            'userId': user_id
        }
        return new_user_response
    except SalesforceResourceNotFound:
        return jsonify({'error': 'User not found in Salesforce with ID: {}'.format(user_id)}), 404
    except SalesforceMalformedRequest as e:
        return jsonify({'error': 'Invalid data provided; Salesforce could not process the request. Details: {}'.format(e)}),400
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred: {}'.format(e)}),500

def update_rating_sf(opportunity_id, rating):
    try:
        sf.Opportunity.update(opportunity_id, {
            'Net_Promoter_Score__c': rating
        })
        new_user_response = {
            'response': 'Rating updated successfully!',
            'opportunityId': opportunity_id
        }
        return new_user_response
    except SalesforceResourceNotFound:
        return jsonify({'error': 'User not found in Salesforce with ID: {}'.format(opportunity_id)}), 404
    except SalesforceMalformedRequest as e:
        return jsonify({'error': 'Invalid data provided; Salesforce could not process the request. Details: {}'.format(e)}),400
    except Exception as e:
        return jsonify({'error': 'An unexpected error occurred: {}'.format(e)}),500

def update_opportunity_sf(new_stage, opp_id):
    try:
        # Check if the Opportunity exists
        sf.Opportunity.get(opp_id)

        # Update the Opportunity stage
        sf.Opportunity.update(opp_id, {
            'StageName': new_stage
        })
        return {'response': 'Opportunity updated successfully!', 'opportunityId':opp_id}
    except SalesforceResourceNotFound:
        # Opportunity ID is not found
        return jsonify({'error': 'Opportunity not found'}), 404
    except SalesforceMalformedRequest as e:
        # Handling cases such as invalid field values or fields that do not exist
        return jsonify({'error': 'Malformed request: ' + str(e)}), 400
    except Exception as e:
        # Generic error handling for any other unexpected errors
        return jsonify({'error': 'An error occurred: ' + str(e)}), 500

def find_user_by_phone(phone):
    query = f"SELECT Name, Id FROM Account WHERE Phone = '{phone}'"
    response = sf.query(query)

    if response['totalSize'] > 0:
        account_details = response['records'][0]
        user_details= {
            "name": account_details.get('Name'),
            "accountId":account_details.get('Id')
        }
        return user_details
    else:
        raise ValueError ("No user found!")

def validate_pin(phone, pin):
    try:
        # Log the initial phone number and pin
        logging.info(f"Validating PIN for phone number: {phone}")

        # Query to check if a user exists with the given phone number
        user_query = f"SELECT Name, Id FROM Account WHERE Phone = '{phone}'"
        user_response = sf.query(user_query)
        
        if user_response['totalSize'] == 0:
            logging.error(f"No user found for phone number: {phone}")
            raise ValueError("No user found!")
        
        # Query to check if the user with the given phone number has the correct PIN
        pin_query = f"SELECT Name, Id FROM Account WHERE Phone = '{phone}' AND PIN_Code__c = {pin}"
        pin_response = sf.query(pin_query)
        
        if pin_response['totalSize'] > 0:
            account_details = pin_response['records'][0]
            user_details = {
                "name": account_details.get('Name'),
                "accountId": account_details.get('Id')
            }
            logging.info(f"User validated successfully for phone number: {phone}")
            return user_details
        else:
            logging.error(f"Wrong PIN for phone number: {phone}")
            raise ValueError("Wrong PIN!")
    except Exception as e:
        logging.exception("An error occurred during PIN validation")
        raise
    

def create_payment_method(account_id, data):
    try:
        new_payment = {
            'Provider_Name__c': data['providerName'],
            'Method_Name__c': data['methodName'],
            'Customer_Phone_Number__c': data['customerPhone'],
            'Customer_Name__c': data['customerName'],
            'Default_Payment_Method__c': data['defaultPaymentMethod'],
            'CurrencyIsoCode': data['currency'],
            'Account__c': account_id
        }
        response = sf.Payment__c.create(new_payment)
        return response
    except SalesforceMalformedRequest as e:
        raise e

def update_payment_method(payment_id, data):
    try:
        update_payment = {}
        if 'providerName' in data:
            update_payment['Provider_Name__c'] = data['providerName']
        if 'methodName' in data:
            update_payment['Method_Name__c'] = data['methodName']
        if 'customerPhone' in data:
            update_payment['Customer_Phone_Number__c'] = data['customerPhone']
        if 'customerName' in data:
            update_payment['Customer_Name__c'] = data['customerName']
        if 'defaultPaymentMethod' in data:
            update_payment['Default_Payment_Method__c'] = data['defaultPaymentMethod']
        if 'currency' in data:
            update_payment['CurrencyIsoCode'] = data['currency']

        response = sf.Payment__c.update(payment_id, update_payment)
        
        return {
            "id": payment_id,
            "message": "Payment method updated successfully"
        }
    except SalesforceMalformedRequest as e:
        raise e

def create_payment_history(opportunity_id, merchant_order_id, provider_name):
    try:
        account_query = f"""
        SELECT AccountId
        FROM Opportunity
        WHERE Id = '{opportunity_id}'
        """
        account_result = sf.query(account_query)

        if account_result['records']:
            account_id = account_result['records'][0]['AccountId']
        else:
            raise ValueError ("No Account found for the given Opportunity ID")
        
        method_name = ''

        if provider_name == "MPU":
            method_name = "OTP"
        elif provider_name == "KBZ Pay":
            method_name = "APP"

        # Data to be inserted into Payment_History__c
        payment_data = {
            'Merchant_Order_ID__c': merchant_order_id,
            'CurrencyIsoCode': 'MMK',
            'Provider_Name__c': provider_name,
            'Opportunity__c':opportunity_id,
            'Method_Name__c':method_name,
            'Account__c': account_id  # Assuming AccountId__c is the relationship field on Payment_History__c
        }

        # Insert the new Payment History record
        sf.Payment_History__c.create(payment_data)
        return {
            "success": "Payment history created successfully",
            "merchantOrderId": merchant_order_id
                }

    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
def create_salesforce_case(case_data):
    try:
        # Check required fields
        required_fields = ['subject', 'description', 'suppliedName', 'suppliedEmail', 'sendbirdUserId', 'sendbirdChannelUrl', 'isEinsteinBotsCase']
        for field in required_fields:
            if field not in case_data:
                return jsonify({"error": f"Missing required field: {field}"}), 400

        # Create a new Case with provided data
        new_case = {
            'Subject': case_data.get('subject'),
            'Description': case_data.get('description'),
            'SuppliedName': case_data.get('suppliedName'),
            'SuppliedEmail': case_data.get('suppliedEmail'),
            'Sendbird__UserId__c': case_data.get('sendbirdUserId'),
            'Sendbird__ChannelUrl__c': case_data.get('sendbirdChannelUrl'),
            'Sendbird__IsEinsteinBotsCase__c': case_data.get('isEinsteinBotsCase'),
            'AccountId': case_data.get('sendbirdUserId')
        }

        # Insert the new case into Salesforce
        case_result = sf.Case.create(new_case)
        case_id = case_result['id']

        # Query the Account to find the Contact with the same name as the Account holder
        account_id = case_data.get('sendbirdUserId')
        account = sf.Account.get(account_id)
        contact_name = account['Name']

        # Query for the contact with the same name
        contacts = sf.query(f"SELECT Id FROM Contact WHERE (Name = '{contact_name}' OR LastName = '{contact_name}') AND AccountId = '{account_id}'")
        if contacts['totalSize'] > 0:
            contact_id = contacts['records'][0]['Id']

            # Update the Case with the ContactId
            sf.Case.update(case_id, {'ContactId': contact_id})

        return jsonify({"success": True, "case_id": case_id}), 201

    except SalesforceMalformedRequest as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# # account_id_to_find = 'A-41225'
# account_id_to_find = '001VE000008xC0dYAE'

# query = f"SELECT Id, Name, Account_ID__c, RecordTypeId, CurrencyIsoCode,(SELECT Id, AccountId, Name, OtherPhone, Member_ID__c, Age__c FROM Contacts) FROM Account WHERE ID = '{account_id_to_find}'"
# # query = f"SELECT Provider_Name__c, Method_Name__c, Customer_Phone_Number__c, Customer_Name__c FROM Opportunity WHERE AccountId = '{account_id_to_find}'"
# # query = f"SELECT ID, Amount, Shopify_Order_Number__c,Name FROM Opportunity WHERE AccountId = '{account_id_to_find}' AND StageName = 'Ordered'"
# response = sf.query(query)
# # if response['totalSize'] > 0:
# #     opportunity_details = response['records'][0]
# #     opportunity_id = opportunity_details.get('Id')
# #     opportunity_amount = opportunity_details.get('Amount')
# #     opportunity_shopify_order_no = opportunity_details.get('Shopify_Order_Number__c')
# #     opportunity_name = opportunity_details.get('Name')
# #     opp_item_query = f"SELECT Product__c, Price__c, Quantity__c, Shopify_Order_Number__c, 	Date__c FROM Opportunity_Item__c WHERE Opportunity__c = '{opportunity_id}' "
# #     opp_item = sf.query(opp_item_query)
# #     if opp_item['totalSize'] > 0:
# #         opp_item_details=opp_item['records'][0]
# #         opp_item_products= opp_item_details.get('Product__c')
# #         opp_item_price= opp_item_details.get('Price__c')
# #         opp_item_quantity= opp_item_details.get('Quantity__c')
# #         opp_item_shopify_order_no= opp_item_details.get('Shopify_Order_Number__c')
# #         opp_item_date= opp_item_details.get('Date__c')

# if response['totalSize'] > 0:
#     account_details = response['records'][0]
#     print("Account Details Found:", account_details)
#     # account_name = account_details.get('Name')
#     # account_id = account_details.get('Account_ID__c')
#     # print("Account Holder:",account_name)
#     # print("Account ID:",account_id)
# else:
#     print("No account found with this Account_ID__c.")