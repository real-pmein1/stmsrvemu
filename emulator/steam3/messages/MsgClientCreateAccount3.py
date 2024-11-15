class ClientCreateAccount3:
    def __init__(self, data: bytes):
        # Split the remaining data by the null byte separator
        parsed_data = data.split(b'\x00')

        # Extract the values
        self.username = parsed_data[1].decode('latin-1')
        self.password = parsed_data[2].decode('latin-1')
        self.email = parsed_data[3].decode('latin-1')
        self.security_question = parsed_data[4].decode('latin-1')
        self.security_answer = parsed_data[5].decode('latin-1')

    def __str__(self):
        return (f"Username: {self.username}\n"
                f"Password: {self.password}\n"
                f"Email: {self.email}\n"
                f"Security Question: {self.security_question}\n"
                f"Security Answer: {self.security_answer}")

    def __repr__(self):
        return (f"MsgClientInformOfCreateAccount(username={self.username!r}, password={self.password!r}, "
                f"email={self.email!r}, security_question={self.security_question!r}, security_answer={self.security_answer!r})")