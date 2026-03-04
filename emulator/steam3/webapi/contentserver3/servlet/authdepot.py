from appownershipticket import AppOwnershipTicket
from crypto import Crypto
from url_decoder import URLDecoder
from http_server import HttpServerRequest, HttpServerResponse, HttpSession
from logger import Logger

class AuthDepot:
    def __init__(self, provider, encryption_key_provider):
        self.provider = provider
        self.encryption_key_provider = encryption_key_provider
        self.logger = Logger()  # Assuming a logger class for logging

    def is_url_decode_request_parameters_values(self):
        return False

    def do_post(self, request: HttpServerRequest, response: HttpServerResponse):
        session = request.get_session()
        session_key = session.get_attribute('CS_SESSION_KEY')

        encoded_encrypted_app_ticket = request.get_parameter_value("appticket")

        if not encoded_encrypted_app_ticket:
            self.logger.error(f"{request.get_server().get_name()} - Required parameters not found")
            response.set_status(401)  # HTTP_STATUS_UNAUTHORIZED
            return

        encrypted_app_ticket = URLDecoder.decode(encoded_encrypted_app_ticket)

        result = self.auth(
            request,
            session,
            session_key.buffer,
            encrypted_app_ticket,
            len(encrypted_app_ticket),
            response
        )

        if result != 200:  # HTTP_STATUS_OK
            response.send_error(result)

    def auth(self, request: HttpServerRequest, session: HttpSession, encryption_key, encrypted_app_ticket, encrypted_app_ticket_length, response: HttpServerResponse):
        app_ticket = None

        try:
            app_ticket_bytes = Crypto.symmetric_decrypt(
                encrypted_app_ticket, encryption_key
            )
            ticket = AppOwnershipTicket.new_instance(app_ticket_bytes)

        except Exception as e:
            self.logger.error(f"{request.get_server().get_name()} - Error: {str(e)}")
            return 401  # HTTP_STATUS_UNAUTHORIZED

        if not ticket or not self.provider.validate_app_ownership_ticket(ticket):
            self.logger.error(f"{request.get_server().get_name()} - Error: Invalid ticket")
            return 401  # HTTP_STATUS_UNAUTHORIZED

        return self.auth_with_ticket(request, session, ticket, response)

    def auth_with_ticket(self, request: HttpServerRequest, session: HttpSession, ticket: AppOwnershipTicket, response: HttpServerResponse):
        self.logger.debug(
            f"{request.get_server().get_name()} - User #{ticket.get_steam_global_id()} authenticated for depot {ticket.get_app_id()}"
        )

        session_name = f"CS_APP_TICKET_{ticket.get_app_id()}"
        session.set_attribute(session_name, ticket)

        return 200  # HTTP_STATUS_OK