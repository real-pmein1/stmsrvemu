from flask import Flask, jsonify, request
from content_server.depot import DepotServlet
from content_server.auth import InitsessionServlet, AuthDepotServlet
from content_server.provider import Content3Provider
from content_server.serverlist import ServerlistServlet
from content_server.serverstatus import ServerstatusServlet


class Content3ServerWebApp:
    def __init__(self, app, server_type, provider, encryption_key_provider):
        """
        Initialize the Content3ServerWebApp.

        :param app: Flask application instance.
        :param server_type: The type of content server (e.g., CDN, SteamCache, CS).
        :param provider: The Content3Provider instance.
        :param encryption_key_provider: The EncryptionKeyProvider instance.
        """
        self.app = app
        self.server_type = server_type
        self.provider = provider
        self.encryption_key_provider = encryption_key_provider
        self.register_servlet_mappings()

    def register_servlet_mappings(self):
        """
        Register HTTP route mappings for the server.
        """
        # Route for depot handling
        depot_servlet = DepotServlet(self.server_type, self.provider, self.encryption_key_provider)
        self.app.add_url_rule('/depot/<int:depot_id>/<string:service>', view_func = depot_servlet.handle_request)

        # Route for server list handling
        serverlist_servlet = ServerlistServlet(self.provider)
        self.app.add_url_rule('/serverlist', view_func = serverlist_servlet.handle_request)

        # Route for server status
        serverstatus_servlet = ServerstatusServlet(self.provider)
        self.app.add_url_rule('/server-status', view_func = serverstatus_servlet.handle_request)

        initsession_servlet = InitsessionServlet(self.provider, self.encryption_key_provider)
        self.app.add_url_rule('/initsession', view_func = initsession_servlet.handle_request, methods = ["POST"])

        authdepot_servlet = AuthDepotServlet(self.provider, self.encryption_key_provider)
        self.app.add_url_rule('/authdepot', view_func = authdepot_servlet.handle_request, methods = ["POST"])