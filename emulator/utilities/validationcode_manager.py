import random
import string
from datetime import datetime, timedelta


class VerificationCodeManager:
    def __init__(self):
        self.codes = {}  # Dictionary to store code, username, and timestamp

    def generate_code(self, username):
        # Generate a random 6-character alphanumeric code
        code = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
        # Record the current timestamp and username
        self.codes[code] = {'username': username, 'time': datetime.now()}
        return code

    def validate_code(self, code, username):
        # Check if code is valid, not expired, and belongs to the given username
        self.clean_codes()
        if code in self.codes and self.codes[code]['username'] == username:
            code_time = self.codes[code]['time']
            if datetime.now() - code_time < timedelta(minutes=5):
                return True
        return False

    def clean_codes(self):
        # Remove codes older than 5 minutes
        current_time = datetime.now()
        self.codes = {code: details for code, details in self.codes.items() if current_time - details['time'] < timedelta(minutes=5)}