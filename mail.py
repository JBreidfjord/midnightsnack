import boto3

ses = boto3.client('ses')

def send_password_reset(email: str):
    ses.send_email(
        Source='The Midnight Snack <noreply@midnightsnack.ca>',
        Destination={
            'ToAddresses': [
                email,
            ]
        },
        Message={
            'Subject': {
                'Data': 'subject text'
            },
            'Body': {
                'Text': {
                    'Data': 'message text'
                },
                'Html': {
                    'Data': '<h3>Test</h3>'
                }
            }
        },
        ReturnPath='return@midnightsnack.ca'
    )